import argparse
import asyncio
from .main import DiscoverAgent

def parse_peers(peers_str):
    # peers_str like "127.0.0.1:9001,127.0.0.1:9002"
    peers = []
    if not peers_str:
        return peers
    for p in peers_str.split(','):
        host, port = p.split(':')
        peers.append((host, int(port)))
    return peers

async def run_node(node_id, port, peers):
    agent = DiscoverAgent(node_id=node_id, listen_port=port, peers=peers)
    await agent.start()
    # run forever
    while True:
        await asyncio.sleep(3600)

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
