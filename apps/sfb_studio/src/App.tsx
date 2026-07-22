import React from 'react';
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import type { QueryClient, UseQueryResult } from '@tanstack/react-query';
import {
  API_BASE,
  getArtifacts,
  getAssets,
  getBakes,
  getComfyStatus,
  getHealth,
  getJobLogs,
  getJobs,
  getModelRegistry,
  getProjects,
  getReviewQueue,
  getScenes,
  getSettings,
  getSummary,
  getTrainingRuns,
  getValidationActive,
  getValidationLatest,
  getValidationReport,
  getValidationReports,
  getWorkflows,
  patch,
  post,
  runValidation,
} from './api';
import type { ArtifactRecord, AssetRecord, BakeRecord, JobRecord, SceneRecord, TrainingRunRecord, ValidationGateRecord, ValidationRunRequest, WorkflowRecord } from './types';

type Page = 'dashboard' | 'review' | 'assets' | 'jobs' | 'artifacts' | 'bakes' | 'scenes' | 'training' | 'workflows' | 'validation' | 'settings';

const pages: { id: Page; label: string }[] = [
  { id: 'dashboard', label: 'Dashboard' },
  { id: 'review', label: 'Review Queue' },
  { id: 'assets', label: 'Assets' },
  { id: 'jobs', label: 'Jobs' },
  { id: 'artifacts', label: 'Artifacts' },
  { id: 'bakes', label: 'Bakes' },
  { id: 'scenes', label: 'Scenes' },
  { id: 'training', label: 'Training' },
  { id: 'workflows', label: 'Workflows' },
  { id: 'validation', label: 'Validation' },
  { id: 'settings', label: 'Settings' },
];

const cancellableJobStatuses = new Set(['created', 'queued', 'running', 'collecting_outputs']);

function invalidateAll(client: QueryClient) {
  void client.invalidateQueries();
}

function formatError(error: unknown): string {
  if (error instanceof Error) return error.message;
  if (typeof error === 'string') return error;
  return 'Unknown error';
}

export function LoadingState({ children }: { children: React.ReactNode }) {
  return (
    <div className="empty-state loading-state">
      <strong className="state-title">{children}</strong>
    </div>
  );
}

export function ErrorState({ title, error }: { title: string; error: unknown }) {
  return (
    <div className="empty-state error-state" role="alert">
      <strong className="state-title">{title}</strong>
      <small>{formatError(error)}</small>
    </div>
  );
}

function DataPanel<T>({
  title,
  result,
  loadingText,
  errorTitle,
  children,
}: {
  title: string;
  result: UseQueryResult<T, Error>;
  loadingText: string;
  errorTitle: string;
  children: (data: T) => React.ReactNode;
}) {
  if (result.isLoading) {
    return (
      <section className="card">
        <h2>{title}</h2>
        <LoadingState>{loadingText}</LoadingState>
      </section>
    );
  }
  if (result.isError || result.data === undefined) {
    return (
      <section className="card">
        <h2>{title}</h2>
        <ErrorState title={errorTitle} error={result.error} />
      </section>
    );
  }
  return <>{children(result.data)}</>;
}

function canCancelJob(job: JobRecord): boolean {
  return cancellableJobStatuses.has(job.status);
}

function Pill({ value }: { value: string | number | undefined | null }) {
  const text = String(value ?? '—');
  const low = text.toLowerCase();
  const cls = low.includes('failed') || low.includes('rejected') || low.includes('offline') || low.includes('bad') || low.includes('invalid')
    ? 'bad'
    : low.includes('completed') || low.includes('approved') || low.includes('online') || low.includes('ok')
      ? 'ok'
      : low.includes('running') || low.includes('candidate') || low.includes('loading')
        ? 'run'
        : low.includes('review') || low.includes('queued') || low.includes('unreviewed') || low.includes('cancelling')
          ? 'warn'
          : 'neutral';
  return <span className={`pill ${cls}`}>{text}</span>;
}

