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
  heartbeat_at?: string | null;
  cancel_requested_at?: string | null;
  cancel_reason?: string | null;
  worker_id?: string | null;
  process_id?: number | null;
}

export interface JobLogFile {
  name: string;
  path: string;
  size: number;
}

export interface JobLogsResponse {
  job_id: string;
  log_dir: string;
  files: JobLogFile[];
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
  metrics?: JsonObject | null;
  warnings?: string[];
  errors?: string[];
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

export interface ValidationGateRecord {
  name: string;
  ok: boolean;
  status: string;
  required: boolean;
  blocked?: boolean;
  started_at?: string;
  finished_at?: string;
  duration_s?: number;
  command?: string[];
  cwd?: string;
  exit_code?: number | null;
  stdout_log?: string | null;
  stderr_log?: string | null;
  report_path?: string | null;
  errors?: string[];
  warnings?: string[];
  artifacts?: string[];
}

export interface ValidationReport {
  schema: string;
  run_id: string;
  ok: boolean;
  status: string;
  workspace: string;
  report_dir?: string;
  gates: ValidationGateRecord[];
  [key: string]: unknown;
}

export interface ValidationReportSummary {
  run_id: string;
  status: string;
  ok: boolean;
  path: string;
  finished_at?: number | string;
  gates: number;
}

export interface ValidationRunRequest {
  skip_slow: boolean;
  include_blender: boolean;
  include_unity: boolean;
  include_comfy_live: boolean;
  fail_on_blocked: boolean;
  real_workspace_smoke: boolean;
}

export interface ValidationActiveRun {
  run_id: string;
  started_at: string;
  status: string;
  command: string[];
  process_id: number;
  exit_code?: number | null;
}
