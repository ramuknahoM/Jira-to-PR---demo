import type { PublicConfig, Workflow } from "../types";

type Props = {
  config?: PublicConfig;
  workflow?: Workflow;
};

export function WorkflowProgress({ config, workflow }: Props) {
  const stages = config?.stages ?? [];
  const activeIndex = stages.findIndex((stage) => stage.id === workflow?.state);

  return (
    <nav className="workflow-progress" aria-label="Workflow progress">
      {stages.map((stage, index) => {
        const active = workflow?.state === stage.id;
        const complete = activeIndex >= 0 && index < activeIndex;
        return (
          <div key={stage.id} className={`progress-step ${active ? "active" : ""} ${complete ? "complete" : ""}`}>
            <span>{index + 1}</span>
            {stage.label}
          </div>
        );
      })}
    </nav>
  );
}
