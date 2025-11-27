#!/bin/bash
#
# Script para iniciar un nodo del Sistema Operativo Descentralizado
# en una red Ad hoc.
#
# Uso:
#   ./start_adhoc_node.sh <ID_DEL_NODO>
#
# Ejemplo:
#   ./start_adhoc_node.sh nodo_maestro
#   ./start_adhoc_node.sh nodo_trabajador_1

if [ -z "$1" ]; then
  echo "Error: Debes proporcionar un ID de nodo."
  echo "Uso: $0 <ID_DEL_NODO>"
  exit 1
fi

NODE_ID="$1"
NODE_PORT="10000" # Puerto por defecto, puedes cambiarlo

# --- Configuración de la Red Ad hoc (ejemplo para Linux con iwconfig) ---
# AJUSTA ESTOS PARÁMETROS A TU TARJETA DE RED Y CONFIGURACIÓN DESEADA
WIFI_INTERFACE="wlan0"
ADHOC_SSID="SO-Descentralizado"
ADHOC_CHANNEL="6"

echo "Configurando la interfaz $WIFI_INTERFACE en modo Ad hoc..."
sudo iwconfig $WIFI_INTERFACE mode ad-hoc essid $ADHOC_SSID channel $ADHOC_CHANNEL
sudo ip link set $WIFI_INTERFACE up
echo "Interfaz $WIFI_INTERFACE configurada."

# --- Iniciar el nodo con Docker Compose ---
echo "Iniciando el nodo del Sistema Operativo Descentralizado con ID: $NODE_ID"
export NODE_ID=$NODE_ID
export NODE_PORT=$NODE_PORT
# Si conoces los peers al momento de iniciar, puedes definirlos aquí
# export NODE_PEERS="192.168.1.10:10000"

docker-compose -f docker-compose.adhoc.yml up -d

echo "¡Nodo iniciado! Verifica su estado con:"
echo "  docker logs so_nodo"
echo "  curl http://localhost:10000/estado"