function StatCard({ label, value, detail }: { label: string; value: React.ReactNode; detail?: React.ReactNode }) {
  return (
    <section className="stat-card">
      <div className="label">{label}</div>
      <div className="value">{value}</div>
      {detail ? <div className="detail">{detail}</div> : null}
    </section>
  );
}

function JsonBlock({ data }: { data: unknown }) {
  return <pre className="json-block">{JSON.stringify(data, null, 2)}</pre>;
}

function EmptyState({ children }: { children: React.ReactNode }) {
  return <div className="empty-state">{children}</div>;
}

function Header({ page, setPage, apiOnline }: { page: Page; setPage: (p: Page) => void; apiOnline: boolean }) {
  return (
    <header className="app-header">
      <div className="brand">
        <div className="logo">SFB</div>
        <div>
          <h1>Splat Facade Baker Studio</h1>
          <p>Local production UI for datasets, jobs, bakes, trainings and reviews.</p>
        </div>
      </div>
      <nav className="tabs">
        {pages.map((item) => (
          <button key={item.id} className={page === item.id ? 'active' : ''} onClick={() => setPage(item.id)}>
            {item.label}
          </button>
        ))}
      </nav>
      <div className="api-status"><Pill value={apiOnline ? 'API online' : 'API offline'} /></div>
    </header>
  );
}

function DashboardPage() {
  const summary = useQuery({ queryKey: ['summary'], queryFn: getSummary, refetchInterval: 5000 });
  const comfy = useQuery({ queryKey: ['comfy'], queryFn: getComfyStatus, retry: false, refetchInterval: 10000 });
  if (summary.isLoading) {
    return (
      <section className="card">
        <h2>Dashboard</h2>
        <LoadingState>Loading workspace summary...</LoadingState>
      </section>
    );
  }
  if (summary.isError || !summary.data) {
    return (
      <section className="card">
        <h2>Dashboard</h2>
        <ErrorState title="Unable to load workspace summary" error={summary.error} />
      </section>
    );
  }
  const s = summary.data;
  const jobStatus = s.jobs.by_status;
  const comfyValue = comfy.isLoading ? 'loading' : comfy.data?.ok ? 'online' : 'offline';
  return (
    <div className="page-stack">
      <section className="stats">
        <StatCard label="Projects" value={s.projects.length} detail={s.active_project_id ?? 'none'} />
        <StatCard label="Assets" value={s.assets.total} detail={`${s.assets.by_quality_status.approved ?? 0} approved`} />
        <StatCard label="Jobs" value={s.jobs.total} detail={`${jobStatus.queued ?? 0} queued / ${jobStatus.running ?? 0} running`} />
        <StatCard label="Failed jobs" value={jobStatus.failed ?? 0} detail="needs action" />
        <StatCard label="Artifacts" value={s.artifacts.total} detail={`${Object.keys(s.artifacts.by_type).length} types`} />
        <StatCard label="Bakes" value={s.bakes.total} detail="SFB packages found" />
        <StatCard label="Scenes" value={s.scenes?.total ?? 0} detail="2.5D graphs" />
        <StatCard label="Training runs" value={s.training.runs_total} detail={`${s.training.running} running`} />
        <StatCard label="ComfyUI" value={comfyValue} detail={comfy.isError ? formatError(comfy.error) : 'background worker'} />
      </section>

      <section className="grid two">
        <section className="card">
          <h2>Review pressure</h2>
          <div className="review-kpis">
            {Object.entries(s.review).map(([key, value]) => <StatCard key={key} label={key.replace(/_/g, ' ')} value={value} />)}
          </div>
        </section>
        <section className="card">
          <h2>Workspace</h2>
          <JsonBlock data={{ workspace: s.workspace, api: API_BASE, comfy: comfy.data ?? 'unavailable' }} />
        </section>
      </section>
    </div>
  );
}

