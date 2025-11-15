# messages.py

class PropuestaMessage:
    def __init__(self, source, task_id, score):
        self.type = "PROPUESTA"
        self.source = source
        self.task_id = task_id
        self.score = score

class AceptarMessage:
    def __init__(self, source, task_id):
        self.type = "ACEPTAR"
        self.source = source
        self.task_id = task_id

class RechazarMessage:
    def __init__(self, source, task_id):
        self.type = "RECHAZAR"
        self.source = source
        self.task_id = task_id

class AsignarMessage:
    def __init__(self, source, target, task_id):
        self.type = "ASIGNAR"
        self.source = source
        self.target = target
        self.task_id = task_id
