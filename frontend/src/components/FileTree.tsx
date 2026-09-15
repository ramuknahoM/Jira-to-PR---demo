import type { Workflow } from "../types";

type Props = {
  workflow?: Workflow;
  selectedFile?: string;
  onSelect: (path: string) => void;
};

export function FileTree({ workflow, selectedFile, onSelect }: Props) {
  const files = workflow?.generated_files ?? workflow?.implementation?.changed_files.map((path) => ({ path, content: "" })) ?? [];

  return (
    <aside className="sidebar">
      <div className="panel-title">Explorer</div>
      {!workflow && <p className="muted">Run a pipeline to inspect generated files.</p>}
      {workflow && (
        <ul className="file-tree">
          {files.map((file) => (
            <li key={file.path}>
              <button className={selectedFile === file.path ? "active" : ""} onClick={() => onSelect(file.path)}>
                {file.path}
              </button>
            </li>
          ))}
        </ul>
      )}
      {workflow?.implementation && (
        <div className="meta-block">
          <div className="panel-title">Branch</div>
          <code>{workflow.implementation.branch}</code>
        </div>
      )}
    </aside>
  );
}
