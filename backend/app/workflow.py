from datetime import datetime, timezone
import logging

from fastapi import HTTPException

from .agents import ComplexityAgent, ImplementationAgent, PlanningAgent, RecommendationAgent, RequirementAgent
from .config import Settings
from .integrations import JiraClient, RepositoryClient
from .llm import ModelGateway
from .models import ImplementationResult, TestResult, Workflow, WorkflowState
from .store import WorkflowStore

logger = logging.getLogger(__name__)


class Orchestrator:
    def __init__(self, store: WorkflowStore, settings: Settings) -> None:
        self.store = store
        self.settings = settings
        self.jira = JiraClient(settings)
        self.repository = RepositoryClient(settings)
        self.gateway = ModelGateway(settings)
        self.requirements = RequirementAgent()
        self.complexity = ComplexityAgent()
        self.recommendations = RecommendationAgent()
        self.planning = PlanningAgent()

    def create(self, jira_key: str) -> Workflow:
        return self.store.create(Workflow(jira_key=jira_key.upper()))

    async def analyze(self, workflow_id: str) -> Workflow:
        workflow = self.store.get(workflow_id)
        self._require(workflow, {WorkflowState.NEW})
        task = await self.jira.fetch_issue(workflow.id, workflow.jira_key)
        workflow.jira_task = task
        workflow.state = WorkflowState.JIRA_RETRIEVED
        workflow.requirement_analysis = self.requirements.analyze(task)
        workflow.complexity = self.complexity.assess(task)
        workflow.recommendation = self.recommendations.recommend(workflow.complexity, bool(self.settings.gemini_api_key))
        workflow.state = WorkflowState.ANALYZED
        self._audit(workflow, "requirement-and-complexity", "completed")
        return self.store.save(workflow)

    def select_model(self, workflow_id: str, model_id: str) -> Workflow:
        workflow = self.store.get(workflow_id)
        self._require(workflow, {WorkflowState.ANALYZED})
        options = {item.id: item for item in workflow.recommendation.alternatives} if workflow.recommendation else {}
        if model_id not in options or not options[model_id].available:
            raise HTTPException(status_code=400, detail="Selected model is not configured and available.")
        workflow.selected_model = model_id
        workflow.state = WorkflowState.MODEL_SELECTED
        return self.store.save(workflow)

    def generate_plan(self, workflow_id: str, comment: str | None = None) -> Workflow:
        workflow = self.store.get(workflow_id)
        self._require(workflow, {WorkflowState.MODEL_SELECTED, WorkflowState.PLAN_CHANGES_REQUESTED})
        if not workflow.jira_task:
            raise HTTPException(status_code=409, detail="Jira task is required before planning.")
        workflow.plans.append(self.planning.plan(workflow.jira_task, len(workflow.plans) + 1, comment))
        workflow.state = WorkflowState.PLAN_GENERATED
        return self.store.save(workflow)

    def approve_plan(self, workflow_id: str) -> Workflow:
        workflow = self.store.get(workflow_id)
        self._require(workflow, {WorkflowState.PLAN_GENERATED})
        workflow.state = WorkflowState.PLAN_APPROVED
        return self.store.save(workflow)

    def request_plan_changes(self, workflow_id: str, comment: str) -> Workflow:
        workflow = self.store.get(workflow_id)
        self._require(workflow, {WorkflowState.PLAN_GENERATED})
        if not comment.strip():
            raise HTTPException(status_code=400, detail="A change request comment is required.")
        workflow.state = WorkflowState.PLAN_CHANGES_REQUESTED
        return self.store.save(workflow)

    async def implement(self, workflow_id: str) -> Workflow:
        workflow = self.store.get(workflow_id)
        self._require(workflow, {WorkflowState.PLAN_APPROVED})
        if not workflow.jira_task:
            raise HTTPException(status_code=409, detail="Jira task is required before implementation.")
        workflow.repository_analysis = self.repository.analyze()
        workflow.state = WorkflowState.REPOSITORY_ANALYZED
        branch = self.repository.create_branch(workflow.jira_task.key, workflow.jira_task.summary)
        if not workflow.plans or not workflow.selected_model:
            raise HTTPException(status_code=409, detail="An approved plan and selected model are required before implementation.")
        agent = ImplementationAgent(self.gateway.provider(workflow.selected_model))
        changes, summary = await agent.generate(workflow.jira_task, workflow.plans[-1], workflow.repository_analysis)
        changed_files = self.repository.write_files(changes)
        validation_status, validation_summary = self.repository.validate()
        workflow.implementation = ImplementationResult(branch=branch, changed_files=changed_files, diff_summary=f"{summary}\n\n{self.repository.diff_summary()}", validation_status=validation_status, validation_summary=validation_summary)
        workflow.state = WorkflowState.VALIDATION_COMPLETED if validation_status == "PASS" else WorkflowState.FAILED
        self._audit(workflow, "implementation", validation_status.lower())
        return self.store.save(workflow)

    def verify(self, workflow_id: str, approved: bool, comment: str | None) -> Workflow:
        workflow = self.store.get(workflow_id)
        self._require(workflow, {WorkflowState.VALIDATION_COMPLETED})
        if not approved and not (comment or "").strip():
            raise HTTPException(status_code=400, detail="A verification comment is required when reporting an issue.")
        workflow.verification_comment = comment
        workflow.state = WorkflowState.HUMAN_VERIFIED if approved else WorkflowState.IMPLEMENTATION_CHANGES_REQUESTED
        return self.store.save(workflow)

    def tests(self, workflow_id: str) -> Workflow:
        workflow = self.store.get(workflow_id)
        self._require(workflow, {WorkflowState.HUMAN_VERIFIED})
        status, passed, failed, command, summary = self.repository.run_tests()
        generated = [path for path in (workflow.implementation.changed_files if workflow.implementation else []) if "test" in path.lower()]
        workflow.test_result = TestResult(generated_tests=generated, executed_command=command, passed=passed, failed=failed, status=status, summary=summary)
        if status == "PASS":
            commit_message = f"{workflow.jira_task.key if workflow.jira_task else workflow.jira_key}: {workflow.jira_task.summary if workflow.jira_task else 'implement approved change'}"
            workflow.implementation.commit = self.repository.commit(commit_message) if workflow.implementation else None
            workflow.state = WorkflowState.TESTS_COMPLETED
        else:
            workflow.state = WorkflowState.FAILED
        self._audit(workflow, "tests", status.lower())
        return self.store.save(workflow)

    async def create_pr(self, workflow_id: str) -> Workflow:
        workflow = self.store.get(workflow_id)
        self._require(workflow, {WorkflowState.TESTS_COMPLETED})
        if not workflow.jira_task or not workflow.implementation:
            raise HTTPException(status_code=409, detail="Implemented Jira task details are required before PR creation.")
        body = f"## {workflow.jira_task.key}\n\n{workflow.jira_task.summary}\n\n### Testing\n{workflow.test_result.summary if workflow.test_result else 'Not recorded'}"
        workflow.pull_request = await self.repository.create_pull_request(workflow.jira_task.summary, body)
        workflow.state = WorkflowState.PR_CREATED
        self._audit(workflow, "pull-request", "created")
        return self.store.save(workflow)

    @staticmethod
    def _require(workflow: Workflow, expected: set[WorkflowState]) -> None:
        if workflow.state not in expected:
            states = ", ".join(state.value for state in expected)
            raise HTTPException(status_code=409, detail=f"Action requires state: {states}. Current state: {workflow.state.value}.")

    @staticmethod
    def _audit(workflow: Workflow, action: str, status: str) -> None:
        event = {"timestamp": datetime.now(timezone.utc).isoformat(), "agent": "orchestrator", "action": action, "status": status}
        workflow.audit_log.append(event)
        logger.info("workflow_event workflow_id=%s jira_key=%s action=%s status=%s", workflow.id, workflow.jira_key, action, status)
