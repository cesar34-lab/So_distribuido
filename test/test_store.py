import pytest
import tempfile
import shutil
import asyncio
import time # <-- Añadido import
from pathlib import Path
from agents.store_d.store import StoreD

# Mock NetAgent para pruebas
class MockNetAgent:
    def __init__(self):
        self.sent_messages = []
        self.known_nodes = {"node1", "node2", "remote_node"} # Simular nodos conocidos

    async def send(self, msg, reliable=False):
        self.sent_messages.append(msg)
        print(f"[MockNetAgent] Enviado mensaje: {msg['type']} a {msg['dst']}")

    async def send_request(self, msg, timeout=5.0):
        # Registrar el mensaje enviado (el STORE_GET)
        self.sent_messages.append(msg)
        print(f"[MockNetAgent] Enviado mensaje REQUEST: {msg['type']} a {msg['dst']}")

        # Simular respuesta basada en el tipo de solicitud
        if msg.get("type") == "STORE_GET":
            # Simular que el nodo remoto tiene o no el hash
            requested_hash = msg["payload"]["hash"]
            # En este mock, asumimos que hay un nodo remoto que sí tiene el hash "existent_hash"
            if requested_hash == "existent_hash":
                # Simulamos que responde el primer nodo al que se le preguntó
                # En la implementación real de StoreD, el bucle itera sobre candidate_nodes
                # y se detiene en el primero que devuelve FOUND.
                # El log dice "[Store-D] Intentando obtener existent_hash de node2"
                # y luego "[Store-D] Obtenido existent_hash de node2"
                # Esto implica que 'node2' fue el destinatario del STORE_GET que devolvió FOUND.
                # Por lo tanto, el mock debe devolver FOUND si el destino es el correcto o si no nos importa el destino.
                # Para simplificar, devolvemos FOUND si el hash es "existent_hash".
                return {
                    "magic": "SOD1",
                    "type": "STORE_FOUND",
                    "src": "remote_node", # Podríamos simular que el src es el nodo que lo tenía
                    "dst": msg["src"],
                    "msg_id": f"found_{requested_hash}_mock",
                    "timestamp": int(time.time()),
                    "payload": {
                        "hash": requested_hash,
                        "data": "48656c6c6f204d6f636b65642053544f5245" # "Hello Mocked STORE"
                    }
                }
            else:
                # Simulamos que devuelve NOT_FOUND
                return {
                    "magic": "SOD1",
                    "type": "STORE_NOT_FOUND",
                    "src": "remote_node", # Podríamos simular que el src es el nodo que no lo tenía
                    "dst": msg["src"],
                    "msg_id": f"not_found_{requested_hash}_mock",
                    "timestamp": int(time.time()),
                    "payload": {"hash": requested_hash}
                }
        return None

    async def handle_message(self, msg):
        # Simular que el Store-D llama a este método para recibir mensajes entrantes
        # En pruebas, tal vez no sea necesario implementarlo completamente
        pass

@pytest.fixture
def temp_storage_dir():
    """Crea un directorio temporal para las pruebas de almacenamiento."""
    temp_dir = tempfile.mkdtemp()
    yield Path(temp_dir)
    shutil.rmtree(temp_dir)

@pytest.fixture
def mock_net_agent():
    """Proporciona una instancia de MockNetAgent."""
    return MockNetAgent()

@pytest.mark.asyncio
async def test_put_get_local(temp_storage_dir, mock_net_agent):
    """Prueba que put() almacene localmente y get() lo recupere."""
    store = StoreD(node_id="test_node", net_agent=mock_net_agent, storage_dir=temp_storage_dir)

    data = b"Hello, Store-D!"
    obj_hash = store.put(data)

    retrieved_data = await store.get(obj_hash)
    assert retrieved_data == data

    # Verificar que el archivo exista en el directorio
    assert (temp_storage_dir / obj_hash).exists()

    # Verificar metadatos
    # El refcount debe ser 1: incrementado por put(), NO por get() local
    assert obj_hash in store.metadata
    assert store.metadata[obj_hash]["refcount"] == 1 # Incrementado solo por put()


