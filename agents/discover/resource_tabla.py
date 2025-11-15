import time
from dataclasses import dataclass, field
from typing import Dict, Optional

@dataclass
class ResourceEntry:
    node_id: str
    cpu_load: float       # [0,1] fraction busy
    ram_free_mb: float
    battery_pct: float    # [0,1]
    rtt_ms: float
    tags: list
    reputation: float     # [0,1]
    last_seen: float = field(default_factory=lambda: time.time())

    def update(self, cpu_load=None, ram_free_mb=None, battery_pct=None,
               rtt_ms=None, tags=None, reputation=None):
        if cpu_load is not None: self.cpu_load = cpu_load
        if ram_free_mb is not None: self.ram_free_mb = ram_free_mb
        if battery_pct is not None: self.battery_pct = battery_pct
        if rtt_ms is not None: self.rtt_ms = rtt_ms
        if tags is not None: self.tags = tags
        if reputation is not None: self.reputation = reputation
        self.last_seen = time.time()

class ResourceTable:
    def __init__(self, expiry_seconds: int = 10):
        self.table: Dict[str, ResourceEntry] = {}
        self.expiry_seconds = expiry_seconds

    def upsert(self, entry: ResourceEntry):
        self.table[entry.node_id] = entry

    def remove_stale(self):
        now = time.time()
        stale = [nid for nid, e in self.table.items() if now - e.last_seen > self.expiry_seconds]
        for nid in stale:
            del self.table[nid]

    def get(self, node_id: str) -> Optional[ResourceEntry]:
        return self.table.get(node_id)

    def all_entries(self):
        self.remove_stale()
        return list(self.table.values())
