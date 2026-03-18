"""
Redis-backed Task Store — PE Org-AI-R Platform
app/services/task_store.py

Stores background task state in Redis so it persists across server restarts.
Synchronous methods (matches existing RedisCache pattern).
"""

import json
import logging
from datetime import datetime, timezone
from typing import Any, Dict, Optional

logger = logging.getLogger(__name__)

TASK_TTL = 86400  # 24 hours


class TaskStore:
    """Redis-backed store for background task state."""

    def __init__(self, redis_client):
        self.client = redis_client

    def _key(self, task_id: str) -> str:
        return f"task:{task_id}"

    def create_task(self, task_id: str, metadata: Optional[Dict[str, Any]] = None) -> dict:
        """Create a new task entry with status='queued'."""
        task = {
            "task_id": task_id,
            "status": "queued",
            "started_at": datetime.now(timezone.utc).isoformat(),
            "completed_at": None,
            "progress": metadata.get("progress") if metadata else None,
            "result": None,
            "error": None,
        }
        if metadata:
            task.update({k: v for k, v in metadata.items() if k not in task})
        self.client.setex(self._key(task_id), TASK_TTL, json.dumps(task))
        return task

    def update_task(self, task_id: str, **updates) -> Optional[dict]:
        """Update an existing task. Returns updated dict or None if not found."""
        task = self.get_task(task_id)
        if task is None:
            return None
        task.update(updates)
        self.client.setex(self._key(task_id), TASK_TTL, json.dumps(task))
        return task

    def get_task(self, task_id: str) -> Optional[dict]:
        """Retrieve task state from Redis. Returns None if expired or missing."""
        data = self.client.get(self._key(task_id))
        if data is None:
            return None
        return json.loads(data)
