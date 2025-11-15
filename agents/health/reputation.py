# agents/health/reputation.py

import time
from typing import Dict

class ReputationSystem:
    def __init__(self, initial_reputation: float = 0.5, decay_factor_per_second: float = 0.999997): # Aprox 0.99 por hora
        """
        Inicializa el sistema de reputación.

        Args:
            initial_reputation (float): Valor inicial de reputación para nuevos nodos.
            decay_factor_per_second (float): Factor por segundo para decaer la reputación.
                                             Ej: 0.999997 ^ (3600 s) ~= 0.99
        """
        self.initial_reputation = initial_reputation
        self.decay_factor_per_second = decay_factor_per_second
        self.node_reputations: Dict[str, float] = {}
        self.last_decay_time = time.time()

    def _apply_decay(self):
        """Aplica decaimiento a todas las reputaciones basado en el tiempo transcurrido."""
        current_time = time.time()
        elapsed = current_time - self.last_decay_time
        if elapsed > 0:
            decay_multiplier = self.decay_factor_per_second ** elapsed
            for node_id in self.node_reputations:
                self.node_reputations[node_id] *= decay_multiplier
                # Asegurar límites
                self.node_reputations[node_id] = max(0.0, min(1.0, self.node_reputations[node_id]))
            self.last_decay_time = current_time

    def update_on_success(self, node_id: str, score_delta: float = 0.1):
        """
        Actualiza la reputación de un nodo por un evento exitoso.

        Args:
            node_id (str): ID del nodo.
            score_delta (float): Cuánto incrementar la reputación (debe ser positivo).
        """
        self._apply_decay()
        if node_id not in self.node_reputations:
            self.node_reputations[node_id] = self.initial_reputation
        self.node_reputations[node_id] += score_delta
        # Asegurar límites
        self.node_reputations[node_id] = max(0.0, min(1.0, self.node_reputations[node_id]))
        print(f"[ReputationSystem] Reputación de {node_id} actualizada por éxito: {self.node_reputations[node_id]:.3f}")

    def update_on_failure(self, node_id: str, score_delta: float = -0.2):
        """
        Actualiza la reputación de un nodo por un evento fallido.

        Args:
            node_id (str): ID del nodo.
            score_delta (float): Cuánto decrementar la reputación (debe ser negativo).
        """
        self._apply_decay()
        if node_id not in self.node_reputations:
            self.node_reputations[node_id] = self.initial_reputation
        self.node_reputations[node_id] += score_delta
        # Asegurar límites
        self.node_reputations[node_id] = max(0.0, min(1.0, self.node_reputations[node_id]))
        print(f"[ReputationSystem] Reputación de {node_id} actualizada por fracaso: {self.node_reputations[node_id]:.3f}")

    def get_reputation(self, node_id: str) -> float:
        """
        Obtiene la reputación actual de un nodo.

        Args:
            node_id (str): ID del nodo.

        Returns:
            float: Reputación (0.0 a 1.0).
        """
        self._apply_decay() # Aplicar decaimiento antes de devolver
        return self.node_reputations.get(node_id, self.initial_reputation)

    def reset_reputation(self, node_id: str):
        """
        Reinicia la reputación de un nodo a su valor inicial.

        Args:
            node_id (str): ID del nodo.
        """
        self.node_reputations[node_id] = self.initial_reputation
        print(f"[ReputationSystem] Reputación de {node_id} reiniciada a {self.initial_reputation:.3f}")