function ReviewQueuePage() {
  const client = useQueryClient();
  const review = useQuery({ queryKey: ['review'], queryFn: getReviewQueue, refetchInterval: 5000 });
  const jobAction = useMutation({ mutationFn: ({ id, action }: { id: string; action: 'retry' | 'approve' | 'reject' }) => post(`/api/jobs/${id}/${action}`), onSuccess: () => invalidateAll(client) });
  const assetReview = useMutation({ mutationFn: ({ asset, status }: { asset: AssetRecord; status: string }) => patch(`/api/assets/${asset.project_id}/${asset.asset_id}/review`, { quality_status: status }), onSuccess: () => invalidateAll(client) });
  return (
    <DataPanel title="Review Queue" result={review} loadingText="Loading review queue..." errorTitle="Unable to load review queue">
      {(data) => (
        <div className="page-stack">
          <section className="grid three">
            <StatCard label="Assets to review" value={data.assets.length} />
            <StatCard label="Jobs to review" value={data.jobs.length} />
            <StatCard label="Bakes to review" value={data.bakes.length} />
          </section>
          <AssetTable assets={data.assets} compact onApprove={(asset) => assetReview.mutate({ asset, status: 'approved' })} onReject={(asset) => assetReview.mutate({ asset, status: 'rejected' })} />
          <JobTable jobs={data.jobs} compact onRetry={(job) => jobAction.mutate({ id: job.job_id, action: 'retry' })} onApprove={(job) => jobAction.mutate({ id: job.job_id, action: 'approve' })} onReject={(job) => jobAction.mutate({ id: job.job_id, action: 'reject' })} />
          <BakeTable bakes={data.bakes} />
        </div>
      )}
    </DataPanel>
  );
}

function AssetTable({ assets, compact = false, onApprove, onReject }: { assets: AssetRecord[]; compact?: boolean; onApprove?: (a: AssetRecord) => void; onReject?: (a: AssetRecord) => void }) {
  return (
    <section className="card">
      <h2>Assets</h2>
      {assets.length === 0 ? <EmptyState>No assets.</EmptyState> : (
        <div className="table-wrap"><table><thead><tr><th>Asset</th><th>Tier</th><th>Status</th><th>Category</th><th>Style</th>{compact ? null : <th>Source</th>}<th>Actions</th></tr></thead><tbody>
          {assets.map((a) => <tr key={`${a.project_id}:${a.asset_id}`}>
            <td><strong>{a.asset_id}</strong><small>{a.project_id}</small></td>
            <td><Pill value={a.data_tier} /></td>
            <td><Pill value={a.quality_status} /></td>
            <td>{a.category}</td>
            <td>{a.style_family}</td>
            {compact ? null : <td className="path-cell">{a.source_path ?? '—'}</td>}
            <td className="actions"><button onClick={() => onApprove?.(a)}>Approve</button><button onClick={() => onReject?.(a)}>Reject</button></td>
          </tr>)}
        </tbody></table></div>
      )}
    </section>
  );
}

function AssetsPage() {
  const client = useQueryClient();
  const assets = useQuery({ queryKey: ['assets'], queryFn: getAssets });
  const action = useMutation({ mutationFn: ({ asset, status }: { asset: AssetRecord; status: string }) => patch(`/api/assets/${asset.project_id}/${asset.asset_id}/review`, { quality_status: status }), onSuccess: () => invalidateAll(client) });
  return (
    <DataPanel title="Assets" result={assets} loadingText="Loading assets..." errorTitle="Unable to load assets">
      {(data) => <AssetTable assets={data.assets} onApprove={(asset) => action.mutate({ asset, status: 'approved' })} onReject={(asset) => action.mutate({ asset, status: 'rejected' })} />}
    </DataPanel>
  );
}

