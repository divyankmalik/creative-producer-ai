// Mirrors api/app/models.py — kept in sync by hand.

export type ProjectStatus =
  | "planning"
  | "running"
  | "blocked"
  | "awaiting_gate"
  | "done"
  | "failed";

export type NodeStatus =
  | "queued"
  | "ready"
  | "running"
  | "succeeded"
  | "failed"
  | "blocked"
  | "skipped";

export type DependencyKind = "hard" | "soft";

export interface Dependency {
  nodeKey: string;
  kind: DependencyKind;
}

export interface TaskNode {
  id: string;
  projectId: string;
  nodeKey: string;
  agent: string;
  capability: string;
  status: NodeStatus;
  dependencies: Dependency[];
  params: Record<string, unknown>;
  attempts: number;
  lastError: string | null;
  createdAt: string;
  updatedAt: string;
}

export interface Artifact {
  id: string;
  projectId: string;
  nodeKey: string;
  type: string;
  slug: string;
  currentVersion: number;
  payload: Record<string, unknown>;
  summary: string | null;
  isStale: boolean;
  staleReason: string | null;
  editedBy: string | null;
  model: string | null;
  createdAt: string;
  updatedAt: string;
}

export interface ArtifactSummary {
  id: string;
  slug: string;
  type: string;
  summary: string | null;
  isStale: boolean;
}

export interface TaskGraph {
  projectId: string;
  nodes: TaskNode[];
}

export interface Project {
  id: string;
  title: string;
  idea: string;
  status: ProjectStatus;
  params: Record<string, unknown>;
  createdAt: string;
  updatedAt: string;
}

export interface TaskEnvelope {
  projectId: string;
  nodeKey: string;
  agent: string;
  capability: string;
  attempt: number;
  inputArtifactSlugs: string[];
  params: Record<string, unknown>;
  wordBudget: number | null;
  timeoutS: number;
}

export interface AgentResult {
  ok: boolean;
  artifactType: string | null;
  slug: string | null;
  payload: Record<string, unknown> | null;
  summary: string | null;
  errorCode: string | null;
  errorMessage: string | null;
  model: string | null;
  latencyMs: number | null;
}

export interface ValidationReport {
  ok: boolean;
  failures: string[];
  repairHint: string | null;
}

export interface ProjectDetail {
  id: string;
  title: string;
  idea: string;
  status: ProjectStatus;
  nodes: TaskNode[];
  artifacts: ArtifactSummary[];
}

export interface ProjectSummary {
  id: string;
  title: string;
  status: ProjectStatus;
  createdAt: string;
}

export interface ArtifactVersionSummary {
  version: number;
  summary: string | null;
  editedBy: string | null;
  model: string | null;
  createdAt: string;
}
