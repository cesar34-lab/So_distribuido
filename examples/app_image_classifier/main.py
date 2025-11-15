import numpy as np
import pickle
import time
import random

from Libs import SODClient
from Libs.ml import MLP
from Libs.ml.base import BaseEstimator


# --- Simulación de Dataset ---
def generate_dataset(n_samples=1000):
    """Genera un dataset sintético de 28x28 imágenes binarias (0-1) para clasificación binaria."""
    X = np.random.rand(n_samples, 28*28).astype(np.float32)
    # Etiquetas: si la media de la imagen > 0.5, es 1, sino 0
    y = (np.mean(X, axis=1) > 0.5).astype(int).reshape(-1, 1)
    return X, y

def split_dataset(X, y, n_parts=3):
    """Divide el dataset en n_parts partes."""
    indices = np.random.permutation(len(X))
    split_points = np.array_split(indices, n_parts)
    datasets = []
    for part in split_points:
        X_part = X[part]
        y_part = y[part]
        datasets.append((X_part, y_part))
    return datasets

# --- Inicialización ---
print("[APP] Inicializando cliente SOD...")
client = SODClient(scheduler_agent=None, store_agent=None)  # En el simulador, esto se inyecta
# En la práctica real, se inyectarían las instancias reales de Scheduler-D y Store-D

# Generar dataset
print("[APP] Generando dataset sintético...")
X, y = generate_dataset(1000)
datasets = split_dataset(X, y, 3)

# Guardar datasets en Store-D
print("[APP] Almacenando datasets en Store-D...")
dataset_hashes = []
for i, (X_part, y_part) in enumerate(datasets):
    data_bytes = pickle.dumps((X_part, y_part))
    h = client.store_put(data_bytes)
    dataset_hashes.append(h)
    print(f"[APP] Dataset {i+1} almacenado con hash: {h}")

# Crear y guardar modelo global inicial
print("[APP] Creando modelo MLP global inicial...")
model_global = MLP(layers=[784, 128, 64, 10], lr=0.01, epochs=10, batch_size=16)
model_bytes = pickle.dumps(model_global)
model_global_hash = client.store_put(model_bytes)
print(f"[APP] Modelo global inicial almacenado con hash: {model_global_hash}")

# Enviar tareas de entrenamiento
print("[APP] Enviando 3 tareas de entrenamiento distribuido...")
task_ids = []
for i, dataset_hash in enumerate(dataset_hashes):
    task_spec = {
        "task_id": f"train_{i}",
        "model_hash": model_global_hash,  # Modelo global a cargar
        "dataset_hash": dataset_hash,     # Dataset local para entrenar
        "resources": {"cpu_mips": 700, "ram_mb": 512},
        "tags": [],
        "checkpoint_interval": 0
    }
    task_id = client.submit_task(
        binary_hash_or_callable=model_global_hash,  # El binario a ejecutar es el modelo (serializado)
        resources=task_spec["resources"],
        tags=task_spec["tags"],
        checkpoint_interval=task_spec["checkpoint_interval"]
    )
    task_ids.append(task_id)
    print(f"[APP] Tarea {i+1} enviada con ID: {task_id}")

# Esperar a que todas las tareas terminen
print("[APP] Esperando a que las tareas terminen...")
final_model_hashes = []
for task_id in task_ids:
    status = client.get_task_status(task_id)
    while status not in ["COMPLETED", "FAILED"]:
        time.sleep(2)
        status = client.get_task_status(task_id)
        print(f"[APP] Estado de {task_id}: {status}")
    if status == "COMPLETED":
        # El Scheduler-D debe haber guardado el modelo entrenado en Store-D
        # El hash del modelo final debe ser reportado por el scheduler, pero por simplicidad,
        # asumiremos que el hash es "model_final_<task_id>"
        final_model_hash = f"model_final_{task_id}"
        final_model_hashes.append(final_model_hash)
        print(f"[APP] Tarea {task_id} completada. Modelo final guardado con hash: {final_model_hash}")
    else:
        print(f"[APP] Tarea {task_id} falló. Abortando.")
        exit(1)

# Promediar los modelos
print("[APP] Recuperando modelos entrenados y promediando...")
final_weights = []
final_biases = []

for model_hash in final_model_hashes:
    model_bytes = client.store_get(model_hash)
    if model_bytes is None:
        print(f"[APP] Error: No se pudo recuperar el modelo {model_hash}.")
        exit(1)
    trained_model = pickle.loads(model_bytes)
    final_weights.append(trained_model.weights)
    final_biases.append(trained_model.biases)

# Promediar pesos y bias
avg_weights = [np.mean(np.array([w[i] for w in final_weights]), axis=0) for i in range(len(final_weights[0]))]
avg_biases = [np.mean(np.array([b[i] for b in final_biases]), axis=0) for i in range(len(final_biases[0]))]

# Crear nuevo modelo global promediado
model_avg = MLP(layers=[784, 128, 64, 10], lr=0.01, epochs=10, batch_size=16)
model_avg.weights = avg_weights
model_avg.biases = avg_biases

# Guardar el modelo promediado
model_avg_bytes = pickle.dumps(model_avg)
model_avg_hash = client.store_put(model_avg_bytes)
print(f"[APP] Modelo global promediado guardado con hash: {model_avg_hash}")

# Evaluar en dataset de prueba
print("[APP] Evaluando modelo promediado...")
X_test, y_test = generate_dataset(200)
y_pred = model_avg.predict(X_test)
y_pred_rounded = (y_pred > 0.5).astype(int)
accuracy = np.mean(y_pred_rounded == y_test)
print(f"[APP] Precisión final del modelo promediado: {accuracy:.4f}")

print("[APP] ¡Entrenamiento distribuido completado exitosamente!")