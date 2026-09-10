export type Plan = {
  version: number;
  objective: string;
  affected_components: string[];
  likely_files: string[];
  implementation_steps: string[];
  test_approach: string[];
  risks: string[];
  expected_result: string;
  change_request?: string | null;
};

export type Workflow = {
  id: string;
  jira_key: string;
  state: string;
  error?: string | null;
  jira_task?: { key: string; summary: string; description?: string; issue_type: string; priority?: string } | null;
  requirement_analysis?: { problem_summary: string; functional_requirement: string; acceptance_criteria: string[]; constraints: string[]; ambiguities: string[] } | null;
  complexity?: { score: number; level: string; explanation: string; estimated_files: number } | null;
  recommendation?: { recommended_model: string; reason: string; alternatives: { id: string; label: string; available: boolean; estimated_tokens: number; estimated_cost_usd?: number | null }[] } | null;
  selected_model?: string | null;
  plans: Plan[];
  repository_analysis?: { project_type: string; relevant_files: string[]; test_command?: string; notes: string } | null;
  implementation?: { branch: string; changed_files: string[]; diff_summary: string; validation_status: string; validation_summary: string; commit?: string } | null;
  verification_comment?: string | null;
  test_result?: { status: string; summary: string; passed: number; failed: number; executed_command: string } | null;
  pull_request?: { title: string; url: string; number: number } | null;
  audit_log: { timestamp: string; agent: string; action: string; status: string }[];
};
