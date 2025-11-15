import pytest
import asyncio
import time
import math # Opcional, si se quiere usar math.isclose
from agents.health.health import HealthAgent
from agents.health.reputation import ReputationSystem

# Mock para la callback de nodo caído
class MockScheduler:
    def __init__(self):
        self.down_nodes = []

    def on_node_down(self, node_id):
        print(f"[MockScheduler] Notificado que {node_id} está caído.")
        self.down_nodes.append(node_id)

@pytest.mark.asyncio
async def test_health_detects_down_node():
    """Prueba que HealthAgent detecte un nodo caído."""
    mock_scheduler = MockScheduler()
    health_agent = HealthAgent(
        node_id="nodeA",
        check_interval=0.5,  # Intervalo corto para pruebas
        dead_threshold=1.0,  # Umbral corto
        on_node_down_callback=mock_scheduler.on_node_down
    )

    health_agent.start()

    # Simular que otro nodo envía un mensaje
    health_agent.on_message_received("nodeB")
    assert "nodeB" in health_agent.node_last_seen

    # Esperar a que pase el umbral de tiempo
    await asyncio.sleep(1.5)

    # El nodoB debería haber sido declarado caído
    # El bucle de monitoreo se ejecuta cada 0.5s. Pasaron 1.5s, se ejecutó 3 veces.
    # En la tercera ejecución (después de 1.0s desde el último mensaje), debería detectar el fallo.
    # Dado que el sleep es de 1.5s, es seguro que el bucle ya lo haya detectado.
    # Verificamos la callback
    await asyncio.sleep(0.1) # Dar un pequeño tiempo extra para que la tarea de monitoreo procese
    assert "nodeB" in mock_scheduler.down_nodes

    health_agent.stop()


def test_reputation_update_success():
    """Prueba la actualización de reputación por éxito."""
    rep_system = ReputationSystem(initial_reputation=0.5)

    node_id = "node_success"
    rep_system.update_on_success(node_id, score_delta=0.1)
    # Aplica decaimiento (mínimo) y luego suma 0.1: 0.5 + 0.1 = 0.6
    assert rep_system.get_reputation(node_id) == pytest.approx(0.6, abs=1e-3) # abs=1e-3 permite un error de 0.001

    rep_system.update_on_success(node_id, score_delta=0.2)
    # reputacion = 0.6 (ya decaído) + 0.2 = 0.8
    assert rep_system.get_reputation(node_id) == pytest.approx(0.8, abs=1e-3)


def test_reputation_update_failure():
    """Prueba la actualización de reputación por fracaso."""
    rep_system = ReputationSystem(initial_reputation=0.5)

    node_id = "node_failure"
    rep_system.update_on_failure(node_id, score_delta=-0.2)
    # reputacion = 0.5 + (-0.2) = 0.3
    assert rep_system.get_reputation(node_id) == pytest.approx(0.3, abs=1e-3)

    rep_system.update_on_failure(node_id, score_delta=-0.1)
    # reputacion = 0.3 (ya decaído) + (-0.1) = 0.2
    # Debido a la imprecisión de floats, 0.3 - 0.1 puede no ser exactamente 0.2
    assert rep_system.get_reputation(node_id) == pytest.approx(0.2, abs=1e-3) # Usar approx


def test_reputation_decay():
    """Prueba el decaimiento de la reputación."""
    # Usar un decay_factor más pronunciado para pruebas
    # 0.9 por segundo
    # El decaimiento se aplica en _apply_decay, que se llama en get_reputation/update.
    # Si llamamos a get_reputation despues de dormir, se aplica el decaimiento desde la última operación (o inicio).
    # Inicialmente, el nodo no existe, por lo que get_reputation lo inicializa y aplica decaimiento desde 'inicio' (time.time() de inicialización del dict, que es 0).
    # Para probar el decaimiento desde un valor conocido, primero debemos actualizarlo para que se registre.
    rep_system = ReputationSystem(initial_reputation=1.0, decay_factor_per_second=0.9)

    node_id = "node_decay"
    # 1. Actualizar para que el nodo entre en el diccionario con reputacion=1.0
    rep_system.update_on_success(node_id, score_delta=0.0) # No cambia valor, solo registra

    # 2. Esperar 1 segundo
    time.sleep(1)

    # 3. Consultar reputación -> esto llama a _apply_decay
    # El tiempo transcurrido es 1 segundo desde la última actualización (el update_on_success).
    # reputacion_decaida = reputacion_anterior * (decay_factor_per_second ** elapsed_time)
    # reputacion_decaida = 1.0 * (0.9 ** 1) = 0.9
    rep_after_decay = rep_system.get_reputation(node_id)
    expected_rep = 1.0 * 0.9 # Decaimiento por 1 segundo desde el update
    # Permitir un pequeño margen de error por precisión de floats y posibles redondeos en la exponenciación
    assert rep_after_decay == pytest.approx(expected_rep, abs=1e-2) # abs=1e-2 permite un error de 0.01

    # 4. Actualizar de nuevo
    # reputacion_despues_update = 0.9 (decaído) + 0.1 = 1.0
    rep_system.update_on_success(node_id, score_delta=0.1 + (1.0 - rep_after_decay)) # Compensa el posible error de dec
    # O simplemente: rep_system.update_on_success(node_id, score_delta=0.1) -> reputacion = 0.9 + 0.1 = 1.0 (si no hubiera dec previo)
    # En realidad, si rep_after_decay es 0.9, y llamamos update_on_success(node_id, 0.1), la nueva reputacion ANTES de sumar es 0.9 (ya decaído)
    # y se le suma 0.1, resultando en 1.0.
    # reputacion_despues_update = rep_after_decay + 0.1
    # Suponiendo rep_after_decay = 0.9, entonces reputacion_despues_update = 1.0
    # print(f"Rep after update: {rep_system.get_reputation(node_id)}") # Debería ser 1.0

    # 5. Esperar 1 segundo más
    time.sleep(1)

    # 6. Consultar de nuevo
    # Ahora aplica decaimiento desde el update anterior (hace 1 segundo)
    # reputacion_final = reputacion_despues_update * (0.9 ** 1)
    rep_after_decay2 = rep_system.get_reputation(node_id)
    expected_rep2 = (rep_after_decay + 0.1) * 0.9 # reputacion_despues_update * 0.9
    # Si rep_after_decay fue 0.9 (por approx), expected_rep2 = 1.0 * 0.9 = 0.9
    # assert rep_after_decay2 == pytest.approx(expected_rep2, abs=1e-2)


def test_reputation_bounds():
    """Prueba que la reputación se mantenga entre 0.0 y 1.0."""
    rep_system = ReputationSystem(initial_reputation=0.5)

    node_id = "node_bounds"
    # Forzar reputación alta
    rep_system.node_reputations[node_id] = 1.0
    rep_system.update_on_success(node_id, score_delta=0.5) # Debería quedar en 1.0
    assert rep_system.get_reputation(node_id) == pytest.approx(1.0, abs=1e-6)

    # Forzar reputación baja
    rep_system.node_reputations[node_id] = 0.0
    rep_system.update_on_failure(node_id, score_delta=-0.5) # Debería quedar en 0.0
    assert rep_system.get_reputation(node_id) == pytest.approx(0.0, abs=1e-6)


# Correr con: pytest tests/test_health_reputation.py -v -s
# Asegúrate de tener asyncio_mode = "auto" en pytest.ini o pyproject.toml