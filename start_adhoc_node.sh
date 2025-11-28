#!/bin/bash
#
# Script para iniciar un nodo del Sistema Operativo Descentralizado
# en AWS EC2 (simulando red Ad hoc via IP directa).
#
# Uso:
#   ./start_adhoc_node.sh <ID_DEL_NODO> <PUERTO_LOCAL> "<PEERS_IP:PUERTO,...>"
#
# Ejemplo:
#   ./start_adhoc_node.sh nodo_maestro 10000 "172.31.10.11:10000,172.31.10.12:10000"
#   (Ajustando IPs al CIDR de tu VPC/subred de AWS)

if [ -z "$1" ] || [ -z "$2" ] || [ -z "$3" ]; then
  echo "Error: Debes proporcionar ID del nodo, puerto local y peers."
  echo "Uso: $0 <ID_DEL_NODO> <PUERTO_LOCAL> \"<PEERS_IP:PUERTO,...>\""
  echo "Ejemplo: $0 nodo_maestro 10000 \"192.168.10.51:10000,192.168.10.52:10000,192.168.10.37:10000\""
  exit 1
fi

NODE_ID="$1"
NODE_PORT="$2"
NODE_PEERS="$3"

echo "Iniciando nodo con ID: $NODE_ID, Puerto: $NODE_PORT, Peers: $NODE_PEERS"

# --- NO hay configuración de red Ad hoc aquí, ya que usamos la VPC de AWS ---

# --- Iniciar el nodo con Docker Compose ---
export NODE_ID=$NODE_ID
export NODE_PORT=$NODE_PORT
export NODE_PEERS=$NODE_PEERS

# Asegúrate de que el compose file use network_mode: "host" o exponga los puertos necesarios
# Si usas host, los puertos del contenedor se mapean directamente al host.
# Si usas puertos mapeados, debes ajustar las IPs/ports de los peers en consecuencia.
# Para esta guía, asumiremos network_mode: "host".

# Usamos 'docker compose' en lugar de 'docker-compose'