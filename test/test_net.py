# tests/test_net.py
import asyncio
import pytest
import time
from agents.net import NetAgent
from agents.net.transport import SimpleSigner

@pytest.mark.asyncio
async def test_send_receive_loopback(tmp_path):
    loop = asyncio.get_event_loop()
    node_a = NetAgent("nodeA", listen_port=12000, signer=SimpleSigner(b"keyA"))
    node_b = NetAgent("nodeB", listen_port=12001, signer=SimpleSigner(b"keyB"))

    received = []

    def handler_b(msg, addr):
        received.append((msg, addr))

    node_b.add_handler(handler_b)

    await node_a.start()
    await node_b.start()

    # enviar mensaje reliable de A a B
    await node_a.send(("127.0.0.1",12001), "TEST", {"foo":"bar", "_reliable": True}, reliable=True, qos='CTRL')

    # esperar hasta que B reciba
    t0 = time.time()
    while time.time() - t0 < 5:
        if received:
            break
        await asyncio.sleep(0.05)

    await node_a.stop()
    await node_b.stop()
    assert len(received) >= 1
    assert received[0][0]['type'] == 'TEST'
    assert received[0][0]['payload']['foo'] == 'bar'
