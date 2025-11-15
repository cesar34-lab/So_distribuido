# agents/net/net_agent.py
import asyncio
import logging
import time
import socket
from typing import Callable, Dict, Any, Optional, Tuple, List
from .transport import (
    make_msg, pack_msg, unpack_msg, MessageRecord,
    DEFAULT_ACK_TIMEOUT, DEFAULT_MAX_RETRIES, SimpleSigner
)

logger = logging.getLogger("NetAgent")
logger.setLevel(logging.INFO)
handler = logging.StreamHandler()
handler.setFormatter(logging.Formatter("[%(asctime)s] %(message)s"))
logger.addHandler(handler)

# QoS priorities (orden de servicio en loop)
QOS_ORDER = ['CTRL', 'DISCOVER', 'DATA']

class UDPProtocol(asyncio.DatagramProtocol):
    def __init__(self, on_datagram):
        self.on_datagram = on_datagram
        self.transport = None

    def connection_made(self, transport):
        self.transport = transport

    def datagram_received(self, data, addr):
        asyncio.create_task(self.on_datagram(data, addr))

class NetAgent:
    def __init__(self, node_id: str, listen_host: str='127.0.0.1', listen_port: int=10000,
                 signer: Optional[SimpleSigner]=None):
        self.node_id = node_id
        self.host = listen_host
        self.port = listen_port
        self.signer = signer
        self.loop = asyncio.get_event_loop()
        # QoS queues: list of (dst_tuple, msg_dict, reliable, msg_id)
        self.queues: Dict[str, asyncio.Queue] = {
            'CTRL': asyncio.Queue(),
            'DISCOVER': asyncio.Queue(),
            'DATA': asyncio.Queue()
        }
        # pending reliable messages: msg_id -> MessageRecord
        self.pending: Dict[str, MessageRecord] = {}
        # handlers: callback(msg_dict, addr)
        self.handlers: List[Callable[[Dict[str,Any], Tuple[str,int]], None]] = []
        self.transport = None
        self.protocol = None
        # network parameters
        self.ack_timeout = DEFAULT_ACK_TIMEOUT
        self.max_retries = DEFAULT_MAX_RETRIES
        self.running = False

    async def start(self):
        # crear socket UDP y protocolo
        logger.info(f"NetAgent {self.node_id} arrancando en {self.host}:{self.port}")
        await self._create_socket()
        self.running = True
        # lanzar consumidor de colas y retransmisor
        self.loop.create_task(self._q_consumer_loop())
        self.loop.create_task(self._retransmit_loop())

    async def _create_socket(self):
        listen = (self.host, self.port)
        transport, protocol = await self.loop.create_datagram_endpoint(
            lambda: UDPProtocol(self._on_datagram),
            local_addr=listen)
        self.transport = transport
        self.protocol = protocol

    async def stop(self):
        self.running = False
        if self.transport:
            self.transport.close()

    # externa: para que agentes reciban mensajes
    def add_handler(self, cb: Callable[[Dict[str,Any], Tuple[str,int]], None]):
        self.handlers.append(cb)

    # envío público
    async def send(self, dst: Tuple[str,int], msg_type: str, payload: Any,
                   reliable: bool=False, qos: str='DATA') -> str:
        msg = make_msg(msg_type, self.node_id, f"{dst[0]}:{dst[1]}", payload)
        packed = pack_msg(msg, self.signer)
        msg_id = msg['msg_id']
        # Encolar según QoS
        await self.queues[qos].put((dst, msg, reliable))
        logger.debug(f"Encolado {msg_type} id={msg_id} dst={dst} reliable={reliable} qos={qos}")
        return msg_id

    # difusión local (simulador): envia a una lista de peers
    async def broadcast(self, peers: List[Tuple[str,int]], msg_type: str, payload: Any, qos='DISCOVER'):
        for p in peers:
            await self.send(p, msg_type, payload, reliable=False, qos=qos)

    # consumidor de colas con prioridad
    async def _q_consumer_loop(self):
        while self.running:
            processed = False
            for qos in QOS_ORDER:
                q = self.queues[qos]
                try:
                    dst, msg, reliable = q.get_nowait()
                except asyncio.QueueEmpty:
                    continue
                packed = pack_msg(msg, self.signer)
                dst_addr = (dst[0], int(dst[1])) if isinstance(dst, tuple) else tuple(dst.split(':'))
                # send immediate
                self._do_send_raw(packed, dst_addr)
                if reliable:
                    rec = MessageRecord(msg['msg_id'], packed, dst_addr, True, time.time(), retries=0, qos=qos)
                    self.pending[msg['msg_id']] = rec
                processed = True
                q.task_done()
                # después de enviar un mensaje, priorizar volver a HEAD de QoS
                await asyncio.sleep(0)  # cede el control
                break
            if not processed:
                # no había mensajes; dormir brevemente
                await asyncio.sleep(0.01)

    def _do_send_raw(self, packed: bytes, dst: Tuple[str,int]):
        try:
            self.transport.sendto(packed, dst)
            logger.debug(f"Enviado paquete a {dst}")
        except Exception as e:
            logger.error(f"Error enviando a {dst}: {e}")

    # retransmisiones para mensajes reliable
    async def _retransmit_loop(self):
        while self.running:
            now = time.time()
            to_retry = []
            for msg_id, rec in list(self.pending.items()):
                elapsed = now - rec.timestamp
                timeout = self.ack_timeout * (2 ** rec.retries)  # backoff exponencial
                if elapsed >= timeout:
                    if rec.retries >= self.max_retries:
                        logger.warning(f"Mensaje {msg_id} agotó reintentos. Notificando fallo.")
                        # notificar a handlers de fallo si hace falta (callback)
                        del self.pending[msg_id]
                    else:
                        rec.retries += 1
                        rec.timestamp = now
                        jitter = min(0.1, 0.01 * rec.retries)
                        await asyncio.sleep(jitter)
                        self._do_send_raw(rec.packed, rec.dst)
                        logger.info(f"Retransmitiendo {msg_id} a {rec.dst}, intento {rec.retries}")
            await asyncio.sleep(0.05)

    # recepción de datagram
    async def _on_datagram(self, data: bytes, addr: Tuple[str,int]):
        try:
            msg, verified = unpack_msg(data, self.signer)
        except Exception as e:
            logger.error(f"Mensaje malformado desde {addr}: {e}")
            return
        mtype = msg.get('type','')
        msg_id = msg.get('msg_id')
        # ACK handling: si es ACK, borrar pending
        if mtype == 'ACK':
            ref = msg.get('payload',{}).get('ref')
            if ref and ref in self.pending:
                logger.info(f"ACK recibido para {ref} desde {addr}")
                del self.pending[ref]
            return
        # Si es mensaje fiable (se marca en payload.reliable) devolver ACK
        reliable_flag = msg.get('payload',{}).get('_reliable', False)
        if reliable_flag:
            ack = make_ack(msg_id, self.node_id)
            packed_ack = pack_msg(ack, self.signer)
            self._do_send_raw(packed_ack, addr)
        # dispatch a handlers
        for cb in self.handlers:
            try:
                cb(msg, addr)
            except Exception as e:
                logger.exception(f"Handler raised: {e}")

def make_ack(ref_msg_id: str, src_node: str):
    return make_msg("ACK", src_node, "*", {"ref": ref_msg_id})
