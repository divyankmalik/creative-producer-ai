import type {
  Artifact,
  ArtifactVersionSummary,
  ProjectDetail,
  ProjectStatus,
} from "./types";

const API_URL = process.env.NEXT_PUBLIC_API_URL ?? "";

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
  // TODO: POST `${API_URL}/projects`, body: req, expect 202.
  throw new Error("not implemented");
}

export async function getProject(projectId: string): Promise<ProjectDetail> {
  // TODO: GET `${API_URL}/projects/${projectId}`.
  throw new Error("not implemented");
}

export async function getArtifact(artifactId: string): Promise<Artifact> {
  // TODO: GET `${API_URL}/artifacts/${artifactId}`.
  throw new Error("not implemented");
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
  // TODO: PATCH `${API_URL}/artifacts/${artifactId}`, body: req.
  throw new Error("not implemented");
}

export interface RegenerateArtifactResponse {
  ok: boolean;
  nodeKey: string;
}

export async function regenerateArtifact(
  artifactId: string
): Promise<RegenerateArtifactResponse> {
  // TODO: POST `${API_URL}/artifacts/${artifactId}/regenerate`.
  throw new Error("not implemented");
}

export async function getArtifactVersions(
  artifactId: string
): Promise<{ versions: ArtifactVersionSummary[] }> {
  // TODO: GET `${API_URL}/artifacts/${artifactId}/versions`.
  throw new Error("not implemented");
}

export interface ApproveGateResponse {
  ok: boolean;
  resumedNodeKeys: string[];
}

export async function approveGate(
  projectId: string,
  gateKey: string
): Promise<ApproveGateResponse> {
  // TODO: POST `${API_URL}/projects/${projectId}/gates/${gateKey}/approve`.
  throw new Error("not implemented");
}

export async function exportProject(
  projectId: string
): Promise<{ projectId: string; bundle: Record<string, unknown> }> {
  // TODO: GET `${API_URL}/projects/${projectId}/export`.
  throw new Error("not implemented");
}
