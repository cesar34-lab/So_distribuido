import asyncio
import json
import time
import uuid
from typing import Dict, Any, List
from .resource_tabla import ResourceEntry, ResourceTable
from .utils import compute_score

# Message types
TYPE_HELLO = "HELLO"
TYPE_ESTADO = "ESTADO"
TYPE_BUSCAR = "BUSCAR"
TYPE_ENCONTRADO = "ENCONTRADO"
TYPE_ACK = "ACK"

class DiscoverAgent:
    def __init__(self, node_id: str, listen_port: int, peers: List[tuple],
                 hello_interval: float = 2.0, resource_expiry: int = 8):
        """
        peers: list of tuples (host, port) of known neighbors (UDP)
        """
        self.node_id = node_id
        self.port = listen_port
        self.peers = peers
        self.hello_interval = hello_interval
        self.rt = ResourceTable(expiry_seconds=resource_expiry)
        # register self in local table (self metrics)
        self.self_entry = ResourceEntry(
            node_id=node_id,
            cpu_load=0.05,
            ram_free_mb=512,
            battery_pct=1.0,
            rtt_ms=1.0,
            tags=["gpu:false","arch:arm"],
            reputation=0.5
        )
        self.rt.upsert(self.self_entry)
        self.transport = None
        self.loop = asyncio.get_event_loop()
        self._buscar_cache = {}  # query_str -> (timestamp, results)

    async def start(self):
        await self._start_socket()
        asyncio.create_task(self._periodic_hello())
        print(f"[{self.node_id}] DiscoverAgent listening on UDP {self.port}")

    async def _start_socket(self):
        # create UDP endpoint
        self.transport, _ = await self.loop.create_datagram_endpoint(
            lambda: DiscoverProtocol(self),
            local_addr=('127.0.0.1', self.port)
        )

    async def _periodic_hello(self):
        while True:
            await self.send_estado()
            await asyncio.sleep(self.hello_interval)

    async def send_estado(self):
        msg = {
            "magic": "SOD1",
            "type": TYPE_ESTADO,
            "src": self.node_id,
            "dst": "*",
            "msg_id": str(uuid.uuid4()),
            "timestamp": time.time(),
            "payload": {
                "cpu_load": self.self_entry.cpu_load,
                "ram_free_mb": self.self_entry.ram_free_mb,
                "battery_pct": self.self_entry.battery_pct,
                "rtt_ms": self.self_entry.rtt_ms,
                "tags": self.self_entry.tags,
                "reputation": self.self_entry.reputation
            }
        }
        await self._broadcast(msg)

    async def _broadcast(self, msg: Dict[str, Any]):
        data = json.dumps(msg).encode('utf-8')
        for (h, p) in self.peers:
            try:
                self.transport.sendto(data, (h, p))
            except Exception as e:
                print(f"[{self.node_id}] broadcast error to {(h,p)}: {e}")

    async def handle_estado(self, msg: Dict[str, Any]):
        payload = msg.get("payload", {})
        src = msg.get("src")
        entry = ResourceEntry(
            node_id=src,
            cpu_load=payload.get("cpu_load", 0.0),
            ram_free_mb=payload.get("ram_free_mb", 0.0),
            battery_pct=payload.get("battery_pct", 1.0),
            rtt_ms=payload.get("rtt_ms", 50.0),
            tags=payload.get("tags", []),
            reputation=payload.get("reputation", 0.5)
        )
        self.rt.upsert(entry)
        # optional: reply ACK to sender
        # print local resource table size
        # print(f"[{self.node_id}] Updated estado from {src}; table size={len(self.rt.table)}")

    async def handle_buscar(self, msg: Dict[str, Any], addr):
        """
        On BUSCAR receive: check if this node meets query -> respond ENCONTRADO
        BUSCAR payload: { "query": { "cpu_mips":..., "ram_mb":..., "tags": {...} }, "k": N, "origin": node_id }
        """
        payload = msg.get("payload", {})
        query = payload.get("query", {})
        k = payload.get("k", 5)
        origin = payload.get("origin")
        # Decide if this node qualifies (we can also forward; here simple respond if meets)
        meets = True
        # For simplicity evaluate RAM and tags
        req_ram = query.get("ram_mb", 0)
        required_tags = query.get("tags", {})
        # check tags via util
        from .utils import matches_required_tags
        if not matches_required_tags(self.self_entry.tags, required_tags):
            meets = False
        if req_ram and self.self_entry.ram_free_mb < req_ram:
            meets = False
        if meets:
            # respond with ENCONTRADO containing candidate info
            resp = {
                "magic": "SOD1",
                "type": TYPE_ENCONTRADO,
                "src": self.node_id,
                "dst": origin,
                "msg_id": str(uuid.uuid4()),
                "timestamp": time.time(),
                "payload": {
                    "candidates": [
                        {
                            "node_id": self.node_id,
                            "cpu_load": self.self_entry.cpu_load,
                            "ram_free_mb": self.self_entry.ram_free_mb,
                            "battery_pct": self.self_entry.battery_pct,
                            "rtt_ms": self.self_entry.rtt_ms,
                            "tags": self.self_entry.tags,
                            "reputation": self.self_entry.reputation
                        }
                    ]
                }
            }
            # send direct to origin (we need to know origin addr -> origin ports are conventionally base+offset)
            # will send to all peers; scheduler or origin will filter by node_id
            await self._broadcast(resp)

    async def handle_encontrado(self, msg: Dict[str, Any]):
        # store in cache as potential result for pending buscar (if we implemented waiting)
        # For now just upsert candidates in local table
        pl = msg.get("payload", {})
        cands = pl.get("candidates", [])
        for c in cands:
            entry = ResourceEntry(
                node_id=c.get("node_id"),
                cpu_load=c.get("cpu_load", 0.0),
                ram_free_mb=c.get("ram_free_mb", 0.0),
                battery_pct=c.get("battery_pct", 1.0),
                rtt_ms=c.get("rtt_ms", 50.0),
                tags=c.get("tags", []),
                reputation=c.get("reputation", 0.5)
            )
            self.rt.upsert(entry)

    async def buscar(self, query: dict, k: int = 5, deadline: float = 1.0):
        """
        Sends BUSCAR to peers and returns list of candidate ResourceEntry sorted by score.
        Uses a simple cache to avoid flooding.
        """
        qkey = json.dumps({"q": query, "k": k})
        now = time.time()
        # cache TTL 2s
        if qkey in self._buscar_cache:
            ts, res = self._buscar_cache[qkey]
            if now - ts < 2.0:
                return res[:k]

        msg = {
            "magic": "SOD1",
            "type": TYPE_BUSCAR,
            "src": self.node_id,
            "dst": "*",
            "msg_id": str(uuid.uuid4()),
            "timestamp": now,
            "payload": {
                "query": query,
                "k": k,
                "origin": self.node_id
            }
        }
        await self._broadcast(msg)
        # wait a short interval for responses to arrive (they will update rt via handle_encontrado)
        await asyncio.sleep(deadline)
        # collect candidates from resource table (excluding self)
        entries = [e for e in self.rt.all_entries() if e.node_id != self.node_id]
        # compute scores
        scored = []
        req_ram = query.get("ram_mb", 0)
        req_tags = query.get("tags", {})
        for e in entries:
            s = compute_score(e, required_ram=req_ram, required_tags=req_tags)
            scored.append((s, e))
        scored.sort(key=lambda x: x[0], reverse=True)
        results = [e for (s, e) in scored][:k]
        self._buscar_cache[qkey] = (now, results)
        return results

class DiscoverProtocol(asyncio.DatagramProtocol):
    def __init__(self, agent: DiscoverAgent):
        self.agent = agent

    def datagram_received(self, data, addr):
        try:
            msg = json.loads(data.decode('utf-8'))
        except Exception as e:
            print(f"[{self.agent.node_id}] Bad msg from {addr}: {e}")
            return
        typ = msg.get("type")
        # dispatch
        if typ == TYPE_ESTADO:
            asyncio.create_task(self.agent.handle_estado(msg))
        elif typ == TYPE_BUSCAR:
            asyncio.create_task(self.agent.handle_buscar(msg, addr))
        elif typ == TYPE_ENCONTRADO:
            asyncio.create_task(self.agent.handle_encontrado(msg))
        else:
            pass  # ignore others
