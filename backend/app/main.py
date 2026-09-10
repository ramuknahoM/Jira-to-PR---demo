import logging
from pathlib import Path

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from .config import get_settings
from .models import CreateWorkflowRequest, ModelSelectionRequest, PlanRequest, VerificationRequest, WorkflowState
from .store import WorkflowStore
from .workflow import Orchestrator

log_directory = Path(__file__).resolve().parents[1] / "logs"
log_directory.mkdir(exist_ok=True)
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(name)s %(message)s",
    handlers=[logging.StreamHandler(), logging.FileHandler(log_directory / "aidlc.log", encoding="utf-8")],
    force=True,
)

app = FastAPI(title="AIDLC Demo API", version="0.1.0")
app.add_middleware(CORSMiddleware, allow_origins=["http://localhost:5173"], allow_credentials=True, allow_methods=["*"], allow_headers=["*"])
store = WorkflowStore()
orchestrator = Orchestrator(store, get_settings())


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}


@app.get("/api/providers/gemini/models")
async def gemini_models() -> dict[str, list[str]]:
    return {"models": await orchestrator.gateway.available_models("gemini")}


@app.post("/api/workflows")
def create_workflow(request: CreateWorkflowRequest):
    return orchestrator.create(request.jira_key)


@app.get("/api/workflows/{workflow_id}")
def get_workflow(workflow_id: str):
    return store.get(workflow_id)


@app.post("/api/workflows/{workflow_id}/analyze")
async def analyze(workflow_id: str):
    return await orchestrator.analyze(workflow_id)


@app.post("/api/workflows/{workflow_id}/model-selection")
def select_model(workflow_id: str, request: ModelSelectionRequest):
    return orchestrator.select_model(workflow_id, request.model_id)


@app.post("/api/workflows/{workflow_id}/plan")
def generate_plan(workflow_id: str, request: PlanRequest):
    return orchestrator.generate_plan(workflow_id, request.comment)


@app.post("/api/workflows/{workflow_id}/approve-plan")
def approve_plan(workflow_id: str):
    return orchestrator.approve_plan(workflow_id)


@app.post("/api/workflows/{workflow_id}/plan-changes")
def request_plan_changes(workflow_id: str, request: PlanRequest):
    return orchestrator.request_plan_changes(workflow_id, request.comment or "")


@app.post("/api/workflows/{workflow_id}/implementation")
async def implementation(workflow_id: str):
    return await orchestrator.implement(workflow_id)


@app.post("/api/workflows/{workflow_id}/verification")
def verification(workflow_id: str, request: VerificationRequest):
    return orchestrator.verify(workflow_id, request.approved, request.comment)


@app.post("/api/workflows/{workflow_id}/tests")
def tests(workflow_id: str):
    return orchestrator.tests(workflow_id)


@app.post("/api/workflows/{workflow_id}/pr")
async def create_pr(workflow_id: str):
    return await orchestrator.create_pr(workflow_id)


@app.get("/api/workflows/{workflow_id}/report")
def report(workflow_id: str):
    workflow = store.get(workflow_id)
    if workflow.state not in {WorkflowState.PR_CREATED, WorkflowState.COMPLETED}:
        return {"status": "incomplete", "workflow": workflow}
    return {"status": "complete", "workflow": workflow}
