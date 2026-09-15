from __future__ import annotations

from ..config_loader import AppConfig
from ..models import JiraTask, Plan, RepositoryAnalysis, ScopeAnalysis


class PlanningAgent:
    def __init__(self, config: AppConfig) -> None:
        self.config = config

    def plan(
        self,
        task: JiraTask,
        repository: RepositoryAnalysis | None,
        version: int = 1,
        scope_analysis: ScopeAnalysis | None = None,
    ) -> Plan:
        risks = ["Confirm endpoint naming and response shape against existing conventions."]
        change_request = scope_analysis.pattern_summary if scope_analysis else None
        if scope_analysis and scope_analysis.already_implemented:
            reason = scope_analysis.already_implemented_reason or "The requested behavior may already exist."
            risks.insert(0, f"Possible duplicate work: {reason}")
        return Plan(
            version=version,
            objective=task.summary,
            affected_components=["Target application API", "Target application tests"],
            likely_files=repository.relevant_files[:4] if repository and repository.relevant_files else ["Existing route/controller module", "Existing test module"],
            implementation_steps=[
                "Inspect the matching application route and test conventions.",
                "Create the smallest implementation matching the accepted requirement.",
                "Add focused unit coverage and run the configured validation commands.",
            ],
            test_approach=[
                "Add a positive behavior test.",
                "Add an invalid-input or error-path test when the endpoint has inputs.",
            ],
            risks=risks,
            expected_result="The ticket behavior is implemented, validated, and ready for review.",
            change_request=change_request,
        )

    def build_prompt(self, task: JiraTask, repository: RepositoryAnalysis | None) -> str:
        template_path = self.config.agents.agents.get("planning", {}).get("prompt_template_path", "prompts/planning.txt")
        template = self.config.load_prompt(template_path)
        return template.format(
            key=task.key,
            summary=task.summary,
            description=task.description or "No additional description.",
            acceptance_criteria=", ".join(task.acceptance_criteria),
            project_type=repository.project_type if repository else "Git repository",
            relevant_files=", ".join(repository.relevant_files if repository else []),
        )
