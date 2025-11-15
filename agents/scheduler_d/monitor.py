# monitor.py
import asyncio
from .node_status import is_node_alive

async def monitor_task(task, scheduler, test_mode=False):
    """
    Simula la ejecución de la tarea:
      - Si el nodo falla -> reasignar
      - Si el nodo sigue vivo -> completar la tarea
    """
    while task["status"] not in ["COMPLETED", "FAILED"]:
        await asyncio.sleep(task.get("checkpoint_interval", 0.05) if test_mode else task.get("checkpoint_interval", 1))

        node_alive = is_node_alive(task["assigned_node"])
        if not node_alive:
            # Nodo muerto → reasignar
            task["status"] = "PENDING"
            task["assigned_node"] = None
            await scheduler.submit_task(
                task["binary_hash"],
                task["resources"],
                task["tags"],
                task.get("checkpoint_interval", 0.05)
            )
            return

        # Nodo vivo → completar la tarea
        task["status"] = "COMPLETED"

        if test_mode:
            return
