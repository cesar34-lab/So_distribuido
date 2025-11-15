import asyncio
import pytest

from agents.discover.main import DiscoverAgent
from agents.discover.resource_tabla import ResourceEntry
@pytest.mark.asyncio
async def test_estado_update_and_expiry():
    nodeA = DiscoverAgent(
        node_id="A",
        listen_port=9100,
        peers=[('127.0.0.1', 9101)],
        hello_interval=0.5,
        resource_expiry=2
    )

    nodeB = DiscoverAgent(
        node_id="B",
        listen_port=9101,
        peers=[('127.0.0.1', 9100)],
        hello_interval=0.5,
        resource_expiry=2
    )

    await nodeA.start()
    await nodeB.start()

    # ✅ esperar a que B envíe AL MENOS UN ESTADO
    await asyncio.sleep(0.6)

    # ✅ simular la muerte del nodo B
    nodeB.transport.close()

    # permitir que A procese el último estado
    await asyncio.sleep(1.0)

    entries = nodeA.rt.all_entries()
    ids = [e.node_id for e in entries]
    assert "B" in ids, f"B debería aparecer en {ids}"

    # esperar expiración
    await asyncio.sleep(2.5)
    nodeA.rt.remove_stale()
    entries = nodeA.rt.all_entries()
    ids = [e.node_id for e in entries]
    assert "B" not in ids, f"B no debería seguir en {ids}"

@pytest.mark.asyncio
async def test_buscar_returns_candidates():
    node1 = DiscoverAgent(node_id="n1", listen_port=9200, peers=[('127.0.0.1', 9201)], hello_interval=0.3)
    node2 = DiscoverAgent(node_id="n2", listen_port=9201, peers=[('127.0.0.1', 9200)], hello_interval=0.3)

    # configure node2 to have high RAM and tag gpu:true
    node2.self_entry.ram_free_mb = 2048
    node2.self_entry.tags = ["gpu:true","arch:arm"]

    await node1.start()
    await node2.start()
    await asyncio.sleep(0.8)  # allow ESTADO propagation

    res = await node1.buscar(query={"ram_mb": 1024, "tags": {"gpu": True}}, k=3, deadline=0.5)

    # should include node2
    ids = [r.node_id for r in res]
    assert "n2" in ids
