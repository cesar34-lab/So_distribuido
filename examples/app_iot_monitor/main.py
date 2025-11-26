# examples/app_iot_monitor/main.py
import threading
import time
import random
import json
from Libs.sod_api import SODClient
# Simulamos que el cliente puede iniciar tareas y leer resultados
client = SODClient(scheduler_agent=None, store_agent=None)

# --- Simulación de Sensor ---
def sensor_simulator(node_id, num_reads=10):
    """Simula un nodo IoT que envía datos de temperatura."""
    for i in range(num_reads):
        temp = random.uniform(15, 35)
        data = {
            "node_id": node_id,
            "timestamp": int(time.time()),
            "temperature": temp,
            "humidity": random.uniform(30, 80)
        }
        data_bytes = json.dumps(data).encode('utf-8')
        data_hash = client.store_put(data_bytes)
        print(f"[SENSOR {node_id}] Enviado dato: {temp:.2f}°C (hash: {data_hash[:8]}...)")
        time.sleep(5)

# --- Simulación de Analizador ---
def alert_analyzer():
    """Analiza los últimos datos y detecta anomalías."""
    print("[ANALIZADOR] Iniciando análisis de alertas...")
    window_size = 10
    threshold = 2.0  # 2 desviaciones estándar

    while True:
        # Recuperar los últimos N datos (simulación: todos los datos en Store-D)
        # En un sistema real, usarías una DHT o un índice
        # Aquí, asumimos que puedes listar todos los hashes
        # Para simplificar, simulamos que hay 10 datos
        # En la práctica, deberías tener un mecanismo de registro de hashes
        # Por ahora, simulamos con un conjunto de datos conocidos
        # Esto es un hack, pero sirve para demostrar el concepto.
        # En un sistema real, tendrías una tabla de "últimos datos" por nodo.
        # Por simplicidad, asumimos que el analizador tiene acceso a los últimos 10 hashes.
        # Este es un punto donde el sistema real necesitaría una DHT o una tabla de índices.
        # Para este ejemplo, generamos datos simulados.
        data_hashes = [f"temp_{i}" for i in range(1, 11)]
        temperatures = []
        for h in data_hashes:
            # Simulación de recuperación
            temp = random.uniform(15, 35)
            temperatures.append(temp)
        mean = sum(temperatures) / len(temperatures)
        std = (sum((x - mean) ** 2 for x in temperatures) / len(temperatures)) ** 0.5

        # Simular un nuevo dato
        new_temp = random.uniform(15, 35)
        if abs(new_temp - mean) > threshold * std:
            alert = {
                "timestamp": int(time.time()),
                "message": f"ALERTA: Temperatura anómala {new_temp:.2f}°C (media: {mean:.2f}, std: {std:.2f})",
                "value": new_temp,
                "mean": mean,
                "std": std
            }
            alert_bytes = json.dumps(alert).encode('utf-8')
            alert_hash = client.store_put(alert_bytes)
            print(f"[ANALIZADOR] 🔴 ALERTA GENERADA! Hash: {alert_hash[:8]}...")
        else:
            print(f"[ANALIZADOR] ✅ Temperatura normal: {new_temp:.2f}°C")
        time.sleep(10)

# --- Ejecución ---
print("[APP] Iniciando Aplicación de Monitoreo IoT Distribuido...")

# Iniciar 3 simuladores de sensores
threads = []
for i in range(3):
    t = threading.Thread(target=sensor_simulator, args=(f"node{i+1}", 5))
    threads.append(t)
    t.start()

# Iniciar el analizador de alertas
analyzer_thread = threading.Thread(target=alert_analyzer)
analyzer_thread.start()

# Mantener la aplicación viva
try:
    while True:
        time.sleep(1)
except KeyboardInterrupt:
    print("\n[APP] Aplicación detenida por el usuario.")
