# agents/scheduler_d/negotiation.py (Corrección: Bucle simple con timeout)

import asyncio
import logging
import time
from typing import List, Dict, Any, Optional
from agents.scheduler_d.messages import PropuestaMessage, AceptarMessage, RechazarMessage, AsignarMessage

logger = logging.getLogger(__name__)

async def negotiate_with_candidates(
    scheduler_agent, # Referencia al SchedulerD para acceder a net_agent
    task_id: str,
    candidates: List[Dict[str, Any]],
    timeout: float = 5.0
) -> Optional[str]:
    """
    Envía PROPUESTA a candidatos y espera respuestas ACEPTAR/RECHAZAR.
    Devuelve el node_id del primer nodo que acepta, o None si ninguno acepta.
    """
    logger.info(f"[NEGOTIATION] Iniciando negociación para tarea {task_id} con {len(candidates)} candidatos.")

    # Enviar PROPUESTA a todos los candidatos
    for candidate_info in candidates:
        node_id = candidate_info["node_id"]
        score = candidate_info.get("score", 0.0)

        # Crear payload del mensaje de propuesta
        propuesta_payload = {
            "task_id": task_id,
            "node_id": node_id,
            "score": score
        }

        try:
            # Enviar mensaje de propuesta usando NetAgent del SchedulerD
            msg_id_sent = await scheduler_agent.net_agent.send_to_node_id(
                node_id, "SCHED_PROPUESTA", propuesta_payload, reliable=True, qos='CTRL'
            )
            if msg_id_sent:
                logger.debug(f"[NEGOTIATION] Enviada PROPUESTA para {task_id} a {node_id} (msg_id: {msg_id_sent})")
            else:
                logger.warning(f"[NEGOTIATION] Fallo al enviar PROPUESTA a {node_id}.")
        except Exception as e:
            logger.error(f"[NEGOTIATION] Error al enviar PROPUESTA a {node_id}: {e}")

    # Esperar respuestas durante el timeout
    winner_node_id = None
    start_time = time.time()

    # Bucle para esperar que el evento se active o se cumpla el timeout
    negotiation_info = scheduler_agent.pending_negotiations.get(task_id)
    if negotiation_info:
        event = negotiation_info.get('event')
        if event:
            # Espera el evento o el timeout manualmente
            while not event.is_set():
                if time.time() - start_time >= timeout:
                    logger.info(f"[NEGOTIATION] Timeout esperando respuesta para tarea {task_id}.")
                    break
                await asyncio.sleep(0.05) # Breve espera para ceder el control y evitar bucle ocupado

            # Ahora, el evento está seteado o se acabó el tiempo.
            # Leemos el resultado del diccionario.
            # Es importante leerlo *después* de que el evento se active para evitar race conditions.
            # Verificamos de nuevo si la entrada aún existe, por si acaso fue borrada por otro hilo o por un timeout anterior no manejado.
            negotiation_info_updated = scheduler_agent.pending_negotiations.get(task_id)
            if negotiation_info_updated:
                result = negotiation_info_updated.get('result')
                if result == 'ACEPTADO':
                    winner_node_id = negotiation_info_updated.get('accepted_node_id')
                    logger.info(f"[NEGOTIATION] Tarea {task_id} aceptada por {winner_node_id}.")
                # else: # Si result es 'RECHAZADO' o None (timeout), winner_node_id sigue siendo None
                # Limpiar la entrada de negociación pendiente *aquí* después de leer
                # Es importante que la limpieza ocurra en un solo lugar si es posible, pero aquí es seguro hacerlo
                # después de que el bucle haya terminado de esperar.
                scheduler_agent.pending_negotiations.pop(task_id, None) # Asegura la limpieza
            else:
                # Si no está, significa que otro proceso (posiblemente un timeout anterior o una respuesta rápida)
                # ya lo borró. En ese caso, winner_node_id ya es None.
                logger.debug(f"[NEGOTIATION] Entrada de negociación para {task_id} ya fue limpiada.")
        else:
            logger.error(f"[NEGOTIATION] No se encontró 'event' en pending_negotiations para {task_id}.")
    else:
        logger.error(f"[NEGOTIATION] No se encontró entrada en pending_negotiations para {task_id}.")


    if not winner_node_id:
        logger.info(f"[NEGOTIATION] Tarea {task_id} no fue aceptada por ningún candidato dentro del timeout.")

    return winner_node_id

