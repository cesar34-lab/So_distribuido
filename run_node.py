# So_distribuido/run_node.py (Versión modificada y testeable)

import argparse
import asyncio
from agents.net.net_agent import NetAgent
from agents.health.health import HealthAgent
from agents.discover.main import DiscoverAgent
from agents.store_d.store import StoreD
from agents.scheduler_d.scheduler import SchedulerD
from agents.leader_election.leader_election import LeaderElectionAgent

def parse_peers(peers_str):
    if not peers_str:
        return []
    peers = []
    for p in peers_str.split(','):
        host, port = p.split(':')
        peers.append((host, int(port)))
    return peers

def on_node_down(node_id):
    print(f"[Node Runner] Nodo {node_id} ha caído.")

def on_become_leader():
    print(f"[Node Runner] ¡Este nodo se ha convertido en el LÍDER!")
    # Aquí podrías iniciar servicios específicos del líder, como un coordinador centralizado temporal.

def on_leader_changed(new_leader_id):
    print(f"[Node Runner] El nuevo líder es: {new_leader_id}")

async def run_node(node_id, port, peers, test_mode=False):
    print(f"Iniciando nodo {node_id} en puerto {port}")

    # 1. Crear NetAgent (base de comunicación)
    net_agent = NetAgent(node_id=node_id, listen_host='127.0.0.1', listen_port=port)

    # 2. Crear HealthAgent
    health_agent = HealthAgent(node_id=node_id, on_node_down_callback=on_node_down, net_agent=net_agent)

    # 3. Crear DiscoverAgent (usa NetAgent)
    discover_agent = DiscoverAgent(node_id=node_id, net_agent=net_agent, peers=peers)

    # 4. Crear StoreD (usa NetAgent)
    store_agent = StoreD(node_id=node_id, net_agent=net_agent, storage_dir=f"store_{node_id}")

    # 5. Crear SchedulerD (usa DiscoverAgent, StoreD, NetAgent)
    scheduler_agent = SchedulerD(discover_agent=discover_agent, store_agent=store_agent, net_agent=net_agent)
    scheduler_agent.set_health_agent(health_agent)

    # 6. Crear LeaderElectionAgent
    leader_election_agent = LeaderElectionAgent(
        node_id=node_id,
        discover_agent=discover_agent,
        health_agent=health_agent,
        on_become_leader_callback=on_become_leader,
        on_leader_changed_callback=on_leader_changed,
        election_timeout=2.0
    )

    # 7. Iniciar NetAgent
    await net_agent.start()

    # 8. Iniciar HealthAgent
    health_agent.start()

    # 9. Iniciar DiscoverAgent
    await discover_agent.start()

    # 10. Iniciar LeaderElectionAgent
    leader_election_agent.start()

    # 11. Iniciar tareas de limpieza para StoreD (simulado con una tarea periódica)
    async def gc_task():
        while True:
            await asyncio.sleep(300 if not test_mode else 1) # Cada 5 minutos o 1 segundo en test
            store_agent.garbage_collect()

    asyncio.create_task(gc_task())

    print(f"[{node_id}] Todos los agentes principales iniciados.")

    # 12. Mantener el nodo corriendo
    try:
        iteration_count = 0
        while True:
            # En modo test, salir después de unas pocas iteraciones
            if test_mode and iteration_count >= 3:
                print(f"[{node_id}] Modo test: Saliendo del bucle principal.")
                break
            await asyncio.sleep(3600 if not test_mode else 0.1) # Dormir 1h o 0.1s en test
            iteration_count += 1
    except KeyboardInterrupt:
        print(f"\n[{node_id}] Cerrando agentes...")
        leader_election_agent.stop()
        health_agent.stop()
        await net_agent.stop()

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--id", required=True, help="Node ID")
    parser.add_argument("--port", required=True, type=int, help="UDP listen port")
    parser.add_argument("--peers", help="comma separated host:port list")
    args = parser.parse_args()
    peers = parse_peers(args.peers)
    asyncio.run(run_node(args.id, args.port, peers))

if __name__ == "__main__":
    main()