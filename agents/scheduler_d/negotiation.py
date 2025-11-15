# scheduler_d/negotiation.py
import asyncio
from random import choice

async def negotiate_with_candidates(task, candidates):
    """
    Flujo simplificado:
    1. Enviar PROPUESTA a cada candidato
    2. Esperar respuesta ACK/RECHAZAR (simulado)
    3. Seleccionar mejor candidato
    """
    # Simulación asincrónica de respuestas
    await asyncio.sleep(0.5)  # tiempo de negociación
    accepted = [c for c in candidates if c.get("available", True)]
    if not accepted:
        return None
    # Selecciona candidato con mejor score
    winner = max(accepted, key=lambda x: x.get("score", 0))
    return winner["node_id"]