function JobTable({ jobs, compact = false, onRetry, onApprove, onReject, onCancel }: { jobs: JobRecord[]; compact?: boolean; onRetry?: (j: JobRecord) => void; onApprove?: (j: JobRecord) => void; onReject?: (j: JobRecord) => void; onCancel?: (j: JobRecord) => void }) {
  const [selected, setSelected] = React.useState<JobRecord | null>(null);
  const selectedJobId = selected?.job_id ?? '';
  const logs = useQuery({ queryKey: ['job-logs', selectedJobId], queryFn: () => getJobLogs(selectedJobId), enabled: selectedJobId.length > 0, retry: false });
  return (
    <section className="card">
      <h2>Jobs</h2>
      {jobs.length === 0 ? <EmptyState>No jobs.</EmptyState> : (
        <div className="table-wrap"><table><thead><tr><th>Job</th><th>Status</th><th>Engine</th><th>Asset</th><th>Attempt</th>{compact ? null : <th>Lifecycle</th>}{compact ? null : <th>Created</th>}<th>Actions</th></tr></thead><tbody>
          {jobs.map((j) => <tr key={j.job_id}>
            <td><button className="link-button" onClick={() => setSelected(j)}>{j.job_id}</button><small>{j.workflow_id ?? 'no workflow'}</small></td>
            <td><Pill value={j.status} /></td>
            <td>{j.engine}</td>
            <td>{j.asset_id ?? '—'}</td>
            <td>{j.attempt}/{j.max_attempts}</td>
            {compact ? null : <td><small>worker {j.worker_id ?? '—'}</small><small>pid {j.process_id ?? '—'} / hb {j.heartbeat_at ?? '—'}</small>{j.cancel_requested_at ? <small>cancel {j.cancel_requested_at}</small> : null}</td>}
            {compact ? null : <td>{j.created_at ?? '—'}</td>}
            <td className="actions">
              <button onClick={() => onRetry?.(j)}>Retry</button>
              {onCancel && canCancelJob(j) ? <button onClick={() => onCancel(j)}>Cancel</button> : null}
              <button onClick={() => onApprove?.(j)}>Approve</button>
              <button onClick={() => onReject?.(j)}>Reject</button>
            </td>
          </tr>)}
        </tbody></table></div>
      )}
      {selected ? (
        <aside className="drawer">
          <button className="close" onClick={() => setSelected(null)}>×</button>
          <h3>{selected.job_id}</h3>
          <JsonBlock data={selected} />
          <h4>Logs</h4>
          {logs.isLoading ? <LoadingState>Loading job logs...</LoadingState> : null}
          {logs.isError ? <ErrorState title="Unable to load job logs" error={logs.error} /> : null}
          {logs.data ? <JsonBlock data={logs.data} /> : null}
        </aside>
      ) : null}
    </section>
  );
}

function JobsPage() {
  const client = useQueryClient();
  const jobs = useQuery({ queryKey: ['jobs'], queryFn: getJobs, refetchInterval: 3000 });
  const runNext = useMutation({ mutationFn: () => post('/api/jobs/run-next'), onSuccess: () => invalidateAll(client) });
  const runAll = useMutation({ mutationFn: () => post('/api/jobs/run-all?limit=25'), onSuccess: () => invalidateAll(client) });
  const action = useMutation({ mutationFn: ({ id, action }: { id: string; action: 'retry' | 'cancel' | 'approve' | 'reject' }) => post(`/api/jobs/${id}/${action}`), onSuccess: () => invalidateAll(client) });
  return (
    <div className="page-stack">
      <section className="card toolbar"><button onClick={() => runNext.mutate()} disabled={runNext.isPending}>Run next</button><button onClick={() => runAll.mutate()} disabled={runAll.isPending}>Run queued batch</button></section>
      <DataPanel title="Jobs" result={jobs} loadingText="Loading jobs..." errorTitle="Unable to load jobs">
        {(data) => <JobTable jobs={data.jobs} onRetry={(job) => action.mutate({ id: job.job_id, action: 'retry' })} onCancel={(job) => action.mutate({ id: job.job_id, action: 'cancel' })} onApprove={(job) => action.mutate({ id: job.job_id, action: 'approve' })} onReject={(job) => action.mutate({ id: job.job_id, action: 'reject' })} />}
      </DataPanel>
    </div>
  );
}

