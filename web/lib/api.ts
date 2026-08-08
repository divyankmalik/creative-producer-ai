import type {
  Artifact,
  ArtifactVersionSummary,
  ProjectDetail,
  ProjectStatus,
} from "./types";

const API_URL = process.env.NEXT_PUBLIC_API_URL ?? "";

class ApiError extends Error {
  constructor(
    public status: number,
    message: string
  ) {
    super(message);
    this.name = "ApiError";
  }
}

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  const res = await fetch(`${API_URL}${path}`, {
    ...init,
    headers: {
      "Content-Type": "application/json",
      ...init?.headers,
    },
  });

  if (!res.ok) {
    let detail = res.statusText;
    try {
      const body = await res.json();
      detail = typeof body?.detail === "string" ? body.detail : JSON.stringify(body);
    } catch {
      // response wasn't JSON -- fall back to statusText
    }
    throw new ApiError(res.status, detail || `request to ${path} failed`);
  }

  if (res.status === 204) {
    return undefined as T;
  }
  return (await res.json()) as T;
}

export interface CreateProjectRequest {
  title: string;
  idea: string;
  params?: Record<string, unknown>;
}

export interface CreateProjectResponse {
  projectId: string;
  status: ProjectStatus;
}

export async function createProject(
  req: CreateProjectRequest
): Promise<CreateProjectResponse> {
  return request<CreateProjectResponse>("/projects", {
    method: "POST",
    body: JSON.stringify(req),
  });
}

export async function getProject(projectId: string): Promise<ProjectDetail> {
  return request<ProjectDetail>(`/projects/${projectId}`);
}

export async function getArtifact(artifactId: string): Promise<Artifact> {
  return request<Artifact>(`/artifacts/${artifactId}`);
}

export interface PatchArtifactRequest {
  payload: Record<string, unknown>;
  editedBy: string;
}

export interface PatchArtifactResponse {
  artifact: Artifact;
  staleDependents: string[];
}

export async function patchArtifact(
  artifactId: string,
  req: PatchArtifactRequest
): Promise<PatchArtifactResponse> {
  return request<PatchArtifactResponse>(`/artifacts/${artifactId}`, {
    method: "PATCH",
    body: JSON.stringify(req),
  });
}

export interface RegenerateArtifactResponse {
  ok: boolean;
  nodeKey: string;
}

export async function regenerateArtifact(
  artifactId: string
): Promise<RegenerateArtifactResponse> {
  return request<RegenerateArtifactResponse>(`/artifacts/${artifactId}/regenerate`, {
    method: "POST",
  });
}

export async function getArtifactVersions(
  artifactId: string
): Promise<{ versions: ArtifactVersionSummary[] }> {
  return request<{ versions: ArtifactVersionSummary[] }>(`/artifacts/${artifactId}/versions`);
}

export interface ApproveGateResponse {
  ok: boolean;
  resumedNodeKeys: string[];
}

export async function approveGate(
  projectId: string,
  gateKey: string
): Promise<ApproveGateResponse> {
  return request<ApproveGateResponse>(`/projects/${projectId}/gates/${gateKey}/approve`, {
    method: "POST",
  });
}

export async function exportProject(
  projectId: string
): Promise<{ projectId: string; bundle: Record<string, unknown> }> {
  return request<{ projectId: string; bundle: Record<string, unknown> }>(
    `/projects/${projectId}/export`
  );
}
