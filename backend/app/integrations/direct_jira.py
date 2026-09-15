from __future__ import annotations

import httpx
from fastapi import HTTPException

from ..connection_models import JiraConnectionConfig
from ..models import JiraTask


def _auth(config: JiraConnectionConfig) -> tuple[str, str]:
    if not config.email or not config.api_token:
        raise HTTPException(status_code=400, detail="Jira email and API token are required for direct mode.")
    return config.email, config.api_token


def _base_url(config: JiraConnectionConfig) -> str:
    if not config.base_url:
        raise HTTPException(status_code=400, detail="Jira base URL is required for direct mode.")
    return config.base_url.rstrip("/")


async def validate_connection(config: JiraConnectionConfig) -> str:
    url = f"{_base_url(config)}/rest/api/3/myself"
    async with httpx.AsyncClient(timeout=20.0) as client:
        response = await client.get(url, auth=_auth(config), headers={"Accept": "application/json"})
    if response.status_code == 401:
        raise HTTPException(status_code=401, detail="Jira authentication failed. Check email and API token.")
    if response.status_code >= 400:
        raise HTTPException(status_code=502, detail=f"Jira connection failed: HTTP {response.status_code}.")
    data = response.json()
    display = data.get("displayName") or data.get("emailAddress") or "authenticated user"
    return f"Connected as {display}"


async def fetch_issue(config: JiraConnectionConfig, jira_key: str) -> JiraTask:
    url = f"{_base_url(config)}/rest/api/3/issue/{jira_key.upper()}"
    async with httpx.AsyncClient(timeout=30.0) as client:
        response = await client.get(url, auth=_auth(config), headers={"Accept": "application/json"})
    if response.status_code == 404:
        raise HTTPException(status_code=404, detail=f"Jira issue {jira_key} was not found.")
    if response.status_code >= 400:
        raise HTTPException(status_code=502, detail=f"Jira fetch failed: HTTP {response.status_code}.")
    data = response.json()
    fields = data.get("fields", {})
    description = fields.get("description")
    if isinstance(description, dict):
        description = " ".join(_walk_adf(description))
    return JiraTask(
        key=jira_key.upper(),
        summary=str(fields.get("summary") or jira_key),
        description=str(description) if description else None,
        issue_type=(fields.get("issuetype") or {}).get("name", "TASK"),
        priority=(fields.get("priority") or {}).get("name"),
        acceptance_criteria=list(fields.get("acceptance_criteria") or []),
    )


async def comment_issue(config: JiraConnectionConfig, jira_key: str, comment: str) -> None:
    url = f"{_base_url(config)}/rest/api/3/issue/{jira_key.upper()}/comment"
    payload = {"body": {"type": "doc", "version": 1, "content": [{"type": "paragraph", "content": [{"type": "text", "text": comment}]}]}}
    async with httpx.AsyncClient(timeout=20.0) as client:
        response = await client.post(url, auth=_auth(config), json=payload, headers={"Accept": "application/json"})
    if response.status_code >= 400:
        raise HTTPException(status_code=502, detail=f"Jira comment failed: HTTP {response.status_code}.")


async def transition_issue(config: JiraConnectionConfig, jira_key: str, transition_id: str) -> None:
    url = f"{_base_url(config)}/rest/api/3/issue/{jira_key.upper()}/transitions"
    async with httpx.AsyncClient(timeout=20.0) as client:
        response = await client.post(url, auth=_auth(config), json={"transition": {"id": transition_id}}, headers={"Accept": "application/json"})
    if response.status_code >= 400:
        raise HTTPException(status_code=502, detail=f"Jira transition failed: HTTP {response.status_code}.")


def _walk_adf(value: object) -> list[str]:
    if isinstance(value, dict):
        parts = [part for child in value.get("content", []) for part in _walk_adf(child)]
        if isinstance(value.get("text"), str):
            parts.append(value["text"])
        return parts
    if isinstance(value, list):
        return [part for child in value for part in _walk_adf(child)]
    return []