function ArtifactTable({ artifacts }: { artifacts: ArtifactRecord[] }) {
  return <section className="card"><h2>Artifacts</h2>{artifacts.length === 0 ? <EmptyState>No artifacts.</EmptyState> : <div className="table-wrap"><table><thead><tr><th>Type</th><th>Asset</th><th>Job</th><th>Path</th><th>Hash</th></tr></thead><tbody>{artifacts.map((a) => <tr key={a.artifact_id}><td><Pill value={a.artifact_type} /></td><td>{a.asset_id ?? '—'}</td><td>{a.job_id ?? '—'}</td><td className="path-cell">{a.path}</td><td>{a.hash ? a.hash.slice(0, 12) : '—'}</td></tr>)}</tbody></table></div>}</section>;
}

function ArtifactsPage() {
  const artifacts = useQuery({ queryKey: ['artifacts'], queryFn: getArtifacts });
  return (
    <DataPanel title="Artifacts" result={artifacts} loadingText="Loading artifacts..." errorTitle="Unable to load artifacts">
      {(data) => <ArtifactTable artifacts={data.artifacts} />}
    </DataPanel>
  );
}

function BakeTable({ bakes }: { bakes: BakeRecord[] }) {
  return (
    <section className="card">
      <h2>Bakes</h2>
      {bakes.length === 0 ? <EmptyState>No SFB packages found yet.</EmptyState> : (
        <div className="table-wrap">
          <table>
            <thead>
              <tr><th>Asset</th><th>Status</th><th>View</th><th>Mode</th><th>Triangles</th><th>Texture memory</th><th>Issues</th><th>Path</th></tr>
            </thead>
            <tbody>
              {bakes.map((b) => {
                const issues = [...(b.errors ?? []), ...(b.warnings ?? [])];
                return (
                  <tr key={b.path}>
                    <td><strong>{b.asset_id}</strong><small>{b.source_asset_id ?? '—'}</small></td>
                    <td><Pill value={b.status} /></td>
                    <td>{b.view_id ?? '—'}</td>
                    <td>{b.mode ?? '—'}</td>
                    <td>{String(b.metrics?.triangles_lod0 ?? b.metrics?.triangles ?? '—')}</td>
                    <td>{String(b.metrics?.estimated_texture_memory_mb_uncompressed ?? b.metrics?.estimated_texture_memory_mb ?? '—')}</td>
                    <td>{issues.slice(0, 2).join('; ') || '—'}</td>
                    <td className="path-cell">{b.path}</td>
                  </tr>
                );
              })}
            </tbody>
          </table>
        </div>
      )}
    </section>
  );
}

function BakesPage() {
  const bakes = useQuery({ queryKey: ['bakes'], queryFn: getBakes });
  return (
    <DataPanel title="Bakes" result={bakes} loadingText="Loading bakes..." errorTitle="Unable to load bakes">
      {(data) => <BakeTable bakes={data.bakes} />}
    </DataPanel>
  );
}

function SceneTable({ scenes }: { scenes: SceneRecord[] }) {
  return <section className="card"><h2>Scenes</h2>{scenes.length === 0 ? <EmptyState>No SFB scenes found under workspace/scenes.</EmptyState> : <div className="table-wrap"><table><thead><tr><th>Scene</th><th>Status</th><th>Cards</th><th>Chunks</th><th>Target</th><th>ViewContracts</th><th>Path</th></tr></thead><tbody>{scenes.map((scene) => <tr key={scene.path}><td><strong>{scene.scene_id}</strong><small>{scene.units ?? 'meters'}</small></td><td><Pill value={scene.status} /></td><td>{scene.cards_total}</td><td>{scene.chunks_total}</td><td>{String(scene.target?.camera_mode ?? scene.target?.engine ?? '—')}</td><td>{(scene.view_contracts ?? []).slice(0, 2).join(', ') || '—'}</td><td className="path-cell">{scene.path}</td></tr>)}</tbody></table></div>}</section>;
}

