export type JsonObject = Record<string, unknown>;

export interface ProjectRecord {
  project_id: string;
  name: string;
  root_path: string;
  default_view_contract?: string | null;
  metadata?: JsonObject;
}

export interface AssetRecord {
  project_id: string;
  asset_id: string;
  source_path?: string | null;
  data_tier: string;
  quality_status: string;
  category: string;
  style_family: string;
  manifest_id?: string | null;
  metadata?: JsonObject;
}

export interface JobRecord {
  job_id: string;
  project_id: string;
  engine: string;
  workflow_id?: string | null;
  asset_id?: string | null;
  status: string;
  priority: number;
  attempt: number;
  max_attempts: number;
  params?: JsonObject;
  created_at?: string | null;
  started_at?: string | null;
  finished_at?: string | null;
  error_type?: string | null;
  error_message?: string | null;
}

export interface ArtifactRecord {
  artifact_id: string;
  project_id: string;
  job_id?: string | null;
  asset_id?: string | null;
  artifact_type: string;
  path: string;
  hash?: string | null;
  metadata?: JsonObject;
  created_at?: string | null;
}

export interface WorkflowRecord {
  workflow_id: string;
  project_id?: string | null;
  engine: string;
  version: string;
  template_path?: string | null;
  description: string;
  metadata?: JsonObject;
}

export interface BakeRecord {
  asset_id: string;
  source_asset_id?: string | null;
  view_id?: string | null;
  mode?: string | null;
  path: string;
  package_dir: string;
  report_path?: string | null;
  status: string;
  metrics?: JsonObject;
  warnings?: string[];
  mobile?: JsonObject;
}


export interface SceneRecord {
  scene_id: string;
  path: string;
  units?: string;
  target?: JsonObject;
  cards_total: number;
  chunks_total: number;
  status: string;
  view_contracts?: string[];
}

export interface TrainingRunRecord {
  run_id: string;
  task: string;
  backend: string;
  status: string;
  dataset_export_id?: string;
  base_model?: JsonObject;
  checkpoints?: JsonObject[];
  eval_reports?: JsonObject[];
  run_dir?: string;
  decision?: string;
}

export interface SummaryResponse {
  active_project_id?: string | null;
  projects: ProjectRecord[];
  workspace: string;
  assets: { total: number; by_quality_status: Record<string, number>; by_data_tier: Record<string, number> };
  jobs: { total: number; by_status: Record<string, number> };
  artifacts: { total: number; by_type: Record<string, number> };
  bakes: { total: number };
  scenes?: { total: number };
  training: { runs_total: number; running: number };
  review: Record<string, number>;
}
