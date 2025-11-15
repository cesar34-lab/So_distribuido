# libs/sod_api/client.py

import uuid
import time
from typing import Dict, List, Any, Optional, Union
import asyncio
# NOTA: En el simulador, asumiremos que tenemos acceso directo a los agentes
# o a una cola/mecanismo para comunicarnos con ellos.
# En el kernel físico, esto sería una syscall hacia el microkernel.
# Aquí, para el simulador, inyectaremos los agentes como dependencias.

# Supongamos que tenemos interfaces o instancias de los agentes a los que llamar
# Estos serían pasados al constructor o accesibles globalmente en el simulador.
# from agents.scheduler_d.scheduler import SchedulerD
# from agents.store_d.store import StoreD

class SODClient:
    def __init__(self, scheduler_agent, store_agent, node_id: str = "api_client"):
        """
        Inicializa el cliente de la API de SOD.

        Args:
            scheduler_agent: Instancia del Scheduler-D para enviar tareas.
            store_agent: Instancia del Store-D para almacenar/recuperar datos.
            node_id (str): ID del nodo cliente (opcional para simulador).
        """
        self.node_id = node_id
        self.scheduler_agent = scheduler_agent
        self.store_agent = store_agent
        # Simular una cola de resultados pendientes o un mecanismo para rastrear tareas
        self.task_results: Dict[str, Any] = {}
        self.task_statuses: Dict[str, str] = {}

    def submit_task(self, binary_hash_or_callable, resources: Dict, tags: List[str], checkpoint_interval: int = 0) -> str:
        """
        Envía una tarea para su ejecución distribuida.

        Args:
            binary_hash_or_callable: Hash del binario en Store-D o un objeto callable (simulado).
            resources (Dict): Requisitos de recursos (e.g., {"cpu_mips": 700, "ram_mb": 512}).
            tags (List[str]): Etiquetas para el nodo ejecutor (e.g., ["gpu"]).
            checkpoint_interval (int): Frecuencia de checkpointing (en epochs o pasos).

        Returns:
            str: ID único de la tarea.
        """
        task_id = str(uuid.uuid4())
        print(f"[SODClient] Enviando tarea {task_id} para ejecución...")

        # En el simulador, pasamos directamente el 'callable' o el hash al Scheduler-D
        # En el kernel físico, se enviaría un mensaje IPC al microkernel, que lo reenviaría al Scheduler-D.
        # El Scheduler-D recibiría un mensaje como:
        # { "type": "SUBMIT_TASK", "task_id": "...", "binary_hash": "...", "resources": {...}, ... }
        # Para el simulador, llamamos directamente al método del agente.
        task_spec = {
            "task_id": task_id,
            "binary_hash": binary_hash_or_callable if isinstance(binary_hash_or_callable, str) else None,
            # Si es callable, el scheduler lo manejaría de forma especial o lo almacenaría previamente
            "callable_code": binary_hash_or_callable if callable(binary_hash_or_callable) else None,
            "resources": resources,
            "tags": tags,
            "checkpoint_interval": checkpoint_interval
        }

        # Simular la interacción con el Scheduler-D
        # Supongamos que el scheduler tiene un método para recibir tareas directamente
        # y que maneja la lógica de descubrimiento, negociación y asignación.
        # El scheduler retornará el task_id si la solicitud es aceptada.
        assigned_task_id = self.scheduler_agent.submit_task_from_api(task_spec)
        if assigned_task_id:
            self.task_statuses[task_id] = "SUBMITTED"
            print(f"[SODClient] Tarea {task_id} aceptada por el Scheduler-D.")
            return task_id
        else:
            print(f"[SODClient] Error: El Scheduler-D rechazó la tarea {task_id}.")
            return "" # O lanzar una excepción


    def get_task_status(self, task_id: str) -> str:
        """
        Consulta el estado actual de una tarea.

        Args:
            task_id (str): ID de la tarea.

        Returns:
            str: Estado de la tarea (e.g., "SUBMITTED", "RUNNING", "COMPLETED", "FAILED").
        """
        # En el simulador, el Scheduler-D puede actualizar un diccionario global o el cliente puede consultarle.
        # Supongamos que el Scheduler-D mantiene un estado y el cliente puede preguntarle.
        # Opcionalmente, el cliente puede mantener un caché local actualizado.
        status = self.scheduler_agent.get_task_status(task_id)
        if status:
            self.task_statuses[task_id] = status
        return status or self.task_statuses.get(task_id, "UNKNOWN")


    def fetch_result(self, task_id: str) -> Optional[Any]:
        """
        Espera a que la tarea termine y recupera su resultado.

        Args:
            task_id (str): ID de la tarea.

        Returns:
            Any: El resultado de la tarea o None si falla o no termina.
        """
        print(f"[SODClient] Esperando resultado de la tarea {task_id}...")
        while True:
            status = self.get_task_status(task_id)
            if status == "COMPLETED":
                print(f"[SODClient] Tarea {task_id} completada. Recuperando resultado...")
                # El Scheduler-D debería haber almacenado el resultado en Store-D y registrado el hash del resultado
                result_hash = self.scheduler_agent.get_task_result_hash(task_id)
                if result_hash:
                    # Recuperar el resultado del Store-D
                    result_data = self.store_agent.get(result_hash)
                    if result_data is not None:
                        print(f"[SODClient] Resultado de la tarea {task_id} recuperado.")
                        # Opcional: deserializar result_data si es necesario
                        return result_data
                    else:
                        print(f"[SODClient] Error: No se pudo recuperar el resultado con hash {result_hash} de la tarea {task_id}.")
                        return None
                else:
                    print(f"[SODClient] Error: El Scheduler-D no reportó un hash de resultado para la tarea {task_id}.")
                    return None
            elif status == "FAILED":
                print(f"[SODClient] Tarea {task_id} falló.")
                return None
            # Opcional: manejar otros estados como "MIGRATING"
            time.sleep(1) # Esperar 1 segundo antes de volver a preguntar


    def store_put(self, data: bytes) -> str:
        """
        Almacena datos en el sistema de almacenamiento distribuido.

        Args:
            data (bytes): Los datos a almacenar.

        Returns:
            str: Hash SHA256 del objeto almacenado.
        """
        print(f"[SODClient] Almacenando datos en Store-D...")
        # Llamar directamente al Store-D en el simulador
        obj_hash = self.store_agent.put(data)
        print(f"[SODClient] Datos almacenados con hash: {obj_hash}")
        return obj_hash


    def store_get(self, obj_hash: str) -> Optional[bytes]:
        """
        Recupera datos del sistema de almacenamiento distribuido.

        Args:
            obj_hash (str): Hash del objeto a recuperar.

        Returns:
            bytes: Los datos recuperados o None si no se encuentran.
        """
        print(f"[SODClient] Recuperando datos con hash {obj_hash} de Store-D...")
        # Llamar directamente al Store-D en el simulador
        data = self.store_agent.get(obj_hash)
        if data is not None:
            print(f"[SODClient] Datos con hash {obj_hash} recuperados.")
        else:
            print(f"[SODClient] Datos con hash {obj_hash} no encontrados.")
        return data
