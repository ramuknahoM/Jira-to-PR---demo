from datetime import datetime, timezone

from fastapi import HTTPException

from .models import Workflow


class WorkflowStore:
    """Small in-memory store for the local MVP; replace with MongoDB behind this boundary."""

    def __init__(self) -> None:
        self._items: dict[str, Workflow] = {}

    def create(self, workflow: Workflow) -> Workflow:
        self._items[workflow.id] = workflow
        return workflow

    def get(self, workflow_id: str) -> Workflow:
        workflow = self._items.get(workflow_id)
        if not workflow:
            raise HTTPException(status_code=404, detail="Workflow not found")
        return workflow

    def save(self, workflow: Workflow) -> Workflow:
        workflow.updated_at = datetime.now(timezone.utc)
        self._items[workflow.id] = workflow
        return workflow
