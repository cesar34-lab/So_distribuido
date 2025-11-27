#!/bin/sh
#
# Script de arranque para el Sistema Operativo Descentralizado
# Este script se ejecutará automáticamente al iniciar el sistema.

echo "[BOOT] Iniciando Sistema Operativo Descentralizado..."

# Cambiar al directorio de la aplicación
cd /opt/so-descentralizado

# Instalar dependencias (opcional, si no están en la imagen de Buildroot)
# pip3 install -r requirements.txt

# Iniciar el nodo en segundo plano
# --- AJUSTA ESTOS PARÁMETROS SEGÚN TU CONFIGURACIÓN ---
# Por ejemplo, puedes leer el ID del nodo de una variable de entorno o de un archivo de configuración.
python3 run_node.py --id "nodo_adhoc_1" --port 10000 --peers "" &
NODO_PID=$!

echo "[BOOT] Nodo iniciado con PID $NODO_PID."

# Opcional: Esperar a que el nodo esté listo (consultar /estado vía curl)
# while ! curl -sf http://localhost:10000/estado > /dev/null 2>&1; do
#     echo "[BOOT] Esperando a que el nodo responda..."
#     sleep 2
# done
# echo "[BOOT] Nodo listo."

# Mantener el script en ejecución para que el sistema no se apague
# Esto es crucial para que el sistema operativo siga corriendo.
wait $NODO_PID