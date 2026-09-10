import { FormEvent, type ReactNode, useState } from "react";
import { api } from "./api";
import type { Workflow } from "./types";

const stages = ["Jira", "Analyze", "Model", "Plan", "Build", "Verify", "Test", "PR"];

function App() {
  const [jiraKey, setJiraKey] = useState("");
  const [workflow, setWorkflow] = useState<Workflow>();
  const [selectedModel, setSelectedModel] = useState("gemini");
  const [comment, setComment] = useState("");
  const [error, setError] = useState<string>();
  const [busy, setBusy] = useState(false);

  const run = async (work: () => Promise<Workflow>) => {
    setBusy(true);
    setError(undefined);
    try {
      setWorkflow(await work());
      setComment("");
    } catch (cause) {
      setError(cause instanceof Error ? cause.message : "An unexpected error occurred.");
    } finally {
      setBusy(false);
    }
  };

  const create = (event: FormEvent) => {
    event.preventDefault();
    run(() => api.create(jiraKey));
  };
  const state = workflow?.state ?? "NEW";
  const latestPlan = workflow?.plans.at(-1);

  return <main>
    <header className="topbar">
      <div className="mark" aria-hidden="true">A</div>
      <div><p className="eyebrow">AI delivery lifecycle</p><h1>AIDLC Flow</h1></div>
      <div className="status"><span className="status-dot" />{workflow ? state.replaceAll("_", " ") : "Ready"}</div>
    </header>

    <section className="workflow-bar" aria-label="Workflow progress">
      {stages.map((stage, index) => <div className="stage" key={stage}><span>{index + 1}</span>{stage}</div>)}
    </section>

    {error && <div className="notice error" role="alert">{error}</div>}

    <section className="input-band">
      <div><p className="eyebrow">Start a workflow</p><h2>Connect a Jira issue to an approved engineering change.</h2></div>
      <form onSubmit={create}>
        <label htmlFor="jira-key">Jira issue key</label>
        <div className="input-row"><input id="jira-key" value={jiraKey} onChange={(event) => setJiraKey(event.target.value.toUpperCase())} placeholder="PROJ-123" pattern="[A-Za-z][A-Za-z0-9_]*-[0-9]+" required /><button disabled={busy}>Create</button></div>
      </form>
    </section>

    {!workflow && <section className="empty"><h2>Workflow details appear here</h2><p>Create a workflow, then retrieve the configured Jira issue. External systems must be configured before they can be used.</p></section>}

    {workflow && <div className="workspace">
      <aside><p className="eyebrow">Issue</p><strong>{workflow.jira_key}</strong><span>{state.replaceAll("_", " ")}</span></aside>
      <div className="content">
        {!workflow.jira_task && <Panel title="1. Jira retrieval" detail="Pull the issue from the configured Jira connector before any analysis."><button onClick={() => run(() => api.analyze(workflow.id))} disabled={busy}>Retrieve and analyze</button></Panel>}

        {workflow.jira_task && <Panel title="2. Requirement analysis" detail={workflow.jira_task.summary}>
          <div className="two-col"><div><h3>Requirement</h3><p>{workflow.requirement_analysis?.functional_requirement}</p></div><div><h3>Complexity</h3><p><b>{workflow.complexity?.level}</b> · {workflow.complexity?.score}/10</p><p>{workflow.complexity?.explanation}</p></div></div>
          {workflow.requirement_analysis?.ambiguities.length ? <div className="notice">Needs clarification: {workflow.requirement_analysis.ambiguities.join(" ")}</div> : null}
        </Panel>}

        {state === "ANALYZED" && <Panel title="3. Model selection" detail={workflow.recommendation?.reason ?? "Select a configured model."}>
          <div className="model-options">{workflow.recommendation?.alternatives.map((option) => <label className={`model-option ${!option.available ? "disabled" : ""}`} key={option.id}><input type="radio" value={option.id} checked={selectedModel === option.id} onChange={() => setSelectedModel(option.id)} disabled={!option.available} /><span><b>{option.label}</b><small>{option.estimated_tokens.toLocaleString()} estimated tokens{option.estimated_cost_usd != null ? ` · about $${option.estimated_cost_usd.toFixed(2)}` : ""}</small></span></label>)}</div>
          <button onClick={() => run(() => api.selectModel(workflow.id, selectedModel))} disabled={busy}>Continue with model</button>
        </Panel>}

        {state === "MODEL_SELECTED" && <Panel title="4. Plan" detail="Generate a structured proposal before modifying the target repository."><button onClick={() => run(() => api.plan(workflow.id))} disabled={busy}>Generate plan</button></Panel>}

        {latestPlan && ["PLAN_GENERATED", "PLAN_CHANGES_REQUESTED"].includes(state) && <Panel title={`4. Plan v${latestPlan.version}`} detail={latestPlan.objective}>
          <ol>{latestPlan.implementation_steps.map((step) => <li key={step}>{step}</li>)}</ol>
          <label htmlFor="plan-comment">Change request</label><textarea id="plan-comment" value={comment} onChange={(event) => setComment(event.target.value)} placeholder="Describe what needs to change in the plan" />
          <div className="actions"><button onClick={() => run(() => api.approvePlan(workflow.id))} disabled={busy || state !== "PLAN_GENERATED"}>Approve plan</button><button className="secondary" onClick={() => state === "PLAN_CHANGES_REQUESTED" ? run(() => api.plan(workflow.id, comment)) : run(() => api.requestPlanChanges(workflow.id, comment))} disabled={busy || !comment.trim()}>{state === "PLAN_CHANGES_REQUESTED" ? "Regenerate plan" : "Request changes"}</button></div>
        </Panel>}

        {state === "PLAN_APPROVED" && <Panel title="5. Repository analysis and branch" detail="Analyze the configured Git repository and create a branch before implementation."><button onClick={() => run(() => api.implement(workflow.id))} disabled={busy}>Analyze repository</button></Panel>}

        {workflow.implementation && <Panel title="6. Implementation review" detail={workflow.implementation.diff_summary}><div className="two-col"><div><h3>Branch</h3><code>{workflow.implementation.branch}</code><h3 className="files-heading">Changed files</h3><ul>{workflow.implementation.changed_files.map((file) => <li key={file}><code>{file}</code></li>)}</ul></div><div><h3>Validation</h3><p>{workflow.implementation.validation_status}: {workflow.implementation.validation_summary}</p></div></div><label htmlFor="verification-comment">Verification note</label><textarea id="verification-comment" value={comment} onChange={(event) => setComment(event.target.value)} placeholder="Describe an issue, if one is found" /><div className="actions"><button onClick={() => run(() => api.verify(workflow.id, true, comment))} disabled={busy}>Approve verification</button><button className="secondary" onClick={() => run(() => api.verify(workflow.id, false, comment))} disabled={busy || !comment.trim()}>Report issue</button></div></Panel>}

        {state === "HUMAN_VERIFIED" && <Panel title="7. Tests" detail="Generate focused unit tests and run the target repository test command."><button onClick={() => run(() => api.tests(workflow.id))} disabled={busy}>Generate and run tests</button></Panel>}
        {workflow.test_result && <Panel title="Test result" detail={workflow.test_result.summary}><p><b>{workflow.test_result.status}</b> · {workflow.test_result.passed} passed · {workflow.test_result.failed} failed</p></Panel>}
        {state === "TESTS_COMPLETED" && <Panel title="8. Pull request" detail="Push the approved branch and open a GitHub pull request."><button onClick={() => run(() => api.createPr(workflow.id))} disabled={busy}>Create pull request</button></Panel>}
        {workflow.pull_request && <Panel title="Pull request created" detail={workflow.pull_request.title}><p><a href={workflow.pull_request.url} target="_blank" rel="noreferrer">Open PR #{workflow.pull_request.number}</a></p></Panel>}
        {workflow.audit_log.length > 0 && <Panel title="Workflow activity" detail="Recorded workflow events"><ul className="activity-log">{workflow.audit_log.map((event) => <li key={`${event.timestamp}-${event.action}`}><time>{new Date(event.timestamp).toLocaleTimeString()}</time><span>{event.action.replaceAll("-", " ")}</span><b>{event.status}</b></li>)}</ul></Panel>}
      </div>
    </div>}
  </main>;
}

function Panel({ title, detail, children }: { title: string; detail: string; children: ReactNode }) {
  return <section className="panel"><div className="panel-head"><div><p className="eyebrow">{title}</p><h2>{detail}</h2></div></div>{children}</section>;
}

export default App;
