import React from 'react';
import { afterEach, describe, expect, it, vi } from 'vitest';
import { cleanup, fireEvent, render, screen, waitFor, within } from '@testing-library/react';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { App } from './App';

type MockResponse = {
  status?: number;
  body?: unknown;
  text?: string;
};

const API_BASE = 'http://127.0.0.1:8765';

function ok(body: unknown): MockResponse {
  return { status: 200, body };
}

function fail(status: number, text: string): MockResponse {
  return { status, text };
}

function jsonResponse(path: string, response: MockResponse): Response {
  const status = response.status ?? 200;
  const body = response.body ?? {};
  return {
    ok: status >= 200 && status < 300,
    status,
    json: () => Promise.resolve(body),
    text: () => Promise.resolve(response.text ?? JSON.stringify(body)),
  } as Response;
}

function renderStudio(routes: Record<string, MockResponse>) {
  const queryClient = new QueryClient({
    defaultOptions: {
      queries: { retry: false, gcTime: Infinity },
      mutations: { retry: false },
    },
  });
  const fetchMock = vi.fn((input: RequestInfo | URL, init?: RequestInit) => {
    const url = String(input);
    const path = url.startsWith(API_BASE) ? url.slice(API_BASE.length) : url;
    const response = routes[path] ?? fail(404, `missing mock for ${path}`);
    return Promise.resolve(jsonResponse(path, response));
  });
  vi.stubGlobal('fetch', fetchMock);
  const view = render(
    <QueryClientProvider client={queryClient}>
      <App />
    </QueryClientProvider>
  );
  return { ...view, fetchMock, queryClient };
}

const baseRoutes: Record<string, MockResponse> = {
  '/health': ok({ ok: true, service: 'sfb-orchestrator', workspace: 'workspace', version: 'test' }),
  '/api/summary': ok({
    active_project_id: 'demo',
    projects: [{ project_id: 'demo', name: 'Demo', root_path: 'workspace' }],
    workspace: 'workspace',
    assets: { total: 1, by_quality_status: { approved: 1 }, by_data_tier: {} },
    jobs: { total: 2, by_status: { queued: 1, completed: 1 } },
    artifacts: { total: 0, by_type: {} },
    bakes: { total: 0 },
    scenes: { total: 0 },
    training: { runs_total: 0, running: 0 },
    review: { jobs_needs_review: 0, bakes_needs_review: 0 },
  }),
  '/api/comfy/status': ok({ ok: true }),
};

afterEach(() => {
  cleanup();
  vi.unstubAllGlobals();
});

