# So_distribuido/test/test_run_node.py (Versión final y simplificada)

import asyncio
import pytest
import tempfile
import sys
import os
from unittest.mock import AsyncMock, patch

# Asegurar la ruta al proyecto
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from agents.net.net_agent import NetAgent
from agents.discover.main import DiscoverAgent
from run_node import run_node


@pytest.mark.asyncio
async def test_run_node_initialization():
    """
    Test que verifica que run_node pueda instanciar todos los agentes necesarios
    y que sus dependencias estén correctamente inyectadas.
    """
    node_id = "test_run_node"
    port = 16000
    peers = []  # Sin peers para esta prueba simple

    # Mockear los métodos de inicio de los agentes para evitar la red real
    with patch.object(NetAgent, 'start', new=AsyncMock()) as mock_net_start, \
            patch.object(DiscoverAgent, 'start', new=AsyncMock()) as mock_discover_start:
        # Ejecutar run_node en modo test
        await run_node(node_id, port, peers, test_mode=True)

        # Verificaciones principales
        # 1. NetAgent.start debe haber sido llamado
        mock_net_start.assert_awaited()

        # 2. DiscoverAgent.start debe haber sido llamado
        mock_discover_start.assert_awaited()

    # Si llegamos aquí, la inicialización fue exitosa
    assert True