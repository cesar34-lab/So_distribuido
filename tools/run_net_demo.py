# tools/run_net_demo.py
import asyncio
import signal
from agents.net import NetAgent
from agents.net.transport import SimpleSigner
import time

async def main():
    a = NetAgent("A", listen_port=13000, signer=SimpleSigner(b"key"))
    b = NetAgent("B", listen_port=13001, signer=SimpleSigner(b"key"))
    def handler_b(msg, addr):
        print(f"[B] Recibido {msg['type']} de {msg['src']} payload={msg['payload']}")
    b.add_handler(handler_b)
    await a.start()
    await b.start()
    # A envía HELLO broadcast (simulado)
    peers = [("127.0.0.1",13001)]
    await a.broadcast(peers, "HELLO", {"info":"hola vecinos"}, qos='DISCOVER')
    # enviar reliable message
    await a.send(("127.0.0.1",13001), "BUSCAR", {"query":"cpu>50","_reliable":True}, reliable=True, qos='CTRL')
    # dejar correr 3 segundos
    await asyncio.sleep(3)
    await a.stop()
    await b.stop()

if __name__ == "__main__":
    asyncio.run(main())
