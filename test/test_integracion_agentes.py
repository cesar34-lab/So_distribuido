# test/test_integracion_agentes.py

import asyncio
import pytest
import tempfile
import time
from pathlib import Path

# Ajusta las rutas de importación según tu estructura
# Asegúrate de estar ejecutando pytest desde la carpeta So_distribuido/
from agents.net.net_agent import NetAgent
from agents.discover.main import DiscoverAgent
from agents.health.health import HealthAgent
from agents.store_d.store import StoreD
from agents.scheduler_d.scheduler import SchedulerD
from Libs.sod_api.client import SODClient


# --- Test NetAgent ---
@pytest.mark.asyncio
async def test_net_agent_creacion():
    """Prueba que NetAgent se crea correctamente."""
    node_id = "test_node_1"
    port = 11000
    net_agent = NetAgent(node_id=node_id, listen_host='127.0.0.1', listen_port=port)
    assert net_agent.node_id == node_id
    assert net_agent.port == port
    assert node_id in net_agent.known_nodes
    assert node_id in net_agent.node_id_to_addr
    await net_agent.stop() # Limpiar


@pytest.mark.asyncio
async def test_net_agent_registro_handler():
    """Prueba que se puede registrar un handler en NetAgent."""
    received_messages = []
    def dummy_handler(msg, addr):
        received_messages.append((msg, addr))

    node_id = "test_node_2"
    port = 11001
    net_agent = NetAgent(node_id=node_id, listen_host='127.0.0.1', listen_port=port)
    net_agent.add_handler(dummy_handler)

    # Simular envío interno (esto no es envío real por red, sino una llamada directa para probar el registro)
    test_msg = {"type": "TEST", "src": "other", "dst": node_id, "payload": {"data": "test"}}
    test_addr = ('127.0.0.1', 12345)
    # Llamar manualmente al handler para verificar que se registró
    # Esto no prueba la red, sino que el handler está en la lista
    assert dummy_handler in net_agent.handlers
    await net_agent.stop()


# --- Test DiscoverAgent con NetAgent ---
@pytest.mark.asyncio
async def test_discover_agent_creacion_con_net():
    """Prueba que DiscoverAgent se crea correctamente con NetAgent."""
    node_id = "test_disc_node_1"
    port = 11002
    peers = [('127.0.0.1', 11003)] # Peer simulado

    net_agent = NetAgent(node_id=node_id, listen_host='127.0.0.1', listen_port=port)
    discover_agent = DiscoverAgent(node_id=node_id, net_agent=net_agent, peers=peers)

    # Verificar que DiscoverAgent se registró como handler
    assert discover_agent.on_net_message in net_agent.handlers
    await net_agent.stop()


# --- Test StoreD con NetAgent ---
@pytest.mark.asyncio
async def test_store_d_creacion_con_net():
    """Prueba que StoreD se crea correctamente con NetAgent."""
    node_id = "test_store_node_1"
    port = 11004

    net_agent = NetAgent(node_id=node_id, listen_host='127.0.0.1', listen_port=port)
    with tempfile.TemporaryDirectory() as temp_dir:
        store_agent = StoreD(node_id=node_id, net_agent=net_agent, storage_dir=temp_dir)

        # Verificar que StoreD se registró como handler
        # Nota: El handler de StoreD es una función asíncrona, por lo que no se puede comparar directamente
        # Podemos verificar que tiene un handler registrado
        assert len(net_agent.handlers) >= 1 # Debe haber al menos 1 handler (el de StoreD)
        await net_agent.stop()


@pytest.mark.asyncio
async def test_store_d_put_get_local():
    """Prueba que StoreD pueda almacenar y recuperar localmente."""
    node_id = "test_store_node_2"
    port = 11005

    net_agent = NetAgent(node_id=node_id, listen_host='127.0.0.1', listen_port=port)
    with tempfile.TemporaryDirectory() as temp_dir:
        store_agent = StoreD(node_id=node_id, net_agent=net_agent, storage_dir=temp_dir)

        test_data = b"test data for store"
        obj_hash = store_agent.put(test_data)

        # --- CORRECCIÓN: await store_agent.get(...) ---
        retrieved_data = await store_agent.get(obj_hash) # <--- Añadido 'await'
        assert retrieved_data == test_data

        await net_agent.stop()


