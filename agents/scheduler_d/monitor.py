# agents/scheduler_d/monitor.py (Correcciones de acceso a TaskDescriptor)

import asyncio
import logging
from .node_status import is_node_alive # Este archivo se puede eliminar si HealthAgent lo reemplaza

logger = logging.getLogger(__name__)

async def monitor_task(task, scheduler, health_agent=None, test_mode=False):
    """
    Monitorea la ejecución de la tarea:
      - Si el nodo asignado falla (según HealthAgent) -> reasignar
      - Si el nodo sigue vivo -> completar la tarea (esto lo haría el nodo ejecutor)
    """
    # --- CORRECCIÓN: Acceder a atributos de TaskDescriptor ---
    logger.info(f"[MONITOR] Iniciando monitor para tarea {task.task_id} en nodo {task.assigned_node}.") # <-- CORRECCIÓN

    if not health_agent:
        logger.warning(f"[MONITOR] HealthAgent no disponible para tarea {task.task_id}. Monitor inactivo.") # <-- CORRECCIÓN
        # Si no hay health_agent, no podemos monitorear activamente. La tarea podría quedar colgada.
        # Opcional: esperar un timeout largo y marcar como FAILED si no hay noticias.
        # Por ahora, salimos.
        return

    assigned_node_id = task.assigned_node # <-- CORRECCIÓN: Acceder directamente al atributo
    if not assigned_node_id:
        logger.error(f"[MONITOR] Tarea {task.task_id} no tiene nodo asignado.") # <-- CORRECCIÓN
        return

    while task.status not in ["COMPLETED", "FAILED"]: # <-- CORRECCIÓN: Acceder directamente al atributo
        await asyncio.sleep(task.checkpoint_interval if test_mode else task.checkpoint_interval) # <-- CORRECCIÓN

        # Verificar si el nodo está vivo usando HealthAgent
        # HealthAgent debería tener un método para consultar la salud de un nodo
        # Supongamos que health_agent.get_node_status(node_id) devuelve "ALIVE", "DOWN", "UNKNOWN"
        node_health_status = health_agent.get_node_status(assigned_node_id) # <-- Método a implementar en HealthAgent

        if node_health_status == "DOWN":
            logger.warning(f"[MONITOR] Nodo {assigned_node_id} asignado a tarea {task.task_id} está DOWN. Reasignando...") # <-- CORRECCIÓN
            # Nodo muerto → reasignar
            task.status = "PENDING" # <-- CORRECCIÓN: Asignar directamente al atributo
            task.assigned_node = None # <-- CORRECCIÓN: Asignar directamente al atributo
            # Opcional: eliminar réplica del modelo en el nodo caído de los metadatos de StoreD
            # Opcional: notificar al StoreD que el nodo no está disponible para replicación
            # Reenviar la tarea al scheduler para una nueva asignación
            # Esta parte es compleja. Idealmente, el SchedulerD tendría un método para reintentar una tarea.
            # Por ahora, simulamos reenviando la tarea original (lo cual no es ideal, debería haber un mecanismo de cola de tareas pendientes).
            # Una forma es llamar directamente a scheduler.submit_task de nuevo, pero eso requiere el spec original.
            # Supongamos que el scheduler mantiene el spec o el TaskDescriptor lo tiene.
            # scheduler.submit_task(task["binary_hash"], task["resources"], task["tags"], task.get("checkpoint_interval", 0.05))
            # Lo dejamos como un placeholder por ahora.
            # Lo ideal es que el SchedulerD tenga una cola de tareas fallidas y las reasigne.
            # Por simplicidad, no lo implementamos aquí, pero se entiende el concepto.
            logger.info(f"[MONITOR] Lógica de reasignación para tarea {task.task_id} es un placeholder.") # <-- CORRECCIÓN
            return # Terminar este monitor, la reasignación la manejaría otra parte del SchedulerD

        elif node_health_status == "UNKNOWN":
            logger.debug(f"[MONITOR] Estado del nodo {assigned_node_id} para tarea {task.task_id} es UNKNOWN. Continuando monitoreo...") # <-- CORRECCIÓN

        # Si node_health_status == "ALIVE", continuar monitoreo

        # En un sistema real, el nodo ejecutor enviaría mensajes de progreso o de finalización.
        # Aquí, solo monitoreamos la salud del nodo. La finalización la debe manejar el nodo o el sistema de mensajes.
        # Para pruebas, podríamos simular la finalización si test_mode=True
        if test_mode:
            logger.info(f"[MONITOR] Tarea {task.task_id} simulada como COMPLETED.") # <-- CORRECCIÓN
            task.status = "COMPLETED" # <-- CORRECCIÓN: Asignar directamente al atributo
            return

    logger.info(f"[MONITOR] Monitor para tarea {task.task_id} finalizado. Estado final: {task.status}") # <-- CORRECCIÓN