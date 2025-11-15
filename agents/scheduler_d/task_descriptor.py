# scheduler_d/task_descriptor.py
from dataclasses import dataclass, field
from typing import Dict, Any
import time

@dataclass
class TaskDescriptor:
    task_id: str
    binary_hash: str
    resources: Dict[str, Any]      # e.g., {'cpu': 2, 'ram': 256}
    tags: list[str]                # requisitos o etiquetas
    checkpoint_interval: int = 30
    assigned_node: str = None
    status: str = "PENDING"       # PENDING, ASSIGNED, RUNNING, COMPLETED, FAILED
    created_at: float = field(default_factory=time.time)
    last_update: float = field(default_factory=time.time)
    result_hash: str = None