# --- Test SchedulerD con DiscoverAgent y StoreD ---
@pytest.mark.asyncio
async def test_scheduler_d_creacion():
    """Prueba que SchedulerD se crea correctamente con DiscoverAgent, StoreD y NetAgent."""
    node_id = "test_sched_node_1"
    port = 11006

    net_agent = NetAgent(node_id=node_id, listen_host='127.0.0.1', listen_port=port)

    # Creamos agentes dummy para pasarlos al SchedulerD
    # En un test real, DiscoverAgent y StoreD también necesitarían NetAgent
    # Para simplificar, creamos sus dependencias también
    discover_agent = DiscoverAgent(node_id=node_id, net_agent=net_agent, peers=[])
    with tempfile.TemporaryDirectory() as temp_dir:
        store_agent = StoreD(node_id=node_id, net_agent=net_agent, storage_dir=temp_dir)

        scheduler_agent = SchedulerD(discover_agent=discover_agent, store_agent=store_agent, net_agent=net_agent)

        # Verificar que SchedulerD tiene las referencias correctas
        assert scheduler_agent.discover_agent == discover_agent
        assert scheduler_agent.store_agent == store_agent
        assert scheduler_agent.net_agent == net_agent

        await net_agent.stop()


# --- Test SODClient con agentes integrados ---
@pytest.mark.asyncio
async def test_sod_client_creacion():
    """Prueba que SODClient se crea correctamente con agentes integrados."""
    node_id = "test_client_node_1"
    port = 11007

    net_agent = NetAgent(node_id=node_id, listen_host='127.0.0.1', listen_port=port)
    discover_agent = DiscoverAgent(node_id=node_id, net_agent=net_agent, peers=[])
    with tempfile.TemporaryDirectory() as temp_dir:
        store_agent = StoreD(node_id=node_id, net_agent=net_agent, storage_dir=temp_dir)
        scheduler_agent = SchedulerD(discover_agent=discover_agent, store_agent=store_agent, net_agent=net_agent)

        client = SODClient(scheduler_agent=scheduler_agent, store_agent=store_agent, node_id=f"{node_id}_client")

        assert client.scheduler_agent == scheduler_agent
        assert client.store_agent == store_agent

        await net_agent.stop()


# --- Test de comunicación básica entre dos NetAgents (Simulación simple) ---
@pytest.mark.asyncio
async def test_comunicacion_entre_net_agents():
    """Prueba la comunicación básica entre dos instancias de NetAgent."""
    node1_id = "node1"
    port1 = 12001
    node2_id = "node2"
    port2 = 12002

    net_agent1 = NetAgent(node_id=node1_id, listen_host='127.0.0.1', listen_port=port1)
    net_agent2 = NetAgent(node_id=node2_id, listen_host='127.0.0.1', listen_port=port2)

    received_messages_node1 = []
    received_messages_node2 = []

    def handler1(msg, addr):
        received_messages_node1.append((msg, addr))

    def handler2(msg, addr):
        received_messages_node2.append((msg, addr))

    net_agent1.add_handler(handler1)
    net_agent2.add_handler(handler2)

    await net_agent1.start()
    await net_agent2.start()

    # Hacer que NetAgent2 conozca la dirección de NetAgent1
    net_agent2.update_node_addr(node1_id, ('127.0.0.1', port1))

    # Enviar un mensaje de node2 a node1
    msg_payload = {"test_key": "test_value"}
    await net_agent2.send_to_node_id(node1_id, "TEST_MSG", msg_payload, reliable=False)

    # Esperar un poco para que el mensaje sea procesado
    await asyncio.sleep(0.1)

    # Verificar que node1 recibió el mensaje
    assert len(received_messages_node1) == 1
    msg_received, addr_received = received_messages_node1[0]
    assert msg_received['type'] == 'TEST_MSG'
    assert msg_received['payload'] == msg_payload
    assert addr_received == ('127.0.0.1', port2) # El mensaje vino de node2

    # Verificar que node2 NO recibió el mensaje
    assert len(received_messages_node2) == 0

    await net_agent1.stop()
    await net_agent2.stop()


