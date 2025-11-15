# protocol.py
from .messages import PropuestaMessage, AceptarMessage, RechazarMessage, AsignarMessage

class SchedulerProtocol:
    def __init__(self):
        self.propuestas = {}  # task_id -> {node_id: score}
        self.asignaciones = {}  # task_id -> node_id

    def send_propuesta(self, target_node, task_id, score):
        msg = PropuestaMessage("scheduler", task_id, score)
        self.propuestas.setdefault(task_id, {})[target_node] = score
        print(f"[PROTOCOL] PROPUESTA a {target_node} tarea {task_id} score {score}")

    def send_aceptar(self, source_node, task_id):
        msg = AceptarMessage("scheduler", task_id)
        self.asignaciones[task_id] = source_node
        print(f"[PROTOCOL] ACEPTAR de {source_node} tarea {task_id}")

    def send_rechazar(self, source_node, task_id):
        msg = RechazarMessage("scheduler", task_id)
        print(f"[PROTOCOL] RECHAZAR de {source_node} tarea {task_id}")

    def send_asignar(self, target_node, task_id):
        msg = AsignarMessage("scheduler", target_node, task_id)
        self.asignaciones[task_id] = target_node
        print(f"[PROTOCOL] ASIGNAR a {target_node} tarea {task_id}")

    def handle_message(self, message):
        if message.type == "PROPUESTA":
            print(f"[PROTOCOL] Recibida PROPUESTA de {message.source} tarea {message.task_id} score {message.score}")
        elif message.type == "ACEPTAR":
            self.asignaciones[message.task_id] = message.source
            print(f"[PROTOCOL] Recibido ACEPTAR de {message.source} tarea {message.task_id}")
        elif message.type == "RECHAZAR":
            print(f"[PROTOCOL] Recibido RECHAZAR de {message.source} tarea {message.task_id}")
        elif message.type == "ASIGNAR":
            self.asignaciones[message.task_id] = message.target
            print(f"[PROTOCOL] Recibido ASIGNAR tarea {message.task_id} a {message.target}")
