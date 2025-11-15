import pytest
from unittest.mock import Mock, patch

from Libs import SODClient


# Mock más inteligente para Store
class MockStoreAgent:
    def __init__(self):
        self.storage = {} # Simula el almacenamiento interno

    def put(self, data: bytes) -> str:
        # Simula generar un hash único para los datos
        # En la práctica real, sería SHA256(data)
        # Para el test, usamos un hash fijo o un contador
        # Usaremos un hash simple para simular unicidad
        import hashlib
        obj_hash = hashlib.sha256(data).hexdigest()[:16] # Tomar los primeros 16 chars para simplificar
        self.storage[obj_hash] = data
        print(f"[MockStoreAgent] Almacenado {obj_hash}: {data}")
        return obj_hash

    def get(self, obj_hash: str) -> bytes:
        data = self.storage.get(obj_hash)
        print(f"[MockStoreAgent] Recuperado {obj_hash}: {data}")
        return data


# Mock para Scheduler
class MockSchedulerAgent:
    def __init__(self):
        self.submitted_tasks = {}
        self.task_statuses = {}
        self.task_results = {}

    def submit_task_from_api(self, task_spec: dict) -> str:
        task_id = task_spec.get("task_id")
        if task_id:
            self.submitted_tasks[task_id] = task_spec
            self.task_statuses[task_id] = "SUBMITTED" # Simular estado inicial
            print(f"[MockSchedulerAgent] Tarea recibida: {task_id}")
            return task_id # Devuelve el ID que recibió
        return ""

    def get_task_status(self, task_id: str) -> str:
        status = self.task_statuses.get(task_id, "UNKNOWN")
        print(f"[MockSchedulerAgent] Estado de {task_id}: {status}")
        return status

    def get_task_result_hash(self, task_id: str) -> str:
        # Simular que el resultado se almacena en Store-D con un hash
        # En un escenario real, el scheduler lo sabe porque el ejecutor lo reportó
        # y lo almacenó.
        # Para el test, devolvemos un hash fijo o lo generamos basado en task_id
        result_hash = f"result_hash_for_{task_id}"
        self.task_results[task_id] = result_hash
        print(f"[MockSchedulerAgent] Result hash para {task_id}: {result_hash}")
        return result_hash


@pytest.fixture
def mock_scheduler_agent():
    return MockSchedulerAgent()

@pytest.fixture
def mock_store_agent():
    return MockStoreAgent()

def test_submit_task(mock_scheduler_agent, mock_store_agent):
    """Prueba la función submit_task."""
    client = SODClient(scheduler_agent=mock_scheduler_agent, store_agent=mock_store_agent)

    task_id = client.submit_task(
        binary_hash_or_callable="some_hash",
        resources={"cpu_mips": 700},
        tags=["gpu"],
        checkpoint_interval=10
    )
    # El task_id ahora es el generado por uuid.uuid4() dentro de SODClient
    # Verificamos que no sea vacío y que el scheduler haya recibido la tarea
    assert task_id != ""
    assert task_id in mock_scheduler_agent.submitted_tasks
    # Opcional: verificar que el task_spec enviado al scheduler contenga los datos correctos
    submitted_spec = mock_scheduler_agent.submitted_tasks[task_id]
    assert submitted_spec["binary_hash"] == "some_hash"
    assert submitted_spec["resources"] == {"cpu_mips": 700}
    assert submitted_spec["tags"] == ["gpu"]
    assert submitted_spec["checkpoint_interval"] == 10
    print(f"[Test] Task ID generado y enviado: {task_id}")


def test_fetch_result(mock_scheduler_agent, mock_store_agent):
    """Prueba la función fetch_result."""
    client = SODClient(scheduler_agent=mock_scheduler_agent, store_agent=mock_store_agent)

    task_id = "task_123"
    # Simular que el scheduler ya tiene la tarea y su estado es COMPLETED
    # y que el resultado está almacenado en el mock_store_agent
    mock_scheduler_agent.submitted_tasks[task_id] = {"task_id": task_id}
    mock_scheduler_agent.task_statuses[task_id] = "COMPLETED"
    result_hash = "result_hash_for_task_123"
    mock_scheduler_agent.task_results[task_id] = result_hash
    # Almacenar el resultado real en el mock_store_agent
    result_data = b"real_result_data_from_task"
    mock_store_agent.storage[result_hash] = result_data

    retrieved_result = client.fetch_result(task_id)
    assert retrieved_result == result_data


def test_store_put_get(mock_scheduler_agent, mock_store_agent):
    """Prueba las funciones store_put y store_get."""
    client = SODClient(scheduler_agent=mock_scheduler_agent, store_agent=mock_store_agent)

    data_to_store = b"test_data"
    stored_hash = client.store_put(data_to_store)
    # El hash se genera en el mock_store_agent, verifiquemos que no sea vacío
    assert stored_hash != ""

    retrieved_data = client.store_get(stored_hash)
    assert retrieved_data == data_to_store # Ahora debería coincidir

# Correr con: pytest tests/test_sod_api.py -v -s
# Asegúrate de tener asyncio_mode = "auto" en pytest.ini o pyproject.toml si se usan async