import type { PublicConfig, Workflow } from "../types";

type Props = {
  config?: PublicConfig;
  workflow?: Workflow;
};

function stageIndex(stages: { id: string }[], id: string) {
  return stages.findIndex((stage) => stage.id === id);
}

function resolveProgress(workflow: Workflow | undefined, stages: { id: string }[]) {
  if (!workflow || !stages.length) {
    return { activeAt: -1, completedUntil: -1, failedAt: -1 };
  }

  const activeAt = stageIndex(stages, workflow.state);
  let completedUntil = -1;

  if (workflow.jira_task) completedUntil = stageIndex(stages, "RUNNING");
  if (workflow.scope_analysis) completedUntil = stageIndex(stages, "ANALYZING");
  if (workflow.complexity || workflow.model_recommendation) completedUntil = stageIndex(stages, "MODEL_RECOMMENDED");
  if (workflow.model_selection) completedUntil = stageIndex(stages, "MODEL_RECOMMENDED");
  if (workflow.plans.length) completedUntil = stageIndex(stages, "PLANNING");
  if (workflow.generated_files.length || workflow.implementation) completedUntil = stageIndex(stages, "IMPLEMENTING");
  if (workflow.test_result) completedUntil = stageIndex(stages, "VALIDATING");
  if (workflow.pull_request) completedUntil = stageIndex(stages, "PUBLISHING");
  if (workflow.state === "COMPLETED") completedUntil = stageIndex(stages, "COMPLETED");

  if (workflow.state === "FAILED") {
    const failedAt = completedUntil >= 0 ? Math.min(completedUntil + 1, stageIndex(stages, "FAILED") - 1) : stageIndex(stages, "RUNNING");
    return { activeAt: stageIndex(stages, "FAILED"), completedUntil, failedAt };
  }

  return { activeAt, completedUntil: activeAt > 0 ? activeAt - 1 : completedUntil, failedAt: -1 };
}

export function WorkflowProgress({ config, workflow }: Props) {
  const stages = config?.stages ?? [];
  const { activeAt, completedUntil, failedAt } = resolveProgress(workflow, stages);

  return (
    <nav className="workflow-progress" aria-label="Workflow progress">
      {stages.map((stage, index) => {
        const active = index === activeAt && workflow?.state !== "FAILED" && workflow?.state !== "COMPLETED";
        const complete = index <= completedUntil;
        const failed = workflow?.state === "FAILED" && (index === failedAt || stage.id === "FAILED");
        return (
          <div
            key={stage.id}
            className={`progress-step ${active ? "active" : ""} ${complete ? "complete" : ""} ${failed ? "failed" : ""}`}
          >
            <span>{index + 1}</span>
            {stage.label}
          </div>
        );
      })}
    </nav>
  );
}
