import { useCallback, useEffect, useState } from "react";
import { api, setSessionId } from "../api";
import type { HealthStatus, PublicConfig, SetupRequest, SetupResponse, SetupSummary, Workflow } from "../types";

const ACTIVE_STATES = new Set(["RUNNING", "ANALYZING", "PLANNING", "IMPLEMENTING", "VALIDATING", "RETRYING", "PUBLISHING"]);

export type AppPhase = "welcome" | "booting" | "setup" | "connected" | "studio";

export function useStudio() {
  const [phase, setPhase] = useState<AppPhase>("welcome");
  const [config, setConfig] = useState<PublicConfig>();
  const [health, setHealth] = useState<HealthStatus>();
  const [setupResult, setSetupResult] = useState<SetupResponse>();
  const [sessionSummary, setSessionSummary] = useState<SetupSummary>();
  const [jiraKey, setJiraKey] = useState("");
  const [branches, setBranches] = useState<string[]>([]);
  const [baseBranch, setBaseBranch] = useState("");
  const [workflow, setWorkflow] = useState<Workflow>();
  const [selectedFile, setSelectedFile] = useState<string>();
  const [fileContent, setFileContent] = useState("");
  const [error, setError] = useState<string>();
  const [busy, setBusy] = useState(false);
  const [selectedRoute, setSelectedRoute] = useState<string>();
  const [workBranch, setWorkBranch] = useState("");

  useEffect(() => {
    api
      .publicConfig()
      .then((publicConfig) => {
        setConfig(publicConfig);
        applyTheme(publicConfig.theme);
        if (publicConfig.default_base_branch) setBaseBranch(publicConfig.default_base_branch);
      })
      .catch((cause) => setError(cause instanceof Error ? cause.message : "Failed to load configuration."));
  }, []);

  useEffect(() => {
    if (phase !== "studio" && phase !== "connected") return;
    api.health().then(setHealth).catch(() => undefined);
  }, [phase]);

  useEffect(() => {
    if (phase !== "studio") return;
    api
      .branches()
      .then((response) => {
        setBranches(response.branches);
        setBaseBranch((current) => current || response.default_branch);
      })
      .catch(() => undefined);
  }, [phase]);

  useEffect(() => {
    if (workflow?.model_recommendation?.recommended_model_id) {
      setSelectedRoute(workflow.model_recommendation.recommended_model_id);
    }
    if (workflow?.branch_analysis?.suggested_work_branch) {
      setWorkBranch(workflow.branch_analysis.suggested_work_branch);
    }
  }, [workflow?.id, workflow?.model_recommendation?.recommended_model_id, workflow?.branch_analysis?.suggested_work_branch]);

  useEffect(() => {
    if (!workflow || !ACTIVE_STATES.has(workflow.state)) return;
    const timer = window.setInterval(() => {
      api.get(workflow.id).then(setWorkflow).catch(() => undefined);
    }, 1500);
    return () => window.clearInterval(timer);
  }, [workflow]);

  useEffect(() => {
    if (!workflow || !selectedFile) return;
    api.file(workflow.id, selectedFile).then(setFileContent).catch((cause) => setError(cause instanceof Error ? cause.message : "Failed to load file."));
  }, [workflow, selectedFile]);

  const beginBoot = useCallback(() => {
    setError(undefined);
    setPhase("booting");
  }, []);

  const finishBoot = useCallback(() => {
    setPhase("setup");
  }, []);

  const submitSetup = useCallback(async (payload: SetupRequest) => {
    setBusy(true);
    setError(undefined);
    try {
      const result = await api.validateSetup(payload);
      setSessionId(result.session_id);
      setSetupResult(result);
      setSessionSummary(result.summary);
      setBranches(result.branches);
      setBaseBranch(result.default_branch);
      setPhase("connected");
    } catch (cause) {
      setError(cause instanceof Error ? cause.message : "Setup validation failed.");
    } finally {
      setBusy(false);
    }
  }, []);

  const enterStudio = useCallback(() => {
    setPhase("studio");
  }, []);

  const resetSession = useCallback(() => {
    setSessionId(undefined);
    setSetupResult(undefined);
    setSessionSummary(undefined);
    setWorkflow(undefined);
    setJiraKey("");
    setBranches([]);
    setWorkBranch("");
    setPhase("welcome");
  }, []);

  const reconfigure = useCallback(() => {
    setSessionId(undefined);
    setSetupResult(undefined);
    setSessionSummary(undefined);
    setWorkflow(undefined);
    setPhase("setup");
  }, []);

  const startWorkflow = useCallback(async () => {
    setBusy(true);
    setError(undefined);
    try {
      const created = await api.create(jiraKey.trim().toUpperCase(), baseBranch || undefined);
      setWorkflow(created);
      if (!selectedFile && created.generated_files[0]) setSelectedFile(created.generated_files[0].path);
    } catch (cause) {
      setError(cause instanceof Error ? cause.message : "Failed to start workflow.");
    } finally {
      setBusy(false);
    }
  }, [jiraKey, baseBranch, selectedFile]);

  const confirmModel = useCallback(async () => {
    if (!workflow || !selectedRoute) return;
    setBusy(true);
    setError(undefined);
    try {
      setWorkflow(await api.selectModel(workflow.id, selectedRoute, workBranch.trim() || undefined));
    } catch (cause) {
      setError(cause instanceof Error ? cause.message : "Model selection failed.");
    } finally {
      setBusy(false);
    }
  }, [workflow, selectedRoute, workBranch]);

  const approveWorkflow = useCallback(async () => {
    if (!workflow) return;
    setBusy(true);
    setError(undefined);
    try {
      setWorkflow(await api.approve(workflow.id));
    } catch (cause) {
      setError(cause instanceof Error ? cause.message : "Approval failed.");
    } finally {
      setBusy(false);
    }
  }, [workflow]);

  return {
    phase,
    config,
    health,
    setupResult,
    sessionSummary,
    jiraKey,
    setJiraKey,
    branches,
    baseBranch,
    setBaseBranch,
    workflow,
    selectedFile,
    setSelectedFile,
    fileContent,
    error,
    busy,
    selectedRoute,
    setSelectedRoute,
    workBranch,
    setWorkBranch,
    beginBoot,
    finishBoot,
    submitSetup,
    enterStudio,
    resetSession,
    reconfigure,
    startWorkflow,
    confirmModel,
    approveWorkflow,
  };
}

function applyTheme(theme: Record<string, string>) {
  const root = document.documentElement;
  Object.entries(theme).forEach(([key, value]) => root.style.setProperty(`--${key.replace(/_/g, "-")}`, value));
}
