import json
import re
from dataclasses import dataclass

from fastapi import HTTPException

from .llm import LLMProvider
from .models import ComplexityAssessment, JiraTask, ModelOption, ModelRecommendation, Plan, RequirementAnalysis, RepositoryAnalysis


class RequirementAgent:
    def analyze(self, task: JiraTask) -> RequirementAnalysis:
        criteria = task.acceptance_criteria or [f"The behavior described by '{task.summary}' is available to callers."]
        ambiguity = [] if task.description else ["The ticket has no description beyond its summary."]
        return RequirementAnalysis(problem_summary=task.summary, functional_requirement=task.description or task.summary, acceptance_criteria=criteria, constraints=["Preserve existing repository conventions."], ambiguities=ambiguity)


class ComplexityAgent:
    def assess(self, task: JiraTask) -> ComplexityAssessment:
        text = f"{task.summary} {task.description or ''}".lower()
        score = 2 + (2 if any(word in text for word in ("database", "migration", "integration")) else 0) + (1 if "api" in text or "endpoint" in text else 0)
        score = min(score, 10)
        level = "LOW" if score <= 3 else "MEDIUM" if score <= 6 else "HIGH"
        return ComplexityAssessment(score=score, level=level, estimated_files=1 if score <= 3 else 3, explanation=f"{level.title()} complexity based on the apparent API, integration, and data-change scope in the ticket.")


class RecommendationAgent:
    def recommend(self, complexity: ComplexityAssessment, gemini_available: bool) -> ModelRecommendation:
        options = [
            ModelOption(id="gemini", label="Gemini Flash", provider="gemini", available=gemini_available, estimated_tokens=6000 if complexity.score <= 3 else 14000, estimated_cost_usd=0.01 if complexity.score <= 3 else 0.03),
            ModelOption(id="openai", label="OpenAI (connector ready)", provider="openai", available=False, estimated_tokens=8000, estimated_cost_usd=None),
            ModelOption(id="anthropic", label="Anthropic (connector ready)", provider="anthropic", available=False, estimated_tokens=8000, estimated_cost_usd=None),
            ModelOption(id="ollama", label="Local Ollama (connector ready)", provider="ollama", available=False, estimated_tokens=8000, estimated_cost_usd=None),
        ]
        return ModelRecommendation(recommended_model="gemini", alternatives=options, reason=f"Gemini Flash is the configured MVP recommendation for this {complexity.level.lower()} complexity task; token and cost figures are approximate.")


class PlanningAgent:
    def plan(self, task: JiraTask, version: int, comment: str | None = None) -> Plan:
        return Plan(version=version, objective=task.summary, affected_components=["Target application API", "Target application tests"], likely_files=["Existing route/controller module", "Existing test module"], implementation_steps=["Inspect the matching application route and test conventions.", "Create the smallest implementation matching the accepted requirement.", "Add focused unit coverage and run the project test command."], test_approach=["Add a positive behavior test.", "Add an invalid-input or error-path test when the endpoint has inputs."], risks=["Confirm endpoint naming and response shape against existing conventions."], expected_result="The ticket behavior is implemented, validated, and ready for review.", change_request=comment)


@dataclass(frozen=True)
class GeneratedFile:
    path: str
    content: str


class ImplementationAgent:
    def __init__(self, provider: LLMProvider) -> None:
        self.provider = provider

    async def generate(self, task: JiraTask, plan: Plan, repository: RepositoryAnalysis) -> tuple[list[GeneratedFile], str]:
        prompt = f"""You are implementing one approved software ticket in a Git repository.
Ticket key: {task.key}
Summary: {task.summary}
Description: {task.description or "No additional description."}
Approved plan: {plan.model_dump_json()}
Repository type: {repository.project_type}
Existing files: {repository.relevant_files}

Return JSON only, with this exact shape:
{{"summary":"short summary", "files":[{{"path":"relative/path", "content":"complete file content"}}]}}

Make the smallest focused change. Include focused automated tests. Do not include markdown fences.
The repository may be empty. If it is empty and the ticket is an HTTP API endpoint, bootstrap a minimal FastAPI application using app/main.py, tests/test_main.py, and requirements.txt. Do not create secrets, workflows, Git metadata, dependency lock files, binaries, or files outside the repository."""
        raw = await self.provider.generate(prompt)
        payload = self._parse(raw)
        files = payload.get("files")
        summary = payload.get("summary")
        if not isinstance(files, list) or not files or len(files) > 10 or not isinstance(summary, str):
            raise HTTPException(status_code=502, detail="Gemini returned an invalid implementation response.")
        generated: list[GeneratedFile] = []
        for item in files:
            if not isinstance(item, dict) or not isinstance(item.get("path"), str) or not isinstance(item.get("content"), str):
                raise HTTPException(status_code=502, detail="Gemini returned an invalid file change.")
            if len(item["content"].encode("utf-8")) > 100_000:
                raise HTTPException(status_code=502, detail="Gemini returned a file exceeding the MVP size limit.")
            generated.append(GeneratedFile(path=item["path"], content=item["content"]))
        return generated, summary.strip()

    @staticmethod
    def _parse(raw: str) -> dict[str, object]:
        cleaned = re.sub(r"^```(?:json)?\s*|\s*```$", "", raw.strip())
        try:
            payload = json.loads(cleaned)
        except json.JSONDecodeError as exc:
            raise HTTPException(status_code=502, detail="Gemini did not return valid JSON for the implementation.") from exc
        if not isinstance(payload, dict):
            raise HTTPException(status_code=502, detail="Gemini implementation response must be an object.")
        return payload
