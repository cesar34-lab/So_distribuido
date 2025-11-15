# test_scheduler.py
import pytest
import asyncio
from agents.scheduler_d.scheduler import SchedulerD
from agents.scheduler_d.monitor import monitor_task

class FakeDiscover:
    def __init__(self):
        self.nodes = [
            {"node_id":"rescue", "cpu":1, "ram":1, "reputacion":1, "rtt":100, "score":1.0}
        ]
    def buscar(self, tags):
        return self.nodes

@pytest.mark.asyncio
async def test_task_submission_and_monitor(monkeypatch):
    scheduler = SchedulerD(FakeDiscover())
    task_id = await scheduler.submit_task("binary_hash1", {"cpu":1}, [])

    task = scheduler.tasks[task_id]
    assert task["status"] in ["ASSIGNED", "PENDING"]

    # Simular fallo del nodo
    monkeypatch.setattr("agents.scheduler_d.node_status.is_node_alive", lambda x: False)
    await monitor_task(task, scheduler, test_mode=True)

    # Después de monitor, tarea debe ser reasignada
    reassigned_task = scheduler.tasks[list(scheduler.tasks.keys())[-1]]
    assert reassigned_task["assigned_node"] == "rescue"