function ScenesPage() {
  const scenes = useQuery({ queryKey: ['scenes'], queryFn: getScenes });
  return (
    <div className="page-stack">
      <DataPanel title="Scenes" result={scenes} loadingText="Loading scenes..." errorTitle="Unable to load scenes">
        {(data) => <SceneTable scenes={data.scenes} />}
      </DataPanel>
      <section className="card"><h2>Scene Graph CLI</h2><pre>sfb-scene create --scene-id demo_lane --out workspace/scenes/demo_lane.sfbscene.json{`\n`}sfb-scene add-card workspace/scenes/demo_lane.sfbscene.json --scene-card-id card_001 --asset-package exports/DemoWall/asset.sfb.json{`\n`}sfb-scene validate workspace/scenes/demo_lane.sfbscene.json --out workspace/scenes/demo_lane_report.json</pre></section>
    </div>
  );
}

function TrainingRunTable({ runs }: { runs: TrainingRunRecord[] }) {
  return <section className="card"><h2>Training runs</h2>{runs.length === 0 ? <EmptyState>No training runs found under workspace/runs.</EmptyState> : <div className="table-wrap"><table><thead><tr><th>Run</th><th>Status</th><th>Task</th><th>Backend</th><th>Dataset</th><th>Checkpoints</th><th>Decision</th></tr></thead><tbody>{runs.map((r) => <tr key={r.run_id}><td><strong>{r.run_id}</strong><small>{r.run_dir ?? ''}</small></td><td><Pill value={r.status} /></td><td>{r.task}</td><td>{r.backend}</td><td>{r.dataset_export_id ?? '—'}</td><td>{r.checkpoints?.length ?? 0}</td><td>{r.decision ?? 'draft'}</td></tr>)}</tbody></table></div>}</section>;
}

function TrainingPage() {
  const runs = useQuery({ queryKey: ['training-runs'], queryFn: getTrainingRuns });
  const registry = useQuery({ queryKey: ['model-registry'], queryFn: getModelRegistry });
  return (
    <div className="page-stack">
      <DataPanel title="Training runs" result={runs} loadingText="Loading training runs..." errorTitle="Unable to load training runs">
        {(data) => <TrainingRunTable runs={data.runs} />}
      </DataPanel>
      <DataPanel title="Model registry" result={registry} loadingText="Loading model registry..." errorTitle="Unable to load model registry">
        {(data) => <section className="card"><h2>Model registry</h2><JsonBlock data={data} /></section>}
      </DataPanel>
    </div>
  );
}

function WorkflowsPage() {
  const workflows = useQuery({ queryKey: ['workflows'], queryFn: getWorkflows });
  return (
    <DataPanel title="Workflows" result={workflows} loadingText="Loading workflows..." errorTitle="Unable to load workflows">
      {(data) => {
        const list = data.workflows;
        return <section className="card"><h2>Workflows</h2>{list.length === 0 ? <EmptyState>No workflows registered.</EmptyState> : <div className="table-wrap"><table><thead><tr><th>Workflow</th><th>Engine</th><th>Version</th><th>Project</th><th>Description</th><th>Template</th></tr></thead><tbody>{list.map((w: WorkflowRecord) => <tr key={`${w.project_id ?? 'global'}:${w.workflow_id}`}><td><strong>{w.workflow_id}</strong></td><td><Pill value={w.engine} /></td><td>{w.version}</td><td>{w.project_id ?? 'global'}</td><td>{w.description}</td><td className="path-cell">{w.template_path ?? '—'}</td></tr>)}</tbody></table></div>}</section>;
      }}
    </DataPanel>
  );
}

