# API de Alto Nivel para SOD (libs/sod_api)

## Instalación

TBD (Depende de cómo se empaquete la librería).

## Uso Básico

### Inicializar el Cliente

```python
from libs.sod_api import SODClient

# En el simulador, necesitas inyectar las instancias de los agentes
# Supongamos que tienes instancias scheduler_d_instance y store_d_instance
client = SODClient(scheduler_agent=scheduler_d_instance, store_agent=store_d_instance)

```
# Supongamos que tienes un modelo serializado o un hash de un binario
# y los datos de entrenamiento ya almacenados
model_hash = client.store_put(serialized_model_bytes)
data_hash = client.store_put(training_data_bytes)

# Definir recursos y etiquetas
```
resources = {"cpu_mips": 700, "ram_mb": 512}
tags = ["gpu"] # Nodo con GPU disponible
```

# Enviar la tarea
```
task_id = client.submit_task(
    binary_hash_or_callable=model_hash, # Hash del modelo a ejecutar
    resources=resources,
    tags=tags,
    checkpoint_interval=5 # Guardar checkpoint cada 5 epochs
)

print(f"Tarea enviada con ID: {task_id}")
```
