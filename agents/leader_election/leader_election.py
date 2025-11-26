# agents/leader_election/leader_election_agent.py

import asyncio
import logging
import time
from typing import List, Optional, Callable
from agents.discover.main import DiscoverAgent
from agents.health.health import HealthAgent

# Tipos de mensaje para el algoritmo Bully
MSG_ELECTION = "BULLY_ELECTION"
MSG_COORDINATOR = "BULLY_COORDINATOR"

logger = logging.getLogger(__name__)

class LeaderElectionAgent:
    def __init__(self, node_id: str, discover_agent: DiscoverAgent, health_agent: HealthAgent,
                 on_become_leader_callback: Callable[[], None],
                 on_leader_changed_callback: Optional[Callable[[str], None]] = None,
                 election_timeout: float = 5.0):
        """
        Args:
            node_id: ID único del nodo local.
            discover_agent: Para obtener la lista de nodos de la red.
            health_agent: Para verificar la salud del líder.
            on_become_leader_callback: Función a llamar cuando este nodo se convierte en líder.
            on_leader_changed_callback: Función a llamar cuando cambia el líder (opcional).
            election_timeout: Tiempo de espera para respuestas en la elección.
        """
        self.node_id = node_id
        self.discover_agent = discover_agent
        self.health_agent = health_agent
        self.on_become_leader_callback = on_become_leader_callback
        self.on_leader_changed_callback = on_leader_changed_callback
        self.election_timeout = election_timeout

        self.current_leader: Optional[str] = None
        self.is_running = False
        self._monitor_task: Optional[asyncio.Task] = None

    def start(self):
        """Inicia el monitoreo del líder."""
        if not self.is_running:
            self.is_running = True
            self._monitor_task = asyncio.create_task(self._leader_monitor_loop())
            logger.info(f"[LeaderElection] Monitoreo de líder iniciado en {self.node_id}.")

    def stop(self):
        """Detiene el monitoreo del líder."""
        self.is_running = False
        if self._monitor_task:
            self._monitor_task.cancel()
            logger.info(f"[LeaderElection] Monitoreo de líder detenido en {self.node_id}.")

    async def _leader_monitor_loop(self):
        """Bucle principal que monitorea al líder y lanza elecciones si es necesario."""
        while self.is_running:
            try:
                # 1. Obtener la lista de nodos activos
                all_nodes = [entry.node_id for entry in self.discover_agent.rt.all_entries()]
                all_nodes.append(self.node_id)  # Incluirse a sí mismo
                all_nodes = list(set(all_nodes)) # Eliminar duplicados

                if not all_nodes:
                    await asyncio.sleep(2)
                    continue

                # 2. Identificar al posible líder (nodo con ID más alto)
                potential_leader = max(all_nodes)

                # 3. Si soy yo el líder potencial, verificar si debo reclamar el liderazgo
                if potential_leader == self.node_id:
                    if self.current_leader != self.node_id:
                        logger.info(f"[LeaderElection] Nodo {self.node_id} es el de mayor ID. Iniciando elección para convertirse en líder.")
                        is_leader = await self._start_election(all_nodes)
                        if is_leader:
                            self._become_leader()
                else:
                    # 4. Si no soy yo, verificar si el líder actual sigue vivo
                    if self.current_leader != potential_leader:
                        # El líder ha cambiado según el descubrimiento
                        self.current_leader = potential_leader
                        if self.on_leader_changed_callback:
                            self.on_leader_changed_callback(potential_leader)
                        logger.info(f"[LeaderElection] Nuevo líder identificado: {potential_leader}")

                    # Verificar la salud del líder actual
                    leader_status = self.health_agent.get_node_status(potential_leader)
                    if leader_status != "ALIVE":
                        logger.warning(f"[LeaderElection] Líder {potential_leader} no responde. Iniciando elección.")
                        is_leader = await self._start_election(all_nodes)
                        if is_leader:
                            self._become_leader()

                await asyncio.sleep(3) # Revisar cada 3 segundos

            except Exception as e:
                logger.error(f"[LeaderElection] Error en el monitoreo: {e}")
                await asyncio.sleep(5)

    async def _start_election(self, all_nodes: List[str]) -> bool:
        """
        Inicia el proceso de elección de Bully.
        Devuelve True si este nodo se convierte en líder.
        """
        logger.info(f"[LeaderElection] Nodo {self.node_id} iniciando elección.")
        # Enviar mensaje ELECTION a todos los nodos con ID mayor
        higher_nodes = [n for n in all_nodes if n > self.node_id]
        if not higher_nodes:
            # No hay nodos con ID mayor, soy el líder
            logger.info(f"[LeaderElection] Nodo {self.node_id} no encontró nodos superiores. Se declara líder.")
            return True

        # Enviar ELECTION a nodos superiores
        # (Nota: Aquí asumimos que tienes un mecanismo para enviar mensajes a nodos específicos, como NetAgent)
        # Por ahora, simulamos que enviamos los mensajes y esperamos respuestas.
        # En una implementación real, registrarías estos mensajes y esperarías respuestas COORDINATOR o ELECTION.

        # Simulación: esperar un poco y asumir que no hubo respuesta (los nodos superiores están caídos)
        await asyncio.sleep(self.election_timeout)

        # Verificar nuevamente si hay nodos superiores activos
        all_nodes_now = [entry.node_id for entry in self.discover_agent.rt.all_entries()]
        all_nodes_now.append(self.node_id)
        all_nodes_now = list(set(all_nodes_now))
        higher_nodes_now = [n for n in all_nodes_now if n > self.node_id]

        if not higher_nodes_now:
            logger.info(f"[LeaderElection] Nodo {self.node_id} confirma que no hay nodos superiores activos. Se convierte en líder.")
            return True
        else:
            logger.info(f"[LeaderElection] Nodo {self.node_id} detecta nodos superiores activos. No es líder.")
            return False

    def _become_leader(self):
        """Este nodo se convierte en el nuevo líder."""
        self.current_leader = self.node_id
        logger.info(f"[LeaderElection] ¡Nodo {self.node_id} se ha convertido en el LÍDER!")
        # Notificar a los callbacks
        self.on_become_leader_callback()
        if self.on_leader_changed_callback:
            self.on_leader_changed_callback(self.node_id)

    def get_current_leader(self) -> Optional[str]:
        """Devuelve el ID del líder actual."""
        return self.current_leader