function ValidationGateTable({ gates }: { gates: ValidationGateRecord[] }) {
  return (
    <section className="card">
      <h2>Validation gates</h2>
      {gates.length === 0 ? <EmptyState>No gates recorded.</EmptyState> : (
        <div className="table-wrap"><table><thead><tr><th>Gate</th><th>Status</th><th>Required</th><th>Duration</th><th>Issues</th><th>Logs</th></tr></thead><tbody>
          {gates.map((gate) => {
            const issues = [...(gate.errors ?? []), ...(gate.warnings ?? [])];
            return (
              <tr key={gate.name}>
                <td><strong>{gate.name}</strong><small>{gate.cwd ?? ''}</small></td>
                <td><Pill value={gate.status} /></td>
                <td>{gate.required ? 'yes' : 'no'}{gate.blocked ? ' / blocked' : ''}</td>
                <td>{gate.duration_s ?? 0}s</td>
                <td>{issues.slice(0, 2).join('; ') || '—'}</td>
                <td><small>{gate.stdout_log ?? '—'}</small><small>{gate.stderr_log ?? ''}</small></td>
              </tr>
            );
          })}
        </tbody></table></div>
      )}
    </section>
  );
}

function ValidationPage() {
  const client = useQueryClient();
  const [selectedRunId, setSelectedRunId] = React.useState<string | null>(null);
  const [options, setOptions] = React.useState<ValidationRunRequest>({
    skip_slow: true,
    include_blender: false,
    include_unity: false,
    include_comfy_live: false,
    fail_on_blocked: false,
    real_workspace_smoke: false,
  });
  const latest = useQuery({ queryKey: ['validation-latest'], queryFn: getValidationLatest, retry: false, refetchInterval: 3000 });
  const reports = useQuery({ queryKey: ['validation-reports'], queryFn: getValidationReports, retry: false, refetchInterval: 5000 });
  const active = useQuery({ queryKey: ['validation-active'], queryFn: getValidationActive, retry: false, refetchInterval: 3000 });
  const selected = useQuery({ queryKey: ['validation-report', selectedRunId], queryFn: () => getValidationReport(selectedRunId as string), enabled: !!selectedRunId, retry: false });
  const run = useMutation({ mutationFn: () => runValidation(options), onSuccess: () => invalidateAll(client) });
  const report = selected.data ?? latest.data;
  const toggle = (key: keyof ValidationRunRequest) => setOptions((prev) => ({ ...prev, [key]: !prev[key] }));
  return (
    <div className="page-stack">
      <section className="card">
        <h2>Validation</h2>
        <div className="toolbar">
          <label><input type="checkbox" checked={options.skip_slow} onChange={() => toggle('skip_slow')} /> skip slow</label>
          <label><input type="checkbox" checked={options.real_workspace_smoke} onChange={() => toggle('real_workspace_smoke')} /> real workspace</label>
          <label><input type="checkbox" checked={options.include_blender} onChange={() => toggle('include_blender')} /> Blender</label>
          <label><input type="checkbox" checked={options.include_unity} onChange={() => toggle('include_unity')} /> Unity</label>
          <label><input type="checkbox" checked={options.include_comfy_live} onChange={() => toggle('include_comfy_live')} /> Comfy live</label>
          <label><input type="checkbox" checked={options.fail_on_blocked} onChange={() => toggle('fail_on_blocked')} /> fail blocked</label>
          <button onClick={() => run.mutate()} disabled={run.isPending || active.data?.active?.status === 'running'}>Run validation</button>
        </div>
        {run.isError ? <ErrorState title="Unable to start validation" error={run.error} /> : null}
        {active.data?.active ? <JsonBlock data={active.data.active} /> : null}
      </section>
      <DataPanel title="Latest validation" result={latest} loadingText="Loading latest validation..." errorTitle="Unable to load latest validation">
        {(data) => (
          <section className="stats">
            <StatCard label="Status" value={<Pill value={report?.status ?? data.status} />} detail={report?.run_id ?? data.run_id} />
            <StatCard label="Gates" value={report?.gates?.length ?? data.gates.length} detail={report?.workspace ?? data.workspace} />
            <StatCard label="Failed" value={(report?.gates ?? data.gates).filter((gate) => !gate.ok && !gate.blocked).length} />
            <StatCard label="Blocked" value={(report?.gates ?? data.gates).filter((gate) => gate.blocked).length} />
          </section>
        )}
      </DataPanel>
      {report ? <ValidationGateTable gates={report.gates} /> : null}
      <DataPanel title="Validation history" result={reports} loadingText="Loading validation reports..." errorTitle="Unable to load validation reports">
        {(data) => (
          <section className="card">
            <h2>Validation history</h2>
            {data.reports.length === 0 ? <EmptyState>No validation reports found.</EmptyState> : (
              <div className="table-wrap"><table><thead><tr><th>Run</th><th>Status</th><th>Gates</th><th>Path</th></tr></thead><tbody>
                {data.reports.map((item) => <tr key={item.run_id}><td><button className="link-button" onClick={() => setSelectedRunId(item.run_id)}>{item.run_id}</button></td><td><Pill value={item.status} /></td><td>{item.gates}</td><td className="path-cell">{item.path}</td></tr>)}
              </tbody></table></div>
            )}
            {selected.isError ? <ErrorState title="Unable to load selected validation report" error={selected.error} /> : null}
          </section>
        )}
      </DataPanel>
      {report ? <section className="card"><h2>Raw report</h2><JsonBlock data={report} /></section> : null}
    </div>
  );
}

