# scheduler.py
import asyncio
import uuid
from .score import ScoreCalculator
from .protocol import SchedulerProtocol
from .monitor import monitor_task

class SchedulerD:
    def __init__(self, discover):
        self.discover = discover
        self.protocol = SchedulerProtocol()
        self.tasks = {}
        self.score_calculator = ScoreCalculator()  # ← 🔥 ESTA LÍNEA ES CLAVE

    async def submit_task(self, binary_hash, resources, tags=[], checkpoint_interval=0.1):
        task_id = str(uuid.uuid4())
        task = {
            "task_id": task_id,
            "binary_hash": binary_hash,
            "resources": resources,
            "tags": tags,
            "status": "PENDING",
            "assigned_node": None,
            "checkpoint_interval": checkpoint_interval
        }

        candidates = self.discover.buscar(tags)
        nodes_info = candidates  # tu discover devuelve un dict {node_id: {...}}

        best_node, scores = self.score_calculator.choose_best_node(nodes_info)

        if not best_node:
            print(f"[SCHEDULER] ❌ No hay nodos disponibles para tarea {task_id}")
            task["status"] = "FAILED"
            self.tasks[task_id] = task
            return task_id

        task["assigned_node"] = best_node
        task["status"] = "ASSIGNED"
        self.tasks[task_id] = task

        # Enviar mensaje de propuesta
        self.protocol.send_propuesta(best_node, task_id, scores[best_node])

        # Iniciar monitor de tarea
        asyncio.create_task(monitor_task(task, self))


        print(f"[SCHEDULER] ✅ Tarea {task_id[:8]} asignada a {best_node} con score {scores[best_node]}")
        return task_id

    def get_task_status(self, task_id):
        return self.tasks.get(task_id, {}).get("status", "UNKNOWN")
