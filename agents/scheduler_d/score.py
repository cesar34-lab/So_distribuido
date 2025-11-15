# agents/scheduler_d/score.py
import math
import random

class ScoreCalculator:
    """
    Calcula el score de un nodo según sus características.
    El resultado está normalizado entre 0 y 1.
    """

    def __init__(self, w_cpu=0.3, w_ram=0.2, w_rep=0.3, w_rtt=0.2):
        """
        Pesos de los factores.
        Los pesos deben sumar 1.0.
        """
        self.w_cpu = w_cpu
        self.w_ram = w_ram
        self.w_rep = w_rep
        self.w_rtt = w_rtt

    # ----------------------------------------------------------------------
    # Cálculo individual de métricas
    # ----------------------------------------------------------------------

    def normalize(self, value, min_val, max_val):
        """Normaliza un valor al rango [0, 1]."""
        if max_val == min_val:
            return 0.0
        norm = (value - min_val) / (max_val - min_val)
        return max(0.0, min(1.0, norm))

    def cpu_score(self, cpu_usage):
        """Calcula score basado en carga de CPU (menor carga = mejor)."""
        return 1.0 - min(cpu_usage, 1.0)

    def ram_score(self, ram_usage):
        """Calcula score basado en uso de RAM (menor uso = mejor)."""
        return 1.0 - min(ram_usage, 1.0)

    def reputation_score(self, rep):
        """Normaliza reputación (entre 0 y 1)."""
        return max(0.0, min(rep, 1.0))

    def rtt_score(self, rtt):
        """
        Calcula score de RTT (menor latencia = mejor).
        Se normaliza considerando RTT entre 0 y 1000 ms.
        """
        max_rtt = 1000
        return 1.0 - self.normalize(rtt, 0, max_rtt)

    # ----------------------------------------------------------------------
    # Score global del nodo
    # ----------------------------------------------------------------------

    def calculate(self, cpu_usage, ram_usage, reputacion, rtt):
        """
        Calcula el score ponderado y lo normaliza entre 0 y 1.
        """
        s_cpu = self.cpu_score(cpu_usage)
        s_ram = self.ram_score(ram_usage)
        s_rep = self.reputation_score(reputacion)
        s_rtt = self.rtt_score(rtt)

        score = (
            self.w_cpu * s_cpu +
            self.w_ram * s_ram +
            self.w_rep * s_rep +
            self.w_rtt * s_rtt
        )

        return round(max(0.0, min(score, 1.0)), 3)

    # ----------------------------------------------------------------------
    # Selección del mejor nodo
    # ----------------------------------------------------------------------

    def choose_best_node(self, nodes):
        """
        Selecciona el nodo con el score más alto.
        nodes: dict[node_id] = {"cpu":..., "ram":..., "reputacion":..., "rtt":...}
        """
        best_node = None
        best_score = -math.inf
        scores = {}

        for node_id, data in nodes.items():
            s = self.calculate(
                cpu_usage=data.get("cpu", 0),
                ram_usage=data.get("ram", 0),
                reputacion=data.get("reputacion", 0),
                rtt=data.get("rtt", 500)
            )
            scores[node_id] = s
            if s > best_score:
                best_node = node_id
                best_score = s

        return best_node, scores

    # ----------------------------------------------------------------------
    # Simulación de dinámica del nodo
    # ----------------------------------------------------------------------

    def fluctuate_metrics(self, node):
        """
        Simula ligeras variaciones en los recursos del nodo para pruebas.
        """
        node["cpu"] = max(0.0, min(1.0, node["cpu"] + random.uniform(-0.1, 0.1)))
        node["ram"] = max(0.0, min(1.0, node["ram"] + random.uniform(-0.1, 0.1)))
        node["reputacion"] = max(0.0, min(1.0, node["reputacion"] + random.uniform(-0.05, 0.05)))
        node["rtt"] = max(10, min(1000, node["rtt"] + random.uniform(-50, 50)))
        return node
