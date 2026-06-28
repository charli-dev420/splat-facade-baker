import React from 'react';
import { createRoot } from 'react-dom/client';
import { QueryClient, QueryClientProvider, useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import {
  API_BASE,
  getArtifacts,
  getAssets,
  getBakes,
  getComfyStatus,
  getHealth,
  getJobs,
  getModelRegistry,
  getProjects,
  getReviewQueue,
  getScenes,
  getSettings,
  getSummary,
  getTrainingRuns,
  getWorkflows,
  patch,
  post,
} from './api';
import type { ArtifactRecord, AssetRecord, BakeRecord, JobRecord, ProjectRecord, SceneRecord, TrainingRunRecord, WorkflowRecord } from './types';
import './style.css';

const queryClient = new QueryClient();
type Page = 'dashboard' | 'review' | 'assets' | 'jobs' | 'artifacts' | 'bakes' | 'scenes' | 'training' | 'workflows' | 'settings';
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
  { id: 'settings', label: 'Settings' },
];

function invalidateAll(client: QueryClient) {
  void client.invalidateQueries();
}

function Pill({ value }: { value: string | number | undefined | null }) {
  const text = String(value ?? '—');
  const low = text.toLowerCase();
  const cls = low.includes('failed') || low.includes('rejected') || low.includes('offline') || low.includes('bad')
    ? 'bad'
    : low.includes('completed') || low.includes('approved') || low.includes('online') || low.includes('ok')
      ? 'ok'
      : low.includes('running') || low.includes('candidate')
        ? 'run'
        : low.includes('review') || low.includes('queued') || low.includes('unreviewed')
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
  if (summary.isLoading) return <EmptyState>Loading workspace summary…</EmptyState>;
  if (summary.isError || !summary.data) return <EmptyState>Start the API with <code>SFB_WORKSPACE=workspace sfb-api</code>.</EmptyState>;
  const s = summary.data;
  const jobStatus = s.jobs.by_status;
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
        <StatCard label="ComfyUI" value={comfy.data?.ok ? 'online' : 'offline'} detail="background worker" />
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
  if (!review.data) return <EmptyState>Loading review queue…</EmptyState>;
  return (
    <div className="page-stack">
      <section className="grid three">
        <StatCard label="Assets to review" value={review.data.assets.length} />
        <StatCard label="Jobs to review" value={review.data.jobs.length} />
        <StatCard label="Bakes to review" value={review.data.bakes.length} />
      </section>
      <AssetTable assets={review.data.assets} compact onApprove={(asset) => assetReview.mutate({ asset, status: 'approved' })} onReject={(asset) => assetReview.mutate({ asset, status: 'rejected' })} />
      <JobTable jobs={review.data.jobs} compact onRetry={(job) => jobAction.mutate({ id: job.job_id, action: 'retry' })} onApprove={(job) => jobAction.mutate({ id: job.job_id, action: 'approve' })} onReject={(job) => jobAction.mutate({ id: job.job_id, action: 'reject' })} />
      <BakeTable bakes={review.data.bakes} />
    </div>
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
  return <AssetTable assets={assets.data?.assets ?? []} onApprove={(asset) => action.mutate({ asset, status: 'approved' })} onReject={(asset) => action.mutate({ asset, status: 'rejected' })} />;
}

function JobTable({ jobs, compact = false, onRetry, onApprove, onReject, onCancel }: { jobs: JobRecord[]; compact?: boolean; onRetry?: (j: JobRecord) => void; onApprove?: (j: JobRecord) => void; onReject?: (j: JobRecord) => void; onCancel?: (j: JobRecord) => void }) {
  const [selected, setSelected] = React.useState<JobRecord | null>(null);
  const logs = useQuery({ queryKey: ['job-logs', selected?.job_id], queryFn: () => fetch(`${API_BASE}/api/jobs/${selected?.job_id}/logs`).then(r => r.json()), enabled: !!selected });
  return (
    <section className="card">
      <h2>Jobs</h2>
      {jobs.length === 0 ? <EmptyState>No jobs.</EmptyState> : (
        <div className="table-wrap"><table><thead><tr><th>Job</th><th>Status</th><th>Engine</th><th>Asset</th><th>Attempt</th>{compact ? null : <th>Created</th>}<th>Actions</th></tr></thead><tbody>
          {jobs.map((j) => <tr key={j.job_id}>
            <td><button className="link-button" onClick={() => setSelected(j)}>{j.job_id}</button><small>{j.workflow_id ?? 'no workflow'}</small></td>
            <td><Pill value={j.status} /></td>
            <td>{j.engine}</td>
            <td>{j.asset_id ?? '—'}</td>
            <td>{j.attempt}/{j.max_attempts}</td>
            {compact ? null : <td>{j.created_at ?? '—'}</td>}
            <td className="actions"><button onClick={() => onRetry?.(j)}>Retry</button><button onClick={() => onCancel?.(j)}>Cancel</button><button onClick={() => onApprove?.(j)}>Approve</button><button onClick={() => onReject?.(j)}>Reject</button></td>
          </tr>)}
        </tbody></table></div>
      )}
      {selected ? <aside className="drawer"><button className="close" onClick={() => setSelected(null)}>×</button><h3>{selected.job_id}</h3><JsonBlock data={selected} /><h4>Logs</h4><JsonBlock data={logs.data ?? 'loading logs'} /></aside> : null}
    </section>
  );
}

function JobsPage() {
  const client = useQueryClient();
  const jobs = useQuery({ queryKey: ['jobs'], queryFn: getJobs, refetchInterval: 3000 });
  const runNext = useMutation({ mutationFn: () => post('/api/jobs/run-next'), onSuccess: () => invalidateAll(client) });
  const runAll = useMutation({ mutationFn: () => post('/api/jobs/run-all?limit=25'), onSuccess: () => invalidateAll(client) });
  const action = useMutation({ mutationFn: ({ id, action }: { id: string; action: 'retry' | 'cancel' | 'approve' | 'reject' }) => post(`/api/jobs/${id}/${action}`), onSuccess: () => invalidateAll(client) });
  return <div className="page-stack"><section className="card toolbar"><button onClick={() => runNext.mutate()}>Run next</button><button onClick={() => runAll.mutate()}>Run queued batch</button></section><JobTable jobs={jobs.data?.jobs ?? []} onRetry={(job) => action.mutate({ id: job.job_id, action: 'retry' })} onCancel={(job) => action.mutate({ id: job.job_id, action: 'cancel' })} onApprove={(job) => action.mutate({ id: job.job_id, action: 'approve' })} onReject={(job) => action.mutate({ id: job.job_id, action: 'reject' })} /></div>;
}

function ArtifactTable({ artifacts }: { artifacts: ArtifactRecord[] }) {
  return <section className="card"><h2>Artifacts</h2>{artifacts.length === 0 ? <EmptyState>No artifacts.</EmptyState> : <div className="table-wrap"><table><thead><tr><th>Type</th><th>Asset</th><th>Job</th><th>Path</th><th>Hash</th></tr></thead><tbody>{artifacts.map((a) => <tr key={a.artifact_id}><td><Pill value={a.artifact_type} /></td><td>{a.asset_id ?? '—'}</td><td>{a.job_id ?? '—'}</td><td className="path-cell">{a.path}</td><td>{a.hash ? a.hash.slice(0, 12) : '—'}</td></tr>)}</tbody></table></div>}</section>;
}

function ArtifactsPage() {
  const artifacts = useQuery({ queryKey: ['artifacts'], queryFn: getArtifacts });
  return <ArtifactTable artifacts={artifacts.data?.artifacts ?? []} />;
}

function BakeTable({ bakes }: { bakes: BakeRecord[] }) {
  return <section className="card"><h2>Bakes</h2>{bakes.length === 0 ? <EmptyState>No SFB packages found yet.</EmptyState> : <div className="table-wrap"><table><thead><tr><th>Asset</th><th>Status</th><th>View</th><th>Mode</th><th>Triangles</th><th>Texture memory</th><th>Warnings</th><th>Path</th></tr></thead><tbody>{bakes.map((b) => <tr key={b.path}><td><strong>{b.asset_id}</strong><small>{b.source_asset_id ?? '—'}</small></td><td><Pill value={b.status} /></td><td>{b.view_id ?? '—'}</td><td>{b.mode ?? '—'}</td><td>{String(b.metrics?.triangles_lod0 ?? b.metrics?.triangles ?? '—')}</td><td>{String(b.metrics?.estimated_texture_memory_mb_uncompressed ?? b.metrics?.estimated_texture_memory_mb ?? '—')}</td><td>{(b.warnings ?? []).slice(0, 2).join('; ') || '—'}</td><td className="path-cell">{b.path}</td></tr>)}</tbody></table></div>}</section>;
}

function BakesPage() {
  const bakes = useQuery({ queryKey: ['bakes'], queryFn: getBakes });
  return <BakeTable bakes={bakes.data?.bakes ?? []} />;
}


function SceneTable({ scenes }: { scenes: SceneRecord[] }) {
  return <section className="card"><h2>Scenes</h2>{scenes.length === 0 ? <EmptyState>No SFB scenes found under workspace/scenes.</EmptyState> : <div className="table-wrap"><table><thead><tr><th>Scene</th><th>Status</th><th>Cards</th><th>Chunks</th><th>Target</th><th>ViewContracts</th><th>Path</th></tr></thead><tbody>{scenes.map((scene) => <tr key={scene.path}><td><strong>{scene.scene_id}</strong><small>{scene.units ?? 'meters'}</small></td><td><Pill value={scene.status} /></td><td>{scene.cards_total}</td><td>{scene.chunks_total}</td><td>{String(scene.target?.camera_mode ?? scene.target?.engine ?? '—')}</td><td>{(scene.view_contracts ?? []).slice(0, 2).join(', ') || '—'}</td><td className="path-cell">{scene.path}</td></tr>)}</tbody></table></div>}</section>;
}

function ScenesPage() {
  const scenes = useQuery({ queryKey: ['scenes'], queryFn: getScenes });
  return <div className="page-stack"><SceneTable scenes={scenes.data?.scenes ?? []} /><section className="card"><h2>Scene Graph CLI</h2><pre>sfb-scene create --scene-id demo_lane --out workspace/scenes/demo_lane.sfbscene.json{`\n`}sfb-scene add-card workspace/scenes/demo_lane.sfbscene.json --scene-card-id card_001 --asset-package exports/DemoWall/asset.sfb.json{`\n`}sfb-scene validate workspace/scenes/demo_lane.sfbscene.json --out workspace/scenes/demo_lane_report.json</pre></section></div>;
}

function TrainingPage() {
  const runs = useQuery({ queryKey: ['training-runs'], queryFn: getTrainingRuns });
  const registry = useQuery({ queryKey: ['model-registry'], queryFn: getModelRegistry });
  return <div className="page-stack"><section className="card"><h2>Training runs</h2>{(runs.data?.runs ?? []).length === 0 ? <EmptyState>No training runs found under workspace/runs.</EmptyState> : <div className="table-wrap"><table><thead><tr><th>Run</th><th>Status</th><th>Task</th><th>Backend</th><th>Dataset</th><th>Checkpoints</th><th>Decision</th></tr></thead><tbody>{(runs.data?.runs ?? []).map((r: TrainingRunRecord) => <tr key={r.run_id}><td><strong>{r.run_id}</strong><small>{r.run_dir ?? ''}</small></td><td><Pill value={r.status} /></td><td>{r.task}</td><td>{r.backend}</td><td>{r.dataset_export_id ?? '—'}</td><td>{r.checkpoints?.length ?? 0}</td><td>{r.decision ?? 'draft'}</td></tr>)}</tbody></table></div>}</section><section className="card"><h2>Model registry</h2><JsonBlock data={registry.data ?? {}} /></section></div>;
}

function WorkflowsPage() {
  const workflows = useQuery({ queryKey: ['workflows'], queryFn: getWorkflows });
  const list = workflows.data?.workflows ?? [];
  return <section className="card"><h2>Workflows</h2>{list.length === 0 ? <EmptyState>No workflows registered.</EmptyState> : <div className="table-wrap"><table><thead><tr><th>Workflow</th><th>Engine</th><th>Version</th><th>Project</th><th>Description</th><th>Template</th></tr></thead><tbody>{list.map((w: WorkflowRecord) => <tr key={`${w.project_id ?? 'global'}:${w.workflow_id}`}><td><strong>{w.workflow_id}</strong></td><td><Pill value={w.engine} /></td><td>{w.version}</td><td>{w.project_id ?? 'global'}</td><td>{w.description}</td><td className="path-cell">{w.template_path ?? '—'}</td></tr>)}</tbody></table></div>}</section>;
}

function SettingsPage() {
  const health = useQuery({ queryKey: ['health'], queryFn: getHealth, retry: false });
  const settings = useQuery({ queryKey: ['settings'], queryFn: getSettings, retry: false });
  const projects = useQuery({ queryKey: ['projects'], queryFn: getProjects, retry: false });
  const comfy = useQuery({ queryKey: ['comfy'], queryFn: getComfyStatus, retry: false });
  return <div className="grid two"><section className="card"><h2>API</h2><JsonBlock data={{ base: API_BASE, health: health.data, settings: settings.data }} /></section><section className="card"><h2>Projects</h2><JsonBlock data={projects.data ?? {}} /></section><section className="card"><h2>ComfyUI</h2><JsonBlock data={comfy.data ?? 'unavailable'} /></section><section className="card"><h2>How to start</h2><pre>SFB_WORKSPACE=workspace sfb-api{`\n`}cd apps/sfb_studio && npm run dev</pre></section></div>;
}

function App() {
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
    case 'settings': content = <SettingsPage />; break;
  }
  return <main><Header page={page} setPage={setPage} apiOnline={health.isSuccess && !!health.data?.ok} />{health.isError ? <section className="card warning"><h2>Local API not connected</h2><p>Start the orchestrator API before using the studio.</p><pre>SFB_WORKSPACE=workspace sfb-api</pre></section> : content}</main>;
}

createRoot(document.getElementById('root')!).render(
  <React.StrictMode>
    <QueryClientProvider client={queryClient}>
      <App />
    </QueryClientProvider>
  </React.StrictMode>
);
