import logging
import subprocess
import sys
from pathlib import Path
from time import perf_counter

import httpx
from fastapi import HTTPException

from .config import Settings
from .models import JiraTask, PullRequest, RepositoryAnalysis

logger = logging.getLogger(__name__)


def log_tool(workflow_id: str, agent: str, tool: str, action: str, success: bool, duration_ms: int, error: str | None = None) -> None:
    logger.info("tool_call workflow_id=%s agent=%s tool=%s action=%s success=%s duration_ms=%s error=%s", workflow_id, agent, tool, action, success, duration_ms, error)


class JiraClient:
    def __init__(self, settings: Settings) -> None:
        self.settings = settings

    async def fetch_issue(self, workflow_id: str, key: str) -> JiraTask:
        if not all((self.settings.jira_base_url, self.settings.jira_username, self.settings.jira_api_token)):
            raise HTTPException(status_code=503, detail="Jira is not configured. Set JIRA_BASE_URL, JIRA_USERNAME, and JIRA_API_TOKEN, then retry.")
        started = perf_counter()
        url = f"{self.settings.jira_base_url.rstrip('/')}/rest/api/3/issue/{key}"
        try:
            async with httpx.AsyncClient(timeout=15.0, auth=(self.settings.jira_username, self.settings.jira_api_token)) as client:
                response = await client.get(url, params={"fields": "summary,description,issuetype,priority"})
            response.raise_for_status()
            fields = response.json()["fields"]
            description = self._text(fields.get("description"))
            task = JiraTask(key=key.upper(), summary=fields["summary"], description=description, issue_type=fields.get("issuetype", {}).get("name", "TASK"), priority=(fields.get("priority") or {}).get("name"))
            log_tool(workflow_id, "jira", "jira-rest", "fetch_issue", True, int((perf_counter() - started) * 1000))
            return task
        except (httpx.HTTPError, KeyError, TypeError) as exc:
            log_tool(workflow_id, "jira", "jira-rest", "fetch_issue", False, int((perf_counter() - started) * 1000), str(exc))
            raise HTTPException(status_code=502, detail=f"Jira retrieval failed: {exc}") from exc

    @staticmethod
    def _text(value: object) -> str | None:
        if isinstance(value, str):
            return value
        if isinstance(value, dict):
            return " ".join(JiraClient._walk(value))
        return None

    @staticmethod
    def _walk(value: object) -> list[str]:
        if isinstance(value, dict):
            return [part for child in value.get("content", []) for part in JiraClient._walk(child)] + ([value["text"]] if isinstance(value.get("text"), str) else [])
        if isinstance(value, list):
            return [part for child in value for part in JiraClient._walk(child)]
        return []


