# agents/scheduler_d/scheduler.py (Modificaciones para negociación y monitorización)

import asyncio
import uuid
import logging
from typing import Dict, Any, Tuple

from .score import ScoreCalculator
from .protocol import SchedulerProtocol
from .monitor import monitor_task
from .task_descriptor import TaskDescriptor
from .negotiation import negotiate_with_candidates # Importar la nueva función

# Definir tipos de mensajes de negociación si no existen
MSG_PROPUESTA = "SCHED_PROPUESTA"
MSG_ACEPTAR = "SCHED_ACEPTAR"
MSG_RECHAZAR = "SCHED_RECHAZAR"
MSG_ASIGNAR = "SCHED_ASIGNAR"

logger = logging.getLogger(__name__)

class SchedulerD:
    def __init__(self, discover_agent, store_agent, net_agent=None):
        self.discover_agent = discover_agent
        self.store_agent = store_agent
        self.net_agent = net_agent
        self.protocol = SchedulerProtocol()
        self.task_descriptors = {} # Usamos TaskDescriptor
        self.score_calculator = ScoreCalculator()

        # --- Nuevo: Diccionario para manejar respuestas de negociación ---
        self.pending_negotiations = {} # task_id -> {'event': asyncio.Event, 'result': str ('ACEPTADO'/'RECHAZADO'/None), 'accepted_node_id': str}

        # --- Nuevo: Referencia a HealthAgent (opcional, se inyecta después) ---
        self.health_agent = None

        # --- Registrar handler en NetAgent si está disponible ---
        if self.net_agent:
            self.net_agent.add_handler(self.handle_negotiation_message)

    # --- Nuevo: Setter para HealthAgent ---
    def set_health_agent(self, health_agent):
        self.health_agent = health_agent

    # --- Nuevo: Handler para mensajes de negociación ---
    async def handle_negotiation_message(self, msg: Dict[str, Any], addr: Tuple[str, int]):
        msg_type = msg.get("type")
        payload = msg.get("payload", {})
        src = msg.get("src") # Nodo que responde
        task_id = payload.get("task_id")

        if msg_type == MSG_ACEPTAR and task_id in self.pending_negotiations:
            pending = self.pending_negotiations[task_id]
            pending['result'] = 'ACEPTADO'
            pending['accepted_node_id'] = src # Guardar el nodo que aceptó
            pending['event'].set() # Liberar el evento de espera
            logger.info(f"[SCHEDULER] Negociación para tarea {task_id} ACEPTADA por {src}.")
        elif msg_type == MSG_RECHAZAR and task_id in self.pending_negotiations:
            pending = self.pending_negotiations[task_id]
            # No necesariamente terminamos la espera aquí, solo registramos el rechazo.
            # La negociación termina cuando alguien acepta o se acaba el timeout.
            # Por ahora, solo logueamos.
            logger.info(f"[SCHEDULER] Negociación para tarea {task_id} RECHAZADA por {src}.")
            # Opcional: Contar rechazos y terminar si todos rechazan antes del timeout.
            # Por simplicidad, no lo implementamos aquí.

    async def submit_task(self, binary_hash, resources, tags=[], checkpoint_interval=0.1):
        task_id = str(uuid.uuid4())
        task_desc = TaskDescriptor(
            task_id=task_id,
            binary_hash=binary_hash,
            resources=resources,
            tags=tags,  # Aseguramos que tags se pasa
            checkpoint_interval=checkpoint_interval,
            status="PENDING"
        )
        self.task_descriptors[task_id] = task_desc

        # Usar discover_agent.buscar
        candidates_info = await self.discover_agent.buscar({"ram_mb": resources.get("ram_mb", 0), "tags": tags}, k=5)

        nodes_info = {}
        for entry in candidates_info:
            ram_total_mb = 1024  # Valor de ejemplo
            # --- CORRECCIÓN: Acceder como diccionario ---
            ram_usage = (ram_total_mb - entry[
                "ram_free_mb"]) / ram_total_mb if ram_total_mb > 0 else 0.0  # <--- Cambiado
            nodes_info[entry["node_id"]] = {  # <--- Cambiado
                "cpu": entry["cpu_load"],  # <--- Cambiado
                "ram": ram_usage,
                "reputacion": entry["reputation"],  # <--- Cambiado
                "rtt": entry["rtt_ms"]  # <--- Cambiado
            }

        best_node, scores = self.score_calculator.choose_best_node(nodes_info)

        if not best_node:
            logger.error(f"[SCHEDULER] ❌ No hay nodos disponibles para tarea {task_id}")
            task_desc.status = "FAILED"
            return task_id

        # --- Nueva Lógica: Negociación ---
        negotiation_success = False
        winner_node_id = None
        if self.net_agent:
            # Preparar lista de candidatos con scores para la negociación
            candidate_list = []
            for node_id, score in scores.items():
                 candidate_list.append({"node_id": node_id, "score": score})

            # Registrar la negociación pendiente
            negotiation_event = asyncio.Event()
            self.pending_negotiations[task_id] = {'event': negotiation_event, 'result': None, 'accepted_node_id': None}

            # Iniciar negociación
            winner_node_id = await negotiate_with_candidates(self, task_id, candidate_list, timeout=5.0)

            if winner_node_id:
                negotiation_success = True
                task_desc.assigned_node = winner_node_id
                task_desc.status = "ASSIGNED"
                logger.info(f"[SCHEDULER] Tarea {task_id} asignada a {winner_node_id} tras negociación exitosa.")

                # --- Enviar mensaje de ASIGNACIÓN ---
                asignar_payload = {
                    "task_id": task_id,
                    "binary_hash": binary_hash, # Incluir hash del binario a ejecutar
                    "resources": resources,
                    "checkpoint_interval": checkpoint_interval
                }
                try:
                    await self.net_agent.send_to_node_id(winner_node_id, MSG_ASIGNAR, asignar_payload, reliable=True, qos='CTRL')
                    logger.info(f"[SCHEDULER] Mensaje ASIGNAR enviado a {winner_node_id} para tarea {task_id}.")
                except Exception as e_assign:
                    logger.error(f"[SCHEDULER] Error al enviar ASIGNAR a {winner_node_id}: {e_assign}")
                    task_desc.status = "FAILED"
                    negotiation_success = False
            else:
                logger.error(f"[SCHEDULER] ❌ Negociación fallida para tarea {task_id}. Ningún nodo aceptó.")
                task_desc.status = "FAILED"
        else:
            logger.error(f"[SCHEDULER] ERROR: No hay NetAgent disponible para negociar tarea {task_id}.")
            task_desc.status = "FAILED"

        # --- Iniciar monitor de tarea si la asignación fue exitosa ---
        if negotiation_success and self.health_agent: # Asegurar que HealthAgent esté disponible
            # Pasar la instancia de health_agent al monitor
            asyncio.create_task(monitor_task(task_desc, self, health_agent=self.health_agent))
        elif negotiation_success:
             # Si no hay HealthAgent, simulamos la ejecución o marcamos como RUNNING indefinidamente
             logger.warning(f"[SCHEDULER] HealthAgent no disponible para monitorear tarea {task_id}. Ejecución simulada.")
             # Podríamos iniciar una simulación aquí o esperar a que HealthAgent se inyecte.
             # Por ahora, simulamos que termina después de un tiempo.
             async def simulate_execution():
                 await asyncio.sleep(5) # Simular tiempo de ejecución
                 current_desc = self.task_descriptors.get(task_id)
                 if current_desc and current_desc.status == "ASSIGNED": # Asegurar estado correcto
                     current_desc.status = "COMPLETED"
                     result_data = b"result_for_" + task_id.encode('utf-8')
                     result_hash = self.store_agent.put(result_data)
                     current_desc.result_hash = result_hash
                     logger.info(f"[SCHEDULER] Tarea {task_id} simulada como COMPLETED. Resultado en hash: {result_hash}")
             asyncio.create_task(simulate_execution())


        if negotiation_success:
            logger.info(f"[SCHEDULER] ✅ Tarea {task_id[:8]} negociada y asignada con éxito a {winner_node_id}.")
        else:
            logger.error(f"[SCHEDULER] ❌ Tarea {task_id[:8]} no pudo ser asignada tras negociación.")

        return task_id

    def get_task_status(self, task_id):
        task_desc = self.task_descriptors.get(task_id)
        return task_desc.status if task_desc else "UNKNOWN"

    def get_task_result_hash(self, task_id):
        task_desc = self.task_descriptors.get(task_id)
        return task_desc.result_hash if task_desc else None

    async def submit_task_from_api(self, task_spec: dict):
        task_id = task_spec.get("task_id")
        binary_hash = task_spec.get("binary_hash")
        resources = task_spec.get("resources", {})
        tags = task_spec.get("tags", [])
        checkpoint_interval = task_spec.get("checkpoint_interval", 0.1)

        assigned_task_id = await self.submit_task(binary_hash, resources, tags, checkpoint_interval)
        return assigned_task_id if assigned_task_id == task_id else None