@pytest.mark.asyncio
async def test_replicate(temp_storage_dir, mock_net_agent):
    """Prueba la funcionalidad de replicación."""
    store = StoreD(node_id="test_node", net_agent=mock_net_agent, storage_dir=temp_storage_dir)

    data = b"Data to replicate"
    obj_hash = store.put(data)

    target_nodes = ["node1", "node2"]
    await store.replicate(obj_hash, target_nodes)

    # Verificar que se hayan enviado mensajes STORE_PUT
    sent_store_puts = [msg for msg in mock_net_agent.sent_messages if msg.get("type") == "STORE_PUT"]
    assert len(sent_store_puts) == len(target_nodes)

    for msg in sent_store_puts:
        assert msg["payload"]["hash"] == obj_hash
        assert bytes.fromhex(msg["payload"]["data"]) == data
        assert msg["dst"] in target_nodes
        assert msg["payload"]["replica"] == True

    # Verificar que las réplicas se hayan registrado localmente en metadatos
    assert set(store.list_replicas(obj_hash)) == {store.node_id} | set(target_nodes)


@pytest.mark.asyncio
async def test_get_remote_found(temp_storage_dir, mock_net_agent):
    """Prueba que get() recupere un objeto de otro nodo si no está localmente."""
    store = StoreD(node_id="test_node", net_agent=mock_net_agent, storage_dir=temp_storage_dir)

    # Intentar obtener un hash que no está localmente pero que un nodo remoto "tiene"
    # El mock de NetAgent ya conoce a "remote_node"
    requested_hash = "existent_hash"
    expected_data = b"Hello Mocked STORE"

    retrieved_data = await store.get(requested_hash)
    assert retrieved_data == expected_data

    # Verificar que se haya enviado un STORE_GET
    sent_gets = [msg for msg in mock_net_agent.sent_messages if msg.get("type") == "STORE_GET"]
    # Ahora, send_request también registra el mensaje enviado.
    # El log muestra que intentó obtenerlo de 'node2' y lo encontró.
    # Por lo tanto, se envió un STORE_GET.
    assert len(sent_gets) >= 1 # Se envió al menos un STORE_GET
    # Opcional: verificar que el hash y el destino sean correctos para al menos un mensaje
    found_matching_get = any(
        msg["payload"]["hash"] == requested_hash
        for msg in sent_gets
    )
    assert found_matching_get, f"No se encontró un STORE_GET para el hash {requested_hash}"


@pytest.mark.asyncio
async def test_get_remote_not_found(temp_storage_dir, mock_net_agent):
    """Prueba que get() devuelva None si el objeto no se encuentra en ningún nodo."""
    store = StoreD(node_id="test_node", net_agent=mock_net_agent, storage_dir=temp_storage_dir)

    # Intentar obtener un hash que no está localmente ni remotamente
    requested_hash = "non_existent_hash"

    retrieved_data = await store.get(requested_hash)
    assert retrieved_data is None

    # Verificar que se haya enviado al menos un STORE_GET
    sent_gets = [msg for msg in mock_net_agent.sent_messages if msg.get("type") == "STORE_GET"]
    # La implementación de store.get() itera sobre candidate_nodes si no está en metadatos.
    # candidate_nodes = ["node1", "node2", "remote_node"] (3 nodos)
    # Enviaría 3 STORE_GET, todos respondiendo NOT_FOUND.
    # El test verifica que se haya enviado *al menos uno*.
    # Con la corrección, ahora debería haber 3 mensajes STORE_GET registrados.
    assert len(sent_gets) >= 1 # Se envió al menos un STORE_GET
    found_matching_get = any(
        msg["payload"]["hash"] == requested_hash
        for msg in sent_gets
    )
    assert found_matching_get, f"No se encontró un STORE_GET para el hash {requested_hash}"


@pytest.mark.asyncio
async def test_garbage_collect(temp_storage_dir, mock_net_agent):
    """Prueba la recolección de basura."""
    store = StoreD(node_id="test_node", net_agent=mock_net_agent, storage_dir=temp_storage_dir, gc_ttl=1) # TTL corto para pruebas

    data = b"Garbage Data"
    obj_hash = store.put(data)

    # Decrementar refcount para que sea 0
    store.metadata[obj_hash]["refcount"] = 0
    store._save_metadata()

    # Forzar un timestamp viejo
    store.metadata[obj_hash]["timestamp"] = int(time.time()) - 2 # Más viejo que TTL
    store._save_metadata()

    # Crear el archivo localmente para simular que existe
    with open(temp_storage_dir / obj_hash, 'wb') as f:
        f.write(data)

    # Ejecutar GC
    store.garbage_collect()

    # Verificar que el archivo ya no exista
    assert not (temp_storage_dir / obj_hash).exists()

    # Verificar que la entrada de metadatos haya sido eliminada
    assert obj_hash not in store.metadata

