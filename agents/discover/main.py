# agents/discover/main.py (Versión modificada para integración)

import asyncio
import json
import time
import uuid
from typing import Dict, Any, List, Tuple
# Asegúrate que la ruta sea correcta para tu estructura de proyecto
from agents.discover.resource_tabla import ResourceEntry, ResourceTable
from agents.discover.utils import compute_score

# Message types
TYPE_HELLO = "HELLO"
TYPE_ESTADO = "ESTADO"
TYPE_BUSCAR = "BUSCAR"
TYPE_ENCONTRADO = "ENCONTRADO"
TYPE_ACK = "ACK"

class DiscoverAgent:
    def __init__(self, node_id: str, net_agent, peers: List[tuple], # <-- Cambio: net_agent en lugar de peers UDP directos
                 hello_interval: float = 2.0, resource_expiry: int = 8):
        """
        net_agent: Instancia del NetAgent a usar para comunicación.
        peers: list of tuples (host, port) of known neighbors (UDP) - Solo para inicialización
        """
        self.node_id = node_id
        self.net_agent = net_agent # <--- Nuevo parámetro
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
        self.loop = asyncio.get_event_loop()
        self._buscar_cache = {}  # query_str -> (timestamp, results)

        # --- Registrar este agente como handler en NetAgent ---
        self.net_agent.add_handler(self.on_net_message) # <-- Añadido: ahora se registra

    async def start(self):
        # Iniciar tarea periódica de envío de estado
        asyncio.create_task(self._periodic_estado()) # <-- Cambio: usar _periodic_estado
        print(f"[{self.node_id}] DiscoverAgent iniciado, usando NetAgent en {self.net_agent.host}:{self.net_agent.port}")

    # --- NUEVO: Método para envío periódico de estado ---
    async def _periodic_estado(self): # <-- Cambio de nombre
        while True:
            await self.send_estado()
            await asyncio.sleep(self.hello_interval)

    async def send_estado(self):
        msg = {
            "magic": "SOD1",
            "type": TYPE_ESTADO,
            "src": self.node_id,
            "dst": "*", # Difusión
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
        # Usar broadcast de NetAgent
        peer_addrs = [(host, port) for host, port in self.peers]
        await self.net_agent.broadcast(peer_addrs, msg["type"], msg["payload"], qos='DISCOVER')
        # Opcional: también enviar a nodos conocidos de NetAgent
        # for known_node_id in self.net_agent.get_known_nodes():
        #     if known_node_id != self.node_id:
        #         # Necesitas mapear node_id -> (host, port) aquí
        #         # Por ahora, asumiremos que peers contiene todos los nodos iniciales
        #         pass


    # --- NUEVO: Handler para mensajes recibidos via NetAgent ---
    async def on_net_message(self, msg: Dict[str, Any], addr: Tuple[str, int]): # <-- Añadido
        """Handler para mensajes recibidos via NetAgent."""
        typ = msg.get("type")
        src = msg.get("src")
        if not src or src == self.node_id:
            return # Ignorar mensajes de uno mismo

        # Avisar a NetAgent para actualizar mapeo node_id -> addr
        self.net_agent.update_node_addr(src, addr)

        # Avisar al HealthAgent (si está integrado) de la recepción
        # Supongamos que hay una referencia opcional a HealthAgent
        # if hasattr(self, 'health_agent') and self.health_agent:
        #     self.health_agent.on_message_received(src)

        # dispatch
        if typ == TYPE_ESTADO:
            await self.handle_estado(msg, src) # Pasa src para actualizar tabla
        elif typ == TYPE_BUSCAR:
            await self.handle_buscar(msg, addr) # Pasa addr para responder
        elif typ == TYPE_ENCONTRADO:
            await self.handle_encontrado(msg, src) # Pasa src para actualizar tabla
        else:
            pass  # ignore others

    async def handle_estado(self, msg: Dict[str, Any], src_node_id: str): # <--- Cambio: src_node_id en lugar de msg["src"]
        payload = msg.get("payload", {})
        # Añadir src_node_id a la entrada
        entry = ResourceEntry(
            node_id=src_node_id, # <--- Cambio
            cpu_load=payload.get("cpu_load", 0.0),
            ram_free_mb=payload.get("ram_free_mb", 0.0),
            battery_pct=payload.get("battery_pct", 1.0),
            rtt_ms=payload.get("rtt_ms", 50.0),
            tags=payload.get("tags", []),
            reputation=payload.get("reputation", 0.5)
        )
        self.rt.upsert(entry)
        # print local resource table size
        # print(f"[{self.node_id}] Updated estado from {src_node_id}; table size={len(self.rt.table)}")

    async def handle_buscar(self, msg: Dict[str, Any], addr: Tuple[str, int]):
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
        from agents.discover.utils import matches_required_tags # <-- Ajusta ruta si es necesario
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
                "dst": origin, # Enviar directamente al origin
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
            # Para enviar directamente al origin, necesitamos mapear node_id -> (host, port)
            # Supongamos que NetAgent tiene una forma de mapear nodos a direcciones
            # Por ahora, simplemente lo difundimos. En un sistema real, se usaría una DHT o tabla de nodos.
            # Para la simulación, si conocemos la dirección del origin, podríamos enviarla directamente.
            # Por simplicidad, lo difundimos a todos los peers (menos eficiente).
            peer_addrs = [(host, port) for host, port in self.peers]
            await self.net_agent.broadcast(peer_addrs, resp["type"], resp["payload"], qos='DISCOVER')
            # Opcional: intentar enviar directamente si se puede mapear origin -> addr
            # origin_addr = self._node_id_to_addr(origin) # Método a implementar
            # if origin_addr:
            #     await self.net_agent.send(origin_addr, resp["type"], resp["payload"], reliable=False, qos='DISCOVER')

    async def handle_encontrado(self, msg: Dict[str, Any], src_node_id: str): # <--- Cambio: src_node_id
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
            # Asegurar que el nodo encontrado también esté en la lista de conocidos de NetAgent
            self.net_agent.add_known_node(c.get("node_id"))

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
        # Usar broadcast de NetAgent
        peer_addrs = [(host, port) for host, port in self.peers]
        await self.net_agent.broadcast(peer_addrs, msg["type"], msg["payload"], qos='DISCOVER')
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