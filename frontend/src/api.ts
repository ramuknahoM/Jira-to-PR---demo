import type { Workflow } from "./types";

const API = import.meta.env.VITE_API_URL ?? "http://localhost:8000";

async function request<T>(path: string, method = "GET", body?: object): Promise<T> {
  const response = await fetch(`${API}${path}`, { method, headers: { "Content-Type": "application/json" }, body: body ? JSON.stringify(body) : undefined });
  if (!response.ok) {
    const error = await response.json().catch(() => ({}));
    throw new Error(error.detail ?? "The request could not be completed.");
  }
  return response.json() as Promise<T>;
}

export const api = {
  create: (jiraKey: string) => request<Workflow>("/api/workflows", "POST", { jira_key: jiraKey }),
  analyze: (id: string) => request<Workflow>(`/api/workflows/${id}/analyze`, "POST"),
  selectModel: (id: string, modelId: string) => request<Workflow>(`/api/workflows/${id}/model-selection`, "POST", { model_id: modelId }),
  plan: (id: string, comment?: string) => request<Workflow>(`/api/workflows/${id}/plan`, "POST", { comment }),
  approvePlan: (id: string) => request<Workflow>(`/api/workflows/${id}/approve-plan`, "POST"),
  requestPlanChanges: (id: string, comment: string) => request<Workflow>(`/api/workflows/${id}/plan-changes`, "POST", { comment }),
  implement: (id: string) => request<Workflow>(`/api/workflows/${id}/implementation`, "POST"),
  verify: (id: string, approved: boolean, comment?: string) => request<Workflow>(`/api/workflows/${id}/verification`, "POST", { approved, comment }),
  tests: (id: string) => request<Workflow>(`/api/workflows/${id}/tests`, "POST"),
  createPr: (id: string) => request<Workflow>(`/api/workflows/${id}/pr`, "POST"),
};