describe('Studio smoke', () => {
  it('renders the dashboard after API data loads', async () => {
    renderStudio(baseRoutes);

    expect(await screen.findByText('Review pressure')).toBeTruthy();
    expect(screen.getByText('API online')).toBeTruthy();
    expect(screen.getByText('demo')).toBeTruthy();
  });

  it('shows a panel error instead of an empty table', async () => {
    renderStudio({
      ...baseRoutes,
      '/api/bakes?limit=250': fail(500, 'bakes unavailable'),
    });

    fireEvent.click(screen.getByRole('button', { name: 'Bakes' }));

    expect(await screen.findByText('Unable to load bakes')).toBeTruthy();
    expect(screen.getByText('/api/bakes?limit=250: 500 bakes unavailable')).toBeTruthy();
    expect(screen.queryByText('No SFB packages found yet.')).toBeNull();
  });

  it('only renders Cancel for cancellable jobs', async () => {
    renderStudio({
      ...baseRoutes,
      '/api/jobs?limit=250': ok({
        jobs: [
          {
            job_id: 'job-queued',
            project_id: 'demo',
            engine: 'noop',
            status: 'queued',
            priority: 50,
            attempt: 0,
            max_attempts: 3,
            worker_id: 'worker-a',
            process_id: 123,
            heartbeat_at: '2026-06-30T04:00:00+00:00',
          },
          { job_id: 'job-cancelling', project_id: 'demo', engine: 'noop', status: 'cancelling', priority: 50, attempt: 1, max_attempts: 3, cancel_requested_at: '2026-06-30T04:01:00+00:00' },
          { job_id: 'job-completed', project_id: 'demo', engine: 'noop', status: 'completed', priority: 50, attempt: 1, max_attempts: 3 },
        ],
      }),
    });

    fireEvent.click(screen.getByRole('button', { name: 'Jobs' }));
    await screen.findByText('job-queued');

    expect(screen.getAllByRole('button', { name: 'Cancel' })).toHaveLength(1);
    expect(screen.getByText('worker worker-a')).toBeTruthy();
    expect(screen.getByText(/pid 123 \/ hb 2026-06-30T04:00:00/)).toBeTruthy();
    const cancellingRow = screen.getByText('job-cancelling').closest('tr');
    expect(cancellingRow).toBeTruthy();
    expect(within(cancellingRow as HTMLElement).queryByRole('button', { name: 'Cancel' })).toBeNull();
    const completedRow = screen.getByText('job-completed').closest('tr');
    expect(completedRow).toBeTruthy();
    expect(within(completedRow as HTMLElement).queryByRole('button', { name: 'Cancel' })).toBeNull();
  });

  it('loads job logs through the API wrapper', async () => {
    const { fetchMock } = renderStudio({
      ...baseRoutes,
      '/api/jobs?limit=250': ok({
        jobs: [
          { job_id: 'job-running', project_id: 'demo', engine: 'noop', status: 'running', priority: 50, attempt: 1, max_attempts: 3 },
        ],
      }),
      '/api/jobs/job-running/logs': ok({ job_id: 'job-running', log_dir: 'logs/job-running', files: [{ name: 'stdout.log', path: 'logs/job-running/stdout.log', size: 12 }] }),
    });

    fireEvent.click(screen.getByRole('button', { name: 'Jobs' }));
    fireEvent.click(await screen.findByRole('button', { name: 'job-running' }));

    expect(await screen.findByText(/stdout\.log/)).toBeTruthy();
    expect(fetchMock).toHaveBeenCalledWith(`${API_BASE}/api/jobs/job-running/logs`, expect.any(Object));
  });

  it('shows log API errors in the job drawer', async () => {
    renderStudio({
      ...baseRoutes,
      '/api/jobs?limit=250': ok({
        jobs: [
          { job_id: 'job-bad-logs', project_id: 'demo', engine: 'noop', status: 'running', priority: 50, attempt: 1, max_attempts: 3 },
        ],
      }),
      '/api/jobs/job-bad-logs/logs': fail(503, 'logs offline'),
    });

    fireEvent.click(screen.getByRole('button', { name: 'Jobs' }));
    fireEvent.click(await screen.findByRole('button', { name: 'job-bad-logs' }));

    expect(await screen.findByText('Unable to load job logs')).toBeTruthy();
    await waitFor(() => expect(screen.getByText('/api/jobs/job-bad-logs/logs: 503 logs offline')).toBeTruthy());
  });

  it('renders validation latest report and can start a validation run', async () => {
    const report = {
      schema: 'sfb.validation_report.v1',
      run_id: '20260630-010101',
      ok: false,
      status: 'failed',
      workspace: 'workspace/validation',
      gates: [
        { name: 'python_pytest', ok: true, status: 'passed', required: true, duration_s: 1.2 },
        { name: 'real_workspace_smoke', ok: false, status: 'failed_real_workspace_invalid', required: false, errors: ['invalid_report_json:path'] },
      ],
    };
    const { fetchMock } = renderStudio({
      ...baseRoutes,
      '/api/validation/latest': ok(report),
      '/api/validation/reports': ok({ reports: [{ run_id: '20260630-010101', status: 'failed', ok: false, path: 'workspace/validation_reports/20260630-010101.json', gates: 2 }] }),
      '/api/validation/active': ok({ active: null }),
      '/api/validation/run': ok({ run_id: '20260630-020202', started_at: 'now', status: 'running', command: ['python'], process_id: 42 }),
    });

    fireEvent.click(screen.getByRole('button', { name: 'Validation' }));
    await screen.findByText('Validation gates');
    expect(screen.getByText('real_workspace_smoke')).toBeTruthy();
    expect(screen.getByText('invalid_report_json:path')).toBeTruthy();
    fireEvent.click(screen.getByLabelText('real workspace'));
    fireEvent.click(screen.getByRole('button', { name: 'Run validation' }));

    await waitFor(() => expect(fetchMock).toHaveBeenCalledWith(`${API_BASE}/api/validation/run`, expect.objectContaining({ method: 'POST' })));
    const runCall = fetchMock.mock.calls.find((call) => String(call[0]).endsWith('/api/validation/run'));
    expect(JSON.parse((runCall?.[1] as RequestInit).body as string).real_workspace_smoke).toBe(true);
  });

  it('shows validation API errors instead of an empty report', async () => {
    renderStudio({
      ...baseRoutes,
      '/api/validation/latest': fail(404, 'validation report not found'),
      '/api/validation/reports': ok({ reports: [] }),
      '/api/validation/active': ok({ active: null }),
    });

    fireEvent.click(screen.getByRole('button', { name: 'Validation' }));

    expect(await screen.findByText('Unable to load latest validation')).toBeTruthy();
    expect(screen.getByText('/api/validation/latest: 404 validation report not found')).toBeTruthy();
  });
});
