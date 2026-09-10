import pytest
from fastapi import HTTPException
from pathlib import Path

from app.config import Settings
from app.agents import ImplementationAgent
from app.models import WorkflowState
from app.store import WorkflowStore
from app.workflow import Orchestrator


def orchestrator_for(tmp_path: Path, settings: Settings | None = None) -> Orchestrator:
    return Orchestrator(WorkflowStore(tmp_path / "workflows.json"), settings or Settings())


def test_workflow_starts_new(tmp_path: Path) -> None:
    workflow = orchestrator_for(tmp_path).create("DEMO-21")
    assert workflow.jira_key == "DEMO-21"
    assert workflow.state == WorkflowState.NEW


def test_model_selection_requires_analysis(tmp_path: Path) -> None:
    orchestrator = orchestrator_for(tmp_path)
    workflow = orchestrator.create("DEMO-21")
    with pytest.raises(HTTPException) as error:
        orchestrator.select_model(workflow.id, "gemini")
    assert error.value.status_code == 409


@pytest.mark.asyncio
async def test_analysis_reports_missing_jira_configuration(tmp_path: Path) -> None:
    settings = Settings(jira_base_url=None, jira_username=None, jira_api_token=None)
    orchestrator = orchestrator_for(tmp_path, settings)
    workflow = orchestrator.create("DEMO-21")
    with pytest.raises(HTTPException) as error:
        await orchestrator.analyze(workflow.id)
    assert error.value.status_code == 503


def test_implementation_response_parses_json() -> None:
    response = ImplementationAgent._parse('{"summary":"Added endpoint", "files":[{"path":"app/main.py", "content":"print(1)"}]}')
    assert response["summary"] == "Added endpoint"


def test_workflow_store_survives_restart(tmp_path: Path) -> None:
    path = tmp_path / "workflows.json"
    workflow = orchestrator_for(tmp_path).create("DEMO-22")
    restored = WorkflowStore(path).get(workflow.id)
    assert restored.jira_key == "DEMO-22"
