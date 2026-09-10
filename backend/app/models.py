from datetime import datetime, timezone
from enum import Enum
from typing import Any
from uuid import uuid4

from pydantic import BaseModel, Field


class WorkflowState(str, Enum):
    NEW = "NEW"
    JIRA_RETRIEVED = "JIRA_RETRIEVED"
    ANALYZED = "ANALYZED"
    MODEL_SELECTED = "MODEL_SELECTED"
    PLAN_GENERATED = "PLAN_GENERATED"
    PLAN_CHANGES_REQUESTED = "PLAN_CHANGES_REQUESTED"
    PLAN_APPROVED = "PLAN_APPROVED"
    REPOSITORY_ANALYZED = "REPOSITORY_ANALYZED"
    IMPLEMENTATION_COMPLETED = "IMPLEMENTATION_COMPLETED"
    VALIDATION_COMPLETED = "VALIDATION_COMPLETED"
    HUMAN_VERIFIED = "HUMAN_VERIFIED"
    IMPLEMENTATION_CHANGES_REQUESTED = "IMPLEMENTATION_CHANGES_REQUESTED"
    TESTS_COMPLETED = "TESTS_COMPLETED"
    BRANCH_CREATED = "BRANCH_CREATED"
    PR_CREATED = "PR_CREATED"
    COMPLETED = "COMPLETED"
    FAILED = "FAILED"


class JiraTask(BaseModel):
    key: str
    summary: str
    description: str | None = None
    issue_type: str = "TASK"
    priority: str | None = None
    acceptance_criteria: list[str] = Field(default_factory=list)


class RequirementAnalysis(BaseModel):
    problem_summary: str
    functional_requirement: str
    acceptance_criteria: list[str]
    constraints: list[str] = Field(default_factory=list)
    ambiguities: list[str] = Field(default_factory=list)


class ComplexityAssessment(BaseModel):
    score: int = Field(ge=1, le=10)
    level: str
    explanation: str
    estimated_files: int


class ModelOption(BaseModel):
    id: str
    label: str
    provider: str
    available: bool
    estimated_tokens: int
    estimated_cost_usd: float | None = None


class ModelRecommendation(BaseModel):
    recommended_model: str
    alternatives: list[ModelOption]
    reason: str


class Plan(BaseModel):
    version: int
    objective: str
    affected_components: list[str]
    likely_files: list[str]
    implementation_steps: list[str]
    test_approach: list[str]
    risks: list[str]
    expected_result: str
    change_request: str | None = None


class RepositoryAnalysis(BaseModel):
    project_type: str
    relevant_directories: list[str]
    relevant_files: list[str]
    test_command: str | None = None
    notes: str


class ImplementationResult(BaseModel):
    branch: str
    changed_files: list[str]
    diff_summary: str
    validation_status: str
    validation_summary: str
    commit: str | None = None


class TestResult(BaseModel):
    generated_tests: list[str]
    executed_command: str
    passed: int
    failed: int
    status: str
    summary: str


class PullRequest(BaseModel):
    number: int
    title: str
    url: str
    status: str


class Workflow(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid4()))
    jira_key: str
    state: WorkflowState = WorkflowState.NEW
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    updated_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    error: str | None = None
    jira_task: JiraTask | None = None
    requirement_analysis: RequirementAnalysis | None = None
    complexity: ComplexityAssessment | None = None
    recommendation: ModelRecommendation | None = None
    selected_model: str | None = None
    plans: list[Plan] = Field(default_factory=list)
    repository_analysis: RepositoryAnalysis | None = None
    implementation: ImplementationResult | None = None
    verification_comment: str | None = None
    test_result: TestResult | None = None
    pull_request: PullRequest | None = None
    audit_log: list[dict[str, Any]] = Field(default_factory=list)


class CreateWorkflowRequest(BaseModel):
    jira_key: str = Field(min_length=2, max_length=64, pattern=r"^[A-Za-z][A-Za-z0-9_]*-\d+$")


class ModelSelectionRequest(BaseModel):
    model_id: str


class PlanRequest(BaseModel):
    comment: str | None = Field(default=None, max_length=2000)


class VerificationRequest(BaseModel):
    approved: bool
    comment: str | None = Field(default=None, max_length=2000)