# --- Test de integración StoreD: PUT y manejo de mensajes ---
# Este test es más complejo y simula el envío de un mensaje STORE_PUT a StoreD
# a través de NetAgent. Requiere que el StoreD maneje el mensaje correctamente.
@pytest.mark.asyncio
async def test_store_d_handle_store_put_via_net():
    """Prueba que StoreD maneje correctamente un mensaje STORE_PUT recibido via NetAgent."""
    node_id = "test_store_handle_node"
    port = 13000

    net_agent = NetAgent(node_id=node_id, listen_host='127.0.0.1', listen_port=port)
    with tempfile.TemporaryDirectory() as temp_dir:
        store_agent = StoreD(node_id=node_id, net_agent=net_agent, storage_dir=temp_dir)

        await net_agent.start()

        # Simular un mensaje STORE_PUT entrante que sería recibido por NetAgent
        # y luego despachado a StoreD.handle_message
        test_data = b"replicated data"
        test_hash = store_agent._calculate_hash(test_data)
        src_node_id = "source_node_for_replication"

        # Simulamos el mensaje que NetAgent recibiría y pasaría a StoreD
        incoming_msg = {
            "magic": "SOD1",
            "type": "STORE_PUT",
            "src": src_node_id,
            "dst": node_id,
            "msg_id": "mock_msg_id_put",
            "timestamp": int(time.time()), # O usar time.time()
            "payload": {
                "hash": test_hash,
                "data": test_data.hex(),
                "replica": True
            }
        }
        incoming_addr = ('127.0.0.1', 9999) # Dirección simulada del emisor

        # Llamar directamente al handler de StoreD para simular la recepción
        # Asumimos que NetAgent llama a todos los handlers con (msg, addr)
        # El handler de StoreD es handle_message, que ahora acepta (msg, addr)
        await store_agent.handle_message(incoming_msg, incoming_addr)

        # Verificar que el dato se haya almacenado localmente
        stored_file_path = Path(temp_dir) / test_hash
        assert stored_file_path.exists(), "El archivo no se almacenó localmente después del mensaje STORE_PUT."

        # Verificar el contenido del archivo
        with open(stored_file_path, 'rb') as f:
            stored_data = f.read()
        assert stored_data == test_data, "El contenido almacenado no coincide con el enviado."

        # Verificar la actualización de metadatos
        assert test_hash in store_agent.metadata, "El hash no se registró en los metadatos."
        meta_entry = store_agent.metadata[test_hash]
        assert src_node_id in meta_entry["replicas"], "El nodo fuente no se registró en las réplicas."
        assert meta_entry["refcount"] == 0, "refcount debería ser 0 para una réplica."

        await net_agent.stop()


# --- Test de integración StoreD: GET local ---
# Verifica que StoreD pueda recuperar un dato que él mismo almacenó localmente
# a través de la API de SODClient.

@pytest.mark.asyncio
async def test_store_d_sod_client_put_get_local_integration():
    """Prueba la integración básica de almacenamiento/recuperación local a través de SODClient."""
    node_id = "test_client_store_node"
    port = 14000

    net_agent = NetAgent(node_id=node_id, listen_host='127.0.0.1', listen_port=port)
    discover_agent = DiscoverAgent(node_id=node_id, net_agent=net_agent, peers=[])
    with tempfile.TemporaryDirectory() as temp_dir:
        store_agent = StoreD(node_id=node_id, net_agent=net_agent, storage_dir=temp_dir)
        scheduler_agent = SchedulerD(discover_agent=discover_agent, store_agent=store_agent, net_agent=net_agent)

        client = SODClient(scheduler_agent=scheduler_agent, store_agent=store_agent, node_id=f"{node_id}_client")

        await net_agent.start()

        test_data = b"client test data"
        obj_hash = client.store_put(test_data)

        # --- CORRECCIÓN: await client.store_get(...) ---
        retrieved_data = await client.store_get(obj_hash) # <--- Añadido 'await'
        assert retrieved_data == test_data, "SODClient.store_get no recuperó los mismos datos almacenados por SODClient.store_put."

        await net_agent.stop()


# Nota sobre pruebas de red más complejas (como StoreD.get remoto o negociación de SchedulerD):
# Estas pruebas requieren una simulación más elaborada de nodos interconectados
# y la posibilidad de esperar respuestas. Se pueden implementar usando asyncio.Event
# y coordinando múltiples instancias de NetAgent en un solo test, o usando frameworks
# de simulación de red. Para ahora, los tests anteriores cubren la integración básica
# y la funcionalidad local dependiente de la integración.

if __name__ == "__main__":
    pytest.main()