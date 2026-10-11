"""Celery worker for asynchronous, governed remediation (requires the ``[worker]`` extra).

celery -A golden.ai.worker.celery_app worker --loglevel=INFO
"""

from __future__ import annotations

import os

from celery import Celery

from golden.ai.agents.executor import ExecutorAgent

REDIS_URL = os.getenv("REDIS_URL", "redis://localhost:6379/0")

app = Celery("golden_worker", broker=REDIS_URL, backend=REDIS_URL)
app.conf.update(
    result_expires=3600,
    task_serializer="json",
    accept_content=["json"],
    result_serializer="json",
    timezone="UTC",
    enable_utc=True,
    task_acks_late=True,
    worker_prefetch_multiplier=1,
    task_time_limit=300,
)


@app.task(name="golden.remediate")
def remediate(plan: dict) -> dict:
    """Execute a remediation plan through the ActionGovernor (caps, approvals, kill switch)."""
    return ExecutorAgent().execute(plan)
