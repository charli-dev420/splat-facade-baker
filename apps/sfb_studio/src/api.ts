import type { ArtifactRecord, AssetRecord, BakeRecord, JobRecord, ProjectRecord, SceneRecord, SummaryResponse, TrainingRunRecord, WorkflowRecord } from './types';

export const API_BASE = import.meta.env.VITE_SFB_API ?? 'http://127.0.0.1:8765';

export async function api<T>(path: string, init?: RequestInit): Promise<T> {
  const res = await fetch(`${API_BASE}${path}`, {
    ...init,
    headers: {
      'Content-Type': 'application/json',
      ...(init?.headers ?? {}),
    },
  });
  if (!res.ok) {
    const text = await res.text().catch(() => '');
    throw new Error(`${path}: ${res.status}${text ? ` ${text}` : ''}`);
  }
  return res.json() as Promise<T>;
}

export const getHealth = () => api<{ ok: boolean; service: string; workspace: string; version: string }>('/health');
export const getSummary = () => api<SummaryResponse>('/api/summary');
export const getProjects = () => api<{ projects: ProjectRecord[] }>('/api/projects');
export const getAssets = () => api<{ assets: AssetRecord[] }>('/api/assets?limit=250');
export const getJobs = () => api<{ jobs: JobRecord[] }>('/api/jobs?limit=250');
export const getArtifacts = () => api<{ artifacts: ArtifactRecord[] }>('/api/artifacts?limit=250');
export const getWorkflows = () => api<{ workflows: WorkflowRecord[] }>('/api/workflows');
export const getBakes = () => api<{ bakes: BakeRecord[] }>('/api/bakes?limit=250');
export const getScenes = () => api<{ scenes: SceneRecord[] }>('/api/scenes?limit=250');
export const getTrainingRuns = () => api<{ runs: TrainingRunRecord[] }>('/api/training/runs');
export const getModelRegistry = () => api<Record<string, unknown>>('/api/training/model-registry');
export const getReviewQueue = () => api<{ assets: AssetRecord[]; jobs: JobRecord[]; bakes: BakeRecord[] }>('/api/review-queue');
export const getComfyStatus = () => api<Record<string, unknown>>('/api/comfy/status');
export const getSettings = () => api<Record<string, unknown>>('/api/settings');

export function post<T>(path: string, body?: unknown): Promise<T> {
  return api<T>(path, { method: 'POST', body: body === undefined ? undefined : JSON.stringify(body) });
}

export function patch<T>(path: string, body?: unknown): Promise<T> {
  return api<T>(path, { method: 'PATCH', body: body === undefined ? undefined : JSON.stringify(body) });
}
