# agents/health/health.py

import time
import asyncio
from typing import Dict, Callable, Optional

class HealthAgent:
    def __init__(self, node_id: str, check_interval: float = 5.0, dead_threshold: float = 30.0, on_node_down_callback: Optional[Callable[[str], None]] = None):
        """
        Inicializa el Health Agent.

        Args:
            node_id (str): ID del nodo donde corre este agente.
            check_interval (float): Segundos entre verificaciones de nodos.
            dead_threshold (float): Segundos sin ver un nodo para considerarlo caído.
            on_node_down_callback (Callable): Función a llamar cuando se detecta un nodo caído.
                                              Ej: on_node_down_callback(node_id)
        """
        self.node_id = node_id
        self.check_interval = check_interval
        self.dead_threshold = dead_threshold
        self.on_node_down_callback = on_node_down_callback

        # Diccionario para almacenar el último timestamp de aviso de cada nodo
        self.node_last_seen: Dict[str, float] = {node_id: time.time()} # Auto-registro
        self.monitor_task = None

    def start(self):
        """Inicia el bucle de monitoreo asincrónico."""
        if self.monitor_task is None or self.monitor_task.done():
            self.monitor_task = asyncio.create_task(self._monitor_loop())
            print(f"[HealthAgent] Monitor iniciado en {self.node_id}, intervalo: {self.check_interval}s, umbral: {self.dead_threshold}s")
        else:
            print(f"[HealthAgent] Monitor ya está corriendo.")

    async def _monitor_loop(self):
        """Bucle principal de monitoreo."""
        while True:
            await asyncio.sleep(self.check_interval)
            current_time = time.time()
            nodes_to_remove = []
            for node_id, last_seen in self.node_last_seen.items():
                if node_id == self.node_id:
                    continue # No monitorear a sí mismo
                if current_time - last_seen > self.dead_threshold:
                    print(f"[HealthAgent] Nodo {node_id} considerado CAÍDO (última vez visto hace {current_time - last_seen:.2f}s).")
                    if self.on_node_down_callback:
                        self.on_node_down_callback(node_id)
                    # Opcional: eliminar el nodo de la lista de seguimiento
                    # nodes_to_remove.append(node_id)
            # for node_id in nodes_to_remove:
            #     del self.node_last_seen[node_id]

    def on_message_received(self, src_node_id: str):
        """
        Método para que otros agentes (como Discover) notifiquen al Health
        cuando reciben un mensaje de un nodo (HELLO, ESTADO).
        """
        self.node_last_seen[src_node_id] = time.time()
        # print(f"[HealthAgent] Actualizado last_seen para {src_node_id}")

    def stop(self):
        """Detiene el bucle de monitoreo."""
        if self.monitor_task:
            self.monitor_task.cancel()
            print(f"[HealthAgent] Monitor detenido en {self.node_id}.")
