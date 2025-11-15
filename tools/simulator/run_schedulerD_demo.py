import asyncio
import random
from agents.scheduler_d.scheduler import SchedulerD
from agents.scheduler_d.score import ScoreCalculator
import agents.scheduler_d.node_status as node_status


# ---------------------------------------------------------------------
# Simulador de entorno distribuido para probar el Scheduler-D
# ---------------------------------------------------------------------
class SimulatedDiscover:
    def __init__(self, nodes_count=5):
        self.nodes = {}
        for i in range(nodes_count):
            self.nodes[f"node{i+1}"] = {
                "cpu": round(random.uniform(0.2, 0.9), 2),
                "ram": round(random.uniform(0.3, 0.9), 2),
                "reputacion": round(random.uniform(0.4, 1.0), 2),
                "rtt": random.randint(20, 300),
            }

    def buscar(self, tags):
        """Devuelve todos los nodos disponibles."""
        return self.nodes

    def fluctuar(self):
        """Simula variaciones leves en las métricas de cada nodo."""
        calc = ScoreCalculator()
        for node_id in self.nodes:
            self.nodes[node_id] = calc.fluctuate_metrics(self.nodes[node_id])


# ---------------------------------------------------------------------
# Función principal del simulador
# ---------------------------------------------------------------------
async def simulate_scheduler_d(n_tasks=15, n_nodes=5, failure_rate=0.2):
    print("\n===== 🚀 Simulador del Scheduler-D =====")

    # Crear Discover simulado
    discover = SimulatedDiscover(nodes_count=n_nodes)
    scheduler = SchedulerD(discover)
    score_calc = ScoreCalculator()

    # Monkeypatch para simular fallos aleatorios
    def is_node_alive_sim(node_id):
        # 20% de probabilidad de fallo
        return random.random() > failure_rate

    node_status.is_node_alive = is_node_alive_sim

    # -----------------------------------------------------------------
    # Enviar tareas simuladas
    # -----------------------------------------------------------------
    print(f"\n📦 Enviando {n_tasks} tareas...\n")
    task_ids = []
    for i in range(n_tasks):
        binary_hash = f"binary_{i+1}"
        resources = {"cpu": 1, "ram": 1}
        tid = await scheduler.submit_task(binary_hash, resources, tags=["test"])
        task_ids.append(tid)

        # Mostrar score de cada nodo
        best_node, scores = score_calc.choose_best_node(discover.buscar([]))
        print(f"Tarea {tid[:8]} asignada inicialmente a {best_node} | Scores: {scores}")

        await asyncio.sleep(0.05)

    # -----------------------------------------------------------------
    # Simulación dinámica
    # -----------------------------------------------------------------
    print("\n⚙️ Iniciando monitoreo de tareas...\n")

    for _ in range(5):  # 5 ciclos de fluctuación
        discover.fluctuar()
        await asyncio.sleep(0.2)

    # Esperar para que los monitores terminen
    await asyncio.sleep(1.0)

    # -----------------------------------------------------------------
    # Mostrar resultados finales
    # -----------------------------------------------------------------
    completed = 0
    failed = 0
    reassigned = 0

    print("\n===== 📊 RESULTADOS FINALES =====")
    for tid in task_ids:
        task = scheduler.tasks[tid]
        node = task["assigned_node"]
        status = task["status"]
        print(f"Tarea {tid[:8]} | nodo={node} | estado={status}")

        if status == "COMPLETED":
            completed += 1
        elif status == "FAILED":
            failed += 1
        if node == "rescue":
            reassigned += 1

    print("\n===== 🧾 ESTADÍSTICAS =====")
    print(f"Tareas completadas: {completed}")
    print(f"Tareas fallidas: {failed}")
    print(f"Tareas reasignadas a 'rescue': {reassigned}")
    print("======================================\n")


# ---------------------------------------------------------------------
# Ejecución principal
# ---------------------------------------------------------------------
if __name__ == "__main__":
    try:
        asyncio.run(simulate_scheduler_d(n_tasks=15, n_nodes=5, failure_rate=0.25))
    except KeyboardInterrupt:
        print("\nSimulación interrumpida por el usuario.")