class RepositoryClient:
    def __init__(self, settings: Settings) -> None:
        self.settings = settings

    def analyze(self) -> RepositoryAnalysis:
        if not self.settings.repository_path:
            raise HTTPException(status_code=503, detail="Repository is not configured. Set REPOSITORY_PATH, then retry.")
        root = Path(self.settings.repository_path).expanduser().resolve()
        if not root.is_dir() or not (root / ".git").exists():
            raise HTTPException(status_code=503, detail="REPOSITORY_PATH must point to an accessible Git repository.")
        files = [str(path.relative_to(root)) for path in root.rglob("*") if path.is_file() and ".git" not in path.parts][:40]
        project_type = "Python" if any(path.endswith("pyproject.toml") or path.endswith("requirements.txt") for path in files) else "Git repository"
        return RepositoryAnalysis(project_type=project_type, relevant_directories=["."], relevant_files=files[:12], test_command="pytest" if any("test" in path for path in files) else None, notes="Repository inspected through the configured local Git path.")

    def create_branch(self, jira_key: str, summary: str) -> str:
        root = self._root()
        slug = "-".join("".join(char.lower() if char.isalnum() else " " for char in summary).split())[:48]
        branch = f"ai/{jira_key.lower()}-{slug or 'change'}"
        current = self._git(root, "branch", "--show-current")
        if current == branch:
            return branch
        self._git(root, "checkout", "-b", branch)
        return branch

    def write_files(self, changes: list[object]) -> list[str]:
        root = self._root()
        written: list[str] = []
        for change in changes:
            relative_path = getattr(change, "path")
            content = getattr(change, "content")
            target = (root / relative_path).resolve()
            if not target.is_relative_to(root) or any(part in {".git", ".env", "node_modules", ".venv", "venv"} for part in target.relative_to(root).parts):
                raise HTTPException(status_code=400, detail=f"Refusing unsafe generated path: {relative_path}")
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_text(content, encoding="utf-8", newline="\n")
            written.append(str(target.relative_to(root)))
        return written

    def diff_summary(self) -> str:
        root = self._root()
        return self._git(root, "diff", "--stat") or "New untracked files generated."

    def validate(self) -> tuple[str, str]:
        root = self._root()
        python_files = list(root.rglob("*.py"))
        if not python_files:
            return "PASS", "No Python syntax validation was required for the generated files."
        result = subprocess.run([sys.executable, "-m", "compileall", "-q", "."], cwd=root, capture_output=True, text=True, timeout=30, check=False)
        if result.returncode:
            return "FAIL", result.stderr.strip() or result.stdout.strip() or "Python syntax validation failed."
        return "PASS", "Python syntax validation completed successfully."

    def run_tests(self) -> tuple[str, int, int, str, str]:
        root = self._root()
        test_files = list(root.rglob("test_*.py"))
        if not test_files:
            return "BLOCKED", 0, 0, "No tests found", "No generated or existing Python tests were found."
        command = f"{sys.executable} -m pytest -q"
        try:
            result = subprocess.run([sys.executable, "-m", "pytest", "-q"], cwd=root, capture_output=True, text=True, timeout=60, check=False)
        except subprocess.TimeoutExpired:
            return "FAIL", 0, 0, command, "Test command timed out after 60 seconds."
        output = (result.stdout + "\n" + result.stderr).strip()
        match = __import__("re").search(r"(\d+) passed(?:, (\d+) failed)?", output)
        passed = int(match.group(1)) if match else 0
        failed = int(match.group(2) or 0) if match and match.group(2) else (1 if result.returncode else 0)
        return ("PASS" if result.returncode == 0 else "FAIL"), passed, failed, command, output[-2000:] or "Test command completed."

    def commit(self, message: str) -> str:
        root = self._root()
        self._git(root, "add", "-A")
        self._git(root, "commit", "-m", message)
        return self._git(root, "rev-parse", "--short", "HEAD")

    async def create_pull_request(self, title: str, body: str) -> PullRequest:
        if not self.settings.github_token or not self.settings.github_repository:
            raise HTTPException(status_code=503, detail="PR creation is not configured. Set GITHUB_TOKEN and GITHUB_REPOSITORY, then retry.")
        root = self._root()
        branch = self._git(root, "branch", "--show-current")
        if not branch:
            raise HTTPException(status_code=409, detail="No active Git branch is available to push.")
        self._git(root, "push", "-u", "origin", branch)
        url = f"https://api.github.com/repos/{self.settings.github_repository}/pulls"
        headers = {"Accept": "application/vnd.github+json", "Authorization": f"Bearer {self.settings.github_token}", "X-GitHub-Api-Version": "2022-11-28"}
        try:
            async with httpx.AsyncClient(timeout=20.0) as client:
                response = await client.post(url, headers=headers, json={"title": title, "body": body, "head": branch, "base": self.settings.github_base_branch})
            response.raise_for_status()
            payload = response.json()
            return PullRequest(number=payload["number"], title=payload["title"], url=payload["html_url"], status=payload["state"].upper())
        except httpx.HTTPStatusError as exc:
            try:
                message = exc.response.json().get("message", "GitHub rejected the request.")
            except ValueError:
                message = "GitHub rejected the request."
            required = exc.response.headers.get("X-Accepted-GitHub-Permissions")
            hint = f" Required permissions: {required}." if required else ""
            raise HTTPException(status_code=502, detail=f"GitHub PR creation failed (HTTP {exc.response.status_code}): {message}.{hint}") from exc
        except (httpx.HTTPError, KeyError, TypeError) as exc:
            raise HTTPException(status_code=502, detail=f"GitHub PR creation failed: {exc}") from exc

    def _root(self) -> Path:
        if not self.settings.repository_path:
            raise HTTPException(status_code=503, detail="Repository is not configured.")
        return Path(self.settings.repository_path).resolve()

    @staticmethod
    def _git(root: Path, *args: str) -> str:
        result = subprocess.run(["git", *args], cwd=root, capture_output=True, text=True, timeout=30, check=False)
        if result.returncode:
            raise HTTPException(status_code=502, detail=f"Git operation failed: {result.stderr.strip() or result.stdout.strip()}")
        return result.stdout.strip()