function QueryJsonPanel<T>({ title, result, data }: { title: string; result: UseQueryResult<T, Error>; data?: (value: T) => unknown }) {
  return (
    <DataPanel title={title} result={result} loadingText={`Loading ${title.toLowerCase()}...`} errorTitle={`Unable to load ${title.toLowerCase()}`}>
      {(value) => <section className="card"><h2>{title}</h2><JsonBlock data={data ? data(value) : value} /></section>}
    </DataPanel>
  );
}

function SettingsPage() {
  const health = useQuery({ queryKey: ['health'], queryFn: getHealth, retry: false });
  const settings = useQuery({ queryKey: ['settings'], queryFn: getSettings, retry: false });
  const projects = useQuery({ queryKey: ['projects'], queryFn: getProjects, retry: false });
  const comfy = useQuery({ queryKey: ['comfy'], queryFn: getComfyStatus, retry: false });
  return (
    <div className="grid two">
      <QueryJsonPanel title="API" result={health} data={(value) => ({ base: API_BASE, health: value })} />
      <QueryJsonPanel title="Settings" result={settings} />
      <QueryJsonPanel title="Projects" result={projects} />
      <QueryJsonPanel title="ComfyUI" result={comfy} />
      <section className="card"><h2>How to start</h2><pre>SFB_WORKSPACE=workspace sfb-api{`\n`}cd apps/sfb_studio && npm run dev</pre></section>
    </div>
  );
}

export function App() {
  const [page, setPage] = React.useState<Page>('dashboard');
  const health = useQuery({ queryKey: ['health'], queryFn: getHealth, retry: false, refetchInterval: 5000 });
  let content: React.ReactNode;
  switch (page) {
    case 'dashboard': content = <DashboardPage />; break;
    case 'review': content = <ReviewQueuePage />; break;
    case 'assets': content = <AssetsPage />; break;
    case 'jobs': content = <JobsPage />; break;
    case 'artifacts': content = <ArtifactsPage />; break;
    case 'bakes': content = <BakesPage />; break;
    case 'scenes': content = <ScenesPage />; break;
    case 'training': content = <TrainingPage />; break;
    case 'workflows': content = <WorkflowsPage />; break;
    case 'validation': content = <ValidationPage />; break;
    case 'settings': content = <SettingsPage />; break;
  }
  return (
    <main>
      <Header page={page} setPage={setPage} apiOnline={health.isSuccess && !!health.data?.ok} />
      {health.isError ? <section className="card warning"><h2>Local API not connected</h2><p>Start the orchestrator API before using the studio.</p><pre>SFB_WORKSPACE=workspace sfb-api</pre></section> : null}
      {content}
    </main>
  );
}
