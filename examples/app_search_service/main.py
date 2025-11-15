# examples/app_search_service/main.py


import pickle
import time

from Libs import SODClient

# Simulación de tabla de etiquetas por nodo (en un sistema real, sería una DHT)
# En este ejemplo, cada nodo tiene una copia de esta tabla
node_tables = {
    "nodeA": {"hash1": ["python", "code"], "hash2": ["ai", "machine"]},
    "nodeB": {"hash3": ["python", "data"], "hash4": ["ai", "deep"]},
    "nodeC": {"hash5": ["python", "web"], "hash6": ["data", "analysis"]}
}

print("[APP] Inicializando cliente de búsqueda...")
client = SODClient(scheduler_agent=None, store_agent=None)

# Simulación: el cliente envía una tarea de búsqueda
query = "python"
print(f"[APP] Buscando documentos con la etiqueta: '{query}'...")

# Enviar tarea de búsqueda
task_spec = {
    "task_id": "search_1",
    "query": query,
    "k": 5,
    "resources": {"cpu_mips": 100, "ram_mb": 128},
    "tags": [],
    "checkpoint_interval": 0
}

task_id = client.submit_task(
    binary_hash_or_callable="search_service",  # Un binario que implementa la lógica de búsqueda
    resources=task_spec["resources"],
    tags=task_spec["tags"],
    checkpoint_interval=task_spec["checkpoint_interval"]
)

print(f"[APP] Tarea de búsqueda enviada con ID: {task_id}")

# Esperar a que termine
status = client.get_task_status(task_id)
while status not in ["COMPLETED", "FAILED"]:
    time.sleep(1)
    status = client.get_task_status(task_id)
    print(f"[APP] Estado de búsqueda: {status}")

if status == "COMPLETED":
    # El resultado de la tarea es un hash que apunta a los resultados
    result_hash = client.get_task_result_hash(task_id)
    if result_hash:
        result_bytes = client.store_get(result_hash)
        if result_bytes:
            results = pickle.loads(result_bytes)
            print(f"[APP] Resultados encontrados: {len(results)} documentos")
            for doc_hash in results:
                print(f"  - Hash: {doc_hash}")
                # Recuperar el documento
                doc_bytes = client.store_get(doc_hash)
                if doc_bytes:
                    doc_content = doc_bytes.decode('utf-8')
                    print(f"    Contenido: {doc_content[:50]}...")
        else:
            print("[APP] No se pudo recuperar los resultados de la búsqueda.")
    else:
        print("[APP] El Scheduler-D no reportó un hash de resultados.")
else:
    print("[APP] La búsqueda falló.")

print("[APP] Búsqueda completada.")