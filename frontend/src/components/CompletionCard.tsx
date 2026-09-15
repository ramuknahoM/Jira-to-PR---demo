import type { Workflow } from "../types";

type Props = {
  workflow?: Workflow;
  onApprove?: () => void;
  busy?: boolean;
};

export function CompletionCard({ workflow, onApprove, busy }: Props) {
  if (!workflow) return null;

  if (workflow.state === "AWAITING_REVIEW") {
    return (
      <section className="completion-card review">
        <h2>Review required before publish</h2>
        <p>Validation passed. Approve to publish the branch, create the PR, and update Jira via MCP.</p>
        <button onClick={onApprove} disabled={busy}>Approve and Publish</button>
      </section>
    );
  }

  if (workflow.state === "COMPLETED" && workflow.pull_request) {
    return (
      <section className="completion-card success">
        <h2>Pipeline completed</h2>
        <p>{workflow.report?.summary ?? workflow.jira_task?.summary}</p>
        <a href={workflow.pull_request.url} target="_blank" rel="noreferrer">
          Open PR #{workflow.pull_request.number}
        </a>
      </section>
    );
  }

  if (workflow.state === "FAILED") {
    return (
      <section className="completion-card error">
        <h2>Pipeline failed</h2>
        <p>{workflow.error ?? "The workflow did not complete successfully."}</p>
      </section>
    );
  }

  return null;
}
