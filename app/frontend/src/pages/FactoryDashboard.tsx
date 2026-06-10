import { useCallback, useEffect, useMemo, useState } from 'react';
import { Link, Navigate } from 'react-router-dom';
import { useAuth } from '../hooks/useAuth';
import { useToast } from '../hooks/useToast';
import {
  type FactoryArtifact,
  type FactoryCriticReport,
  type FactoryInstance,
  type FactoryLearningAssessment,
  type FactoryMcpReadiness,
  type FactoryRun,
  type FactoryRunDetail,
  type FactoryRunEvent,
  type FactoryRunRepository,
  type FactorySummary,
  type FactoryTool,
  type FactoryToolingJob,
  checkLatestFactoryTooling,
  getFactoryEvidenceReport,
  getFactoryRun,
  getFactoryStalled,
  getFactorySummary,
  listFactoryInstances,
  listFactoryLearningAssessments,
  listFactoryMcpReadiness,
  listFactoryRuns,
  listFactoryTooling,
  pauseFactoryInstance,
  requestFactoryMcpReauth,
  resumeFactoryInstance,
  updateFactoryTooling,
} from '../lib/api';

type FactoryTab = 'overview' | 'runs' | 'mcps' | 'tooling' | 'learning';

const tabs: Array<{ id: FactoryTab; label: string }> = [
  { id: 'overview', label: 'Overview' },
  { id: 'runs', label: 'Runs' },
  { id: 'mcps', label: 'MCPs' },
  { id: 'tooling', label: 'Tooling' },
  { id: 'learning', label: 'Learning' },
];

function statusClass(status: string) {
  const normalized = status.toLowerCase();
  if (['ready', 'completed', 'verified', 'present', 'configured'].includes(normalized)) {
    return 'border-emerald-500/40 bg-emerald-500/10 text-emerald-300';
  }
  if (['running', 'queued', 'claimed', 'check_queued'].includes(normalized)) {
    return 'border-blue-500/40 bg-blue-500/10 text-blue-300';
  }
  if (
    ['stalled', 'paused', 'suspended', 'degraded', 'unauthenticated', 'stale'].includes(normalized)
  ) {
    return 'border-amber-500/40 bg-amber-500/10 text-amber-300';
  }
  if (['failed', 'unavailable', 'missing', 'error'].includes(normalized)) {
    return 'border-red-500/40 bg-red-500/10 text-red-300';
  }
  return 'border-slate-500/40 bg-slate-500/10 text-slate-300';
}

function StatusPill({ status }: { status: string }) {
  return (
    <span className={`inline-flex items-center border px-2 py-0.5 text-xs ${statusClass(status)}`}>
      {status}
    </span>
  );
}

function formatTime(value?: string | null) {
  if (!value) return '-';
  return value.slice(0, 19).replace('T', ' ');
}

function JsonPreview({ value }: { value: unknown }) {
  if (
    !value ||
    (typeof value === 'object' && Object.keys(value as Record<string, unknown>).length === 0)
  ) {
    return <span className="text-[var(--text-tertiary)]">none</span>;
  }
  return (
    <pre className="max-h-44 overflow-auto whitespace-pre-wrap rounded border border-[var(--border)] bg-black/20 p-3 text-xs text-[var(--text-secondary)]">
      {JSON.stringify(value, null, 2)}
    </pre>
  );
}

function EmptyState({ children }: { children: string }) {
  return (
    <div className="border border-[var(--border)] p-6 text-sm text-[var(--text-secondary)]">
      {children}
    </div>
  );
}

function Metric({
  label,
  value,
  tone,
}: { label: string; value: number; tone?: 'warn' | 'danger' }) {
  const toneClass =
    tone === 'danger'
      ? 'text-red-300'
      : tone === 'warn'
        ? 'text-amber-300'
        : 'text-[var(--text-primary)]';
  return (
    <div className="border border-[var(--border)] bg-[var(--surface-1)] p-4">
      <div className={`text-2xl font-semibold ${toneClass}`}>{value}</div>
      <div className="mt-1 text-xs uppercase tracking-normal text-[var(--text-secondary)]">
        {label}
      </div>
    </div>
  );
}

export function FactoryDashboard() {
  const { status, user } = useAuth();
  const { addToast } = useToast();
  const [activeTab, setActiveTab] = useState<FactoryTab>('overview');
  const [summary, setSummary] = useState<FactorySummary | null>(null);
  const [instances, setInstances] = useState<FactoryInstance[]>([]);
  const [mcps, setMcps] = useState<FactoryMcpReadiness[]>([]);
  const [runs, setRuns] = useState<FactoryRun[]>([]);
  const [stalledRuns, setStalledRuns] = useState<FactoryRun[]>([]);
  const [tools, setTools] = useState<FactoryTool[]>([]);
  const [toolJobs, setToolJobs] = useState<FactoryToolingJob[]>([]);
  const [learning, setLearning] = useState<FactoryLearningAssessment[]>([]);
  const [selectedRunId, setSelectedRunId] = useState<string | null>(null);
  const [selectedRun, setSelectedRun] = useState<FactoryRunDetail | null>(null);
  const [loading, setLoading] = useState(true);
  const [pending, setPending] = useState<string | null>(null);

  const loadDashboard = useCallback(async () => {
    setLoading(true);
    try {
      const [summaryRes, instancesRes, mcpRes, runsRes, stalledRes, toolingRes, learningRes] =
        await Promise.all([
          getFactorySummary(),
          listFactoryInstances(),
          listFactoryMcpReadiness(),
          listFactoryRuns(),
          getFactoryStalled(),
          listFactoryTooling(),
          listFactoryLearningAssessments(),
        ]);
      setSummary(summaryRes);
      setInstances(instancesRes.instances);
      setMcps(mcpRes.mcps);
      setRuns(runsRes.runs);
      setStalledRuns(stalledRes.runs);
      setTools(toolingRes.tools);
      setToolJobs(toolingRes.update_jobs);
      setLearning(learningRes.assessments);
      const nextRunId = selectedRunId ?? runsRes.runs[0]?.id ?? null;
      setSelectedRunId(nextRunId);
    } catch (err) {
      addToast(err instanceof Error ? err.message : 'Failed to load factory dashboard', 'error');
    } finally {
      setLoading(false);
    }
  }, [addToast, selectedRunId]);

  useEffect(() => {
    void loadDashboard();
  }, [loadDashboard]);

  useEffect(() => {
    if (!selectedRunId) {
      setSelectedRun(null);
      return;
    }
    let active = true;
    getFactoryRun(selectedRunId)
      .then((detail) => {
        if (active) setSelectedRun(detail);
      })
      .catch((err) => addToast(err instanceof Error ? err.message : 'Failed to load run', 'error'));
    return () => {
      active = false;
    };
  }, [addToast, selectedRunId]);

  const activeRuns = useMemo(
    () => runs.filter((run) => ['queued', 'claimed', 'running', 'stalled'].includes(run.status)),
    [runs],
  );

  if (status === 'loading') {
    return (
      <div className="min-h-screen bg-[var(--bg)] p-6 text-[var(--text-secondary)]">Loading...</div>
    );
  }
  if (status === 'anon') {
    return <Navigate to="/login" replace state={{ from: '/factory' }} />;
  }
  if (!user?.is_admin) {
    return <Navigate to="/" replace />;
  }

  async function handlePause(instance: FactoryInstance) {
    setPending(instance.id);
    try {
      await pauseFactoryInstance(instance.id, 'Paused from factory dashboard');
      addToast('Instance paused', 'success');
      await loadDashboard();
    } catch (err) {
      addToast(err instanceof Error ? err.message : 'Pause failed', 'error');
    } finally {
      setPending(null);
    }
  }

  async function handleResume(instance: FactoryInstance) {
    setPending(instance.id);
    try {
      await resumeFactoryInstance(instance.id);
      addToast('Instance resumed', 'success');
      await loadDashboard();
    } catch (err) {
      addToast(err instanceof Error ? err.message : 'Resume failed', 'error');
    } finally {
      setPending(null);
    }
  }

  async function handleReauth(mcp: FactoryMcpReadiness) {
    setPending(`${mcp.instance_id || 'global'}:${mcp.mcp_name}`);
    try {
      await requestFactoryMcpReauth(mcp.mcp_name, mcp.instance_id, mcp.reauth_url);
      addToast(`Reauth requested for ${mcp.mcp_name}`, 'success');
      await loadDashboard();
    } catch (err) {
      addToast(err instanceof Error ? err.message : 'Reauth request failed', 'error');
    } finally {
      setPending(null);
    }
  }

  async function handleCheckTooling() {
    setPending('tooling-check');
    try {
      await checkLatestFactoryTooling();
      addToast('Tooling check queued', 'success');
      await loadDashboard();
    } catch (err) {
      addToast(err instanceof Error ? err.message : 'Tooling check failed', 'error');
    } finally {
      setPending(null);
    }
  }

  async function handleUpdateTool(tool: FactoryTool) {
    setPending(tool.id);
    try {
      await updateFactoryTooling(tool.id, tool.latest_version);
      addToast(`Update queued for ${tool.name}`, 'success');
      await loadDashboard();
    } catch (err) {
      addToast(err instanceof Error ? err.message : 'Update request failed', 'error');
    } finally {
      setPending(null);
    }
  }

  async function handleCopyEvidence(runId: string) {
    setPending(`evidence:${runId}`);
    try {
      const report = await getFactoryEvidenceReport(runId);
      await navigator.clipboard.writeText(report);
      addToast('Evidence report copied', 'success');
    } catch (err) {
      addToast(err instanceof Error ? err.message : 'Evidence report failed', 'error');
    } finally {
      setPending(null);
    }
  }

  return (
    <div className="min-h-screen bg-[var(--bg)] text-[var(--text-primary)]">
      <div className="border-b border-[var(--border)] bg-[var(--surface-1)]">
        <div className="mx-auto flex max-w-7xl flex-col gap-4 px-6 py-5 lg:flex-row lg:items-center lg:justify-between">
          <div>
            <div className="text-xs uppercase tracking-normal text-[var(--text-secondary)]">
              PAVE Dark Factory
            </div>
            <h1 className="mt-1 text-2xl font-semibold">Factory control portal</h1>
            <p className="mt-1 text-sm text-[var(--text-secondary)]">
              Board: Peter's Board. Staff code: PWS. CargoWise work starts and reports through PAVE.
            </p>
          </div>
          <div className="flex flex-wrap items-center gap-2">
            <button
              type="button"
              onClick={loadDashboard}
              disabled={loading}
              className="border border-[var(--border)] px-3 py-2 text-sm text-[var(--text-primary)] hover:bg-[var(--surface-2)] disabled:opacity-50"
            >
              Refresh
            </button>
            <Link
              to="/admin"
              className="border border-[var(--border)] px-3 py-2 text-sm text-[var(--text-secondary)] hover:bg-[var(--surface-2)] hover:text-[var(--text-primary)]"
            >
              Library admin
            </Link>
            <Link
              to="/chat"
              className="border border-[var(--border)] px-3 py-2 text-sm text-[var(--text-secondary)] hover:bg-[var(--surface-2)] hover:text-[var(--text-primary)]"
            >
              Legacy chat
            </Link>
          </div>
        </div>
      </div>

      <main className="mx-auto max-w-7xl px-6 py-6">
        <div className="mb-5 flex flex-wrap gap-2 border-b border-[var(--border)]">
          {tabs.map((tab) => (
            <button
              key={tab.id}
              type="button"
              onClick={() => setActiveTab(tab.id)}
              className={`border-x border-t border-[var(--border)] px-4 py-2 text-sm ${
                activeTab === tab.id
                  ? 'bg-[var(--surface-1)] text-[var(--text-primary)]'
                  : 'text-[var(--text-secondary)] hover:bg-[var(--surface-2)] hover:text-[var(--text-primary)]'
              }`}
            >
              {tab.label}
            </button>
          ))}
        </div>

        {loading && (
          <div className="mb-4 border border-[var(--border)] bg-[var(--surface-1)] p-4 text-sm text-[var(--text-secondary)]">
            Loading factory state...
          </div>
        )}

        {activeTab === 'overview' && (
          <OverviewTab
            summary={summary}
            instances={instances}
            mcps={mcps}
            activeRuns={activeRuns}
            stalledRuns={stalledRuns}
            onPause={handlePause}
            onResume={handleResume}
            pending={pending}
          />
        )}

        {activeTab === 'runs' && (
          <RunsTab
            runs={runs}
            selectedRunId={selectedRunId}
            selectedRun={selectedRun}
            pending={pending}
            onSelectRun={setSelectedRunId}
            onCopyEvidence={handleCopyEvidence}
          />
        )}

        {activeTab === 'mcps' && <McpsTab mcps={mcps} pending={pending} onReauth={handleReauth} />}

        {activeTab === 'tooling' && (
          <ToolingTab
            tools={tools}
            jobs={toolJobs}
            pending={pending}
            onCheck={handleCheckTooling}
            onUpdate={handleUpdateTool}
          />
        )}

        {activeTab === 'learning' && <LearningTab assessments={learning} />}
      </main>
    </div>
  );
}

function OverviewTab({
  summary,
  instances,
  mcps,
  activeRuns,
  stalledRuns,
  pending,
  onPause,
  onResume,
}: {
  summary: FactorySummary | null;
  instances: FactoryInstance[];
  mcps: FactoryMcpReadiness[];
  activeRuns: FactoryRun[];
  stalledRuns: FactoryRun[];
  pending: string | null;
  onPause: (instance: FactoryInstance) => void;
  onResume: (instance: FactoryInstance) => void;
}) {
  return (
    <div className="space-y-6">
      <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-4">
        <Metric label="Instances" value={summary?.instances_total ?? 0} />
        <Metric label="Active runs" value={summary?.runs_active ?? 0} />
        <Metric label="Stalled MCPs" value={summary?.stalled_mcp_count ?? 0} tone="warn" />
        <Metric label="Failed runs" value={summary?.runs_failed ?? 0} tone="danger" />
      </div>

      <section>
        <h2 className="mb-3 text-lg font-semibold">Instances</h2>
        {instances.length === 0 ? (
          <EmptyState>
            No factory instances have registered yet. Start the scout service.
          </EmptyState>
        ) : (
          <div className="overflow-x-auto border border-[var(--border)]">
            <table className="w-full min-w-[900px] text-sm">
              <thead className="bg-[var(--surface-2)] text-left">
                <tr>
                  <th className="px-3 py-2 font-medium">Instance</th>
                  <th className="px-3 py-2 font-medium">Status</th>
                  <th className="px-3 py-2 font-medium">Staff</th>
                  <th className="px-3 py-2 font-medium">Board</th>
                  <th className="px-3 py-2 font-medium">Heartbeat</th>
                  <th className="px-3 py-2 font-medium text-right">Control</th>
                </tr>
              </thead>
              <tbody>
                {instances.map((instance) => (
                  <tr key={instance.id} className="border-t border-[var(--border)]">
                    <td className="px-3 py-2">
                      <div className="font-medium">{instance.name}</div>
                      <div className="text-xs text-[var(--text-secondary)]">
                        {instance.host_name}
                      </div>
                    </td>
                    <td className="px-3 py-2">
                      <StatusPill status={instance.is_paused ? 'paused' : instance.status} />
                      {instance.paused_reason && (
                        <div className="mt-1 text-xs text-[var(--text-secondary)]">
                          {instance.paused_reason}
                        </div>
                      )}
                    </td>
                    <td className="px-3 py-2 text-[var(--text-secondary)]">
                      {instance.detected_staff_code || instance.staff_code}
                    </td>
                    <td className="px-3 py-2 text-[var(--text-secondary)]">
                      {instance.board_name}
                    </td>
                    <td className="px-3 py-2 text-[var(--text-secondary)]">
                      {formatTime(instance.last_heartbeat_at)}
                    </td>
                    <td className="px-3 py-2 text-right">
                      {instance.is_paused ? (
                        <button
                          type="button"
                          onClick={() => onResume(instance)}
                          disabled={pending === instance.id}
                          className="border border-[var(--border)] px-3 py-1.5 text-xs hover:bg-[var(--surface-2)] disabled:opacity-50"
                        >
                          Resume
                        </button>
                      ) : (
                        <button
                          type="button"
                          onClick={() => onPause(instance)}
                          disabled={pending === instance.id}
                          className="border border-amber-500/40 px-3 py-1.5 text-xs text-amber-300 hover:bg-amber-500/10 disabled:opacity-50"
                        >
                          Pause
                        </button>
                      )}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </section>

      <div className="grid gap-6 lg:grid-cols-2">
        <section>
          <h2 className="mb-3 text-lg font-semibold">Active queue</h2>
          <CompactRunList runs={activeRuns} />
        </section>
        <section>
          <h2 className="mb-3 text-lg font-semibold">Stalled work</h2>
          <CompactRunList runs={stalledRuns} />
        </section>
      </div>

      <section>
        <h2 className="mb-3 text-lg font-semibold">Required MCP readiness</h2>
        <CompactMcpList mcps={mcps} />
      </section>
    </div>
  );
}

function CompactRunList({ runs }: { runs: FactoryRun[] }) {
  if (runs.length === 0) return <EmptyState>No runs in this state.</EmptyState>;
  return (
    <div className="border border-[var(--border)]">
      {runs.slice(0, 8).map((run) => (
        <div key={run.id} className="border-b border-[var(--border)] p-3 last:border-b-0">
          <div className="flex items-center justify-between gap-3">
            <div className="min-w-0">
              <div className="truncate text-sm font-medium">{run.pave_task_title || run.id}</div>
              <div className="text-xs text-[var(--text-secondary)]">
                {run.pave_task_id || 'no PAVE task'} / {run.phase}
              </div>
            </div>
            <StatusPill status={run.status} />
          </div>
        </div>
      ))}
    </div>
  );
}

function CompactMcpList({ mcps }: { mcps: FactoryMcpReadiness[] }) {
  if (mcps.length === 0) return <EmptyState>No MCP readiness has been reported.</EmptyState>;
  return (
    <div className="grid gap-3 md:grid-cols-3">
      {mcps.map((mcp) => (
        <div
          key={`${mcp.instance_id || 'global'}:${mcp.mcp_name}`}
          className="border border-[var(--border)] p-3"
        >
          <div className="flex items-center justify-between gap-2">
            <div className="font-medium">{mcp.mcp_name}</div>
            <StatusPill status={mcp.status} />
          </div>
          <div className="mt-2 text-xs text-[var(--text-secondary)]">
            {mcp.detail || 'No detail'}
          </div>
        </div>
      ))}
    </div>
  );
}

function RunsTab({
  runs,
  selectedRunId,
  selectedRun,
  pending,
  onSelectRun,
  onCopyEvidence,
}: {
  runs: FactoryRun[];
  selectedRunId: string | null;
  selectedRun: FactoryRunDetail | null;
  pending: string | null;
  onSelectRun: (runId: string) => void;
  onCopyEvidence: (runId: string) => void;
}) {
  return (
    <div className="grid gap-6 lg:grid-cols-[380px_1fr]">
      <section>
        <h2 className="mb-3 text-lg font-semibold">Runs</h2>
        {runs.length === 0 ? (
          <EmptyState>No PAVE factory runs have been recorded.</EmptyState>
        ) : (
          <div className="border border-[var(--border)]">
            {runs.map((run) => (
              <button
                key={run.id}
                type="button"
                onClick={() => onSelectRun(run.id)}
                className={`block w-full border-b border-[var(--border)] p-3 text-left last:border-b-0 ${
                  selectedRunId === run.id ? 'bg-[var(--surface-2)]' : 'hover:bg-[var(--surface-1)]'
                }`}
              >
                <div className="flex items-start justify-between gap-3">
                  <div className="min-w-0">
                    <div className="truncate text-sm font-medium">
                      {run.pave_task_title || run.id}
                    </div>
                    <div className="mt-1 text-xs text-[var(--text-secondary)]">
                      {run.pave_task_id || 'no PAVE task'} / {formatTime(run.updated_at)}
                    </div>
                  </div>
                  <StatusPill status={run.status} />
                </div>
              </button>
            ))}
          </div>
        )}
      </section>

      <section>
        <div className="mb-3 flex items-center justify-between gap-3">
          <h2 className="text-lg font-semibold">Run detail</h2>
          {selectedRun?.run.id && (
            <button
              type="button"
              onClick={() => onCopyEvidence(selectedRun.run.id)}
              disabled={pending === `evidence:${selectedRun.run.id}`}
              className="border border-[var(--border)] px-3 py-2 text-sm hover:bg-[var(--surface-2)] disabled:opacity-50"
            >
              Copy evidence report
            </button>
          )}
        </div>
        {!selectedRun ? (
          <EmptyState>Select a run to inspect the full dashboard log and artifacts.</EmptyState>
        ) : (
          <div className="space-y-5">
            <RunSummary run={selectedRun.run} />
            <RepositoryList repositories={selectedRun.repositories} />
            <ArtifactList artifacts={selectedRun.artifacts} />
            <CriticList critics={selectedRun.critic_reports} />
            <EventLog events={selectedRun.events} />
          </div>
        )}
      </section>
    </div>
  );
}

function RunSummary({ run }: { run: FactoryRun }) {
  return (
    <div className="border border-[var(--border)] p-4">
      <div className="flex flex-wrap items-start justify-between gap-3">
        <div>
          <div className="text-xs uppercase tracking-normal text-[var(--text-secondary)]">
            PAVE run
          </div>
          <h3 className="mt-1 text-lg font-semibold">{run.pave_task_title || run.id}</h3>
        </div>
        <StatusPill status={run.status} />
      </div>
      <div className="mt-4 grid gap-3 text-sm md:grid-cols-3">
        <div>
          <div className="text-xs text-[var(--text-secondary)]">Task</div>
          <div>{run.pave_task_id || '-'}</div>
        </div>
        <div>
          <div className="text-xs text-[var(--text-secondary)]">Work item</div>
          <div>{run.pave_work_item_id || '-'}</div>
        </div>
        <div>
          <div className="text-xs text-[var(--text-secondary)]">eDoc</div>
          <div>{run.e_doc_status || 'not uploaded'}</div>
        </div>
        <div>
          <div className="text-xs text-[var(--text-secondary)]">Phase</div>
          <div>{run.phase}</div>
        </div>
        <div>
          <div className="text-xs text-[var(--text-secondary)]">Staff</div>
          <div>{run.staff_code || '-'}</div>
        </div>
        <div>
          <div className="text-xs text-[var(--text-secondary)]">Updated</div>
          <div>{formatTime(run.updated_at)}</div>
        </div>
      </div>
      {run.failure_reason && (
        <div className="mt-4 border border-red-500/30 bg-red-500/10 p-3 text-sm text-red-200">
          {run.failure_reason}
        </div>
      )}
    </div>
  );
}

function RepositoryList({ repositories }: { repositories: FactoryRunRepository[] }) {
  return (
    <section>
      <h3 className="mb-2 text-base font-semibold">Repositories and PRs</h3>
      {repositories.length === 0 ? (
        <EmptyState>No repositories recorded for this run.</EmptyState>
      ) : (
        <div className="overflow-x-auto border border-[var(--border)]">
          <table className="w-full min-w-[760px] text-sm">
            <thead className="bg-[var(--surface-2)] text-left">
              <tr>
                <th className="px-3 py-2 font-medium">Repo</th>
                <th className="px-3 py-2 font-medium">Branch</th>
                <th className="px-3 py-2 font-medium">PR</th>
                <th className="px-3 py-2 font-medium">Build</th>
                <th className="px-3 py-2 font-medium">Test</th>
                <th className="px-3 py-2 font-medium">Status</th>
              </tr>
            </thead>
            <tbody>
              {repositories.map((item) => (
                <tr key={item.id} className="border-t border-[var(--border)]">
                  <td className="px-3 py-2">{item.repo_name}</td>
                  <td className="px-3 py-2 text-[var(--text-secondary)]">
                    {item.branch_name || '-'}
                  </td>
                  <td className="px-3 py-2">
                    {item.pr_url ? (
                      <a href={item.pr_url} className="text-[var(--accent)] hover:underline">
                        PR
                      </a>
                    ) : (
                      <span className="text-[var(--text-tertiary)]">-</span>
                    )}
                  </td>
                  <td className="px-3 py-2 text-[var(--text-secondary)]">
                    {item.build_status || '-'}
                  </td>
                  <td className="px-3 py-2 text-[var(--text-secondary)]">
                    {item.test_status || '-'}
                  </td>
                  <td className="px-3 py-2">
                    <StatusPill status={item.status} />
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </section>
  );
}

function ArtifactList({ artifacts }: { artifacts: FactoryArtifact[] }) {
  return (
    <section>
      <h3 className="mb-2 text-base font-semibold">Artifacts</h3>
      {artifacts.length === 0 ? (
        <EmptyState>No artifacts recorded for this run.</EmptyState>
      ) : (
        <div className="grid gap-3 md:grid-cols-2">
          {artifacts.map((artifact) => (
            <div key={artifact.id} className="border border-[var(--border)] p-3">
              <div className="flex items-start justify-between gap-3">
                <div>
                  <div className="text-xs text-[var(--text-secondary)]">{artifact.category}</div>
                  <div className="font-medium">{artifact.name}</div>
                </div>
                <StatusPill status={artifact.status} />
              </div>
              {artifact.summary && (
                <div className="mt-2 text-sm text-[var(--text-secondary)]">{artifact.summary}</div>
              )}
            </div>
          ))}
        </div>
      )}
    </section>
  );
}

function CriticList({ critics }: { critics: FactoryCriticReport[] }) {
  return (
    <section>
      <h3 className="mb-2 text-base font-semibold">Critic output</h3>
      {critics.length === 0 ? (
        <EmptyState>No critic output recorded.</EmptyState>
      ) : (
        <div className="space-y-3">
          {critics.map((critic) => (
            <div key={critic.id} className="border border-[var(--border)] p-3">
              <div className="flex items-center justify-between gap-3">
                <div className="font-medium">{critic.node_id}</div>
                <StatusPill status={critic.status} />
              </div>
              {critic.summary && (
                <div className="mt-2 text-sm text-[var(--text-secondary)]">{critic.summary}</div>
              )}
              <JsonPreview value={critic.findings} />
            </div>
          ))}
        </div>
      )}
    </section>
  );
}

function EventLog({ events }: { events: FactoryRunEvent[] }) {
  return (
    <section>
      <h3 className="mb-2 text-base font-semibold">Dashboard log</h3>
      {events.length === 0 ? (
        <EmptyState>No log entries recorded.</EmptyState>
      ) : (
        <div className="border border-[var(--border)]">
          {events.map((event, index) => (
            <div
              key={event.id || `${event.created_at}:${index}`}
              className="border-b border-[var(--border)] p-3 last:border-b-0"
            >
              <div className="flex flex-wrap items-center gap-2 text-xs text-[var(--text-secondary)]">
                <span>{formatTime(event.created_at)}</span>
                <StatusPill status={event.level} />
                <span>{event.phase || 'run'}</span>
              </div>
              <div className="mt-2 text-sm">{event.message}</div>
              {event.payload && Object.keys(event.payload).length > 0 && (
                <div className="mt-2">
                  <JsonPreview value={event.payload} />
                </div>
              )}
            </div>
          ))}
        </div>
      )}
    </section>
  );
}

function McpsTab({
  mcps,
  pending,
  onReauth,
}: {
  mcps: FactoryMcpReadiness[];
  pending: string | null;
  onReauth: (mcp: FactoryMcpReadiness) => void;
}) {
  if (mcps.length === 0) return <EmptyState>No MCP readiness rows have been reported.</EmptyState>;
  return (
    <div className="overflow-x-auto border border-[var(--border)]">
      <table className="w-full min-w-[900px] text-sm">
        <thead className="bg-[var(--surface-2)] text-left">
          <tr>
            <th className="px-3 py-2 font-medium">MCP</th>
            <th className="px-3 py-2 font-medium">Instance</th>
            <th className="px-3 py-2 font-medium">Status</th>
            <th className="px-3 py-2 font-medium">Detail</th>
            <th className="px-3 py-2 font-medium">Checked</th>
            <th className="px-3 py-2 font-medium text-right">Action</th>
          </tr>
        </thead>
        <tbody>
          {mcps.map((mcp) => {
            const key = `${mcp.instance_id || 'global'}:${mcp.mcp_name}`;
            return (
              <tr key={key} className="border-t border-[var(--border)]">
                <td className="px-3 py-2 font-medium">{mcp.mcp_name}</td>
                <td className="px-3 py-2 text-[var(--text-secondary)]">
                  {mcp.instance_id || 'global'}
                </td>
                <td className="px-3 py-2">
                  <StatusPill status={mcp.status} />
                </td>
                <td className="max-w-xl px-3 py-2 text-[var(--text-secondary)]">
                  {mcp.detail || '-'}
                </td>
                <td className="px-3 py-2 text-[var(--text-secondary)]">
                  {formatTime(mcp.last_checked_at)}
                </td>
                <td className="px-3 py-2 text-right">
                  <button
                    type="button"
                    onClick={() => onReauth(mcp)}
                    disabled={pending === key}
                    className="border border-[var(--border)] px-3 py-1.5 text-xs hover:bg-[var(--surface-2)] disabled:opacity-50"
                  >
                    Reauth
                  </button>
                </td>
              </tr>
            );
          })}
        </tbody>
      </table>
    </div>
  );
}

function ToolingTab({
  tools,
  jobs,
  pending,
  onCheck,
  onUpdate,
}: {
  tools: FactoryTool[];
  jobs: FactoryToolingJob[];
  pending: string | null;
  onCheck: () => void;
  onUpdate: (tool: FactoryTool) => void;
}) {
  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between gap-3">
        <h2 className="text-lg font-semibold">Skills, plugins, and MCP tooling</h2>
        <button
          type="button"
          onClick={onCheck}
          disabled={pending === 'tooling-check'}
          className="border border-[var(--border)] px-3 py-2 text-sm hover:bg-[var(--surface-2)] disabled:opacity-50"
        >
          Check latest
        </button>
      </div>

      {tools.length === 0 ? (
        <EmptyState>No tooling inventory has been reported.</EmptyState>
      ) : (
        <div className="overflow-x-auto border border-[var(--border)]">
          <table className="w-full min-w-[900px] text-sm">
            <thead className="bg-[var(--surface-2)] text-left">
              <tr>
                <th className="px-3 py-2 font-medium">Tool</th>
                <th className="px-3 py-2 font-medium">Type</th>
                <th className="px-3 py-2 font-medium">Installed</th>
                <th className="px-3 py-2 font-medium">Latest</th>
                <th className="px-3 py-2 font-medium">Status</th>
                <th className="px-3 py-2 font-medium text-right">Action</th>
              </tr>
            </thead>
            <tbody>
              {tools.map((tool) => (
                <tr key={tool.id} className="border-t border-[var(--border)]">
                  <td className="px-3 py-2">
                    <div className="font-medium">{tool.name}</div>
                    <div className="text-xs text-[var(--text-secondary)]">
                      {tool.source_url || '-'}
                    </div>
                  </td>
                  <td className="px-3 py-2 text-[var(--text-secondary)]">{tool.tool_type}</td>
                  <td className="px-3 py-2 text-[var(--text-secondary)]">
                    {tool.installed_version || '-'}
                  </td>
                  <td className="px-3 py-2 text-[var(--text-secondary)]">
                    {tool.latest_version || '-'}
                  </td>
                  <td className="px-3 py-2">
                    <StatusPill status={tool.update_available ? 'update_available' : tool.status} />
                  </td>
                  <td className="px-3 py-2 text-right">
                    <button
                      type="button"
                      onClick={() => onUpdate(tool)}
                      disabled={pending === tool.id}
                      className="border border-[var(--border)] px-3 py-1.5 text-xs hover:bg-[var(--surface-2)] disabled:opacity-50"
                    >
                      Update
                    </button>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}

      <section>
        <h3 className="mb-2 text-base font-semibold">Update jobs</h3>
        {jobs.length === 0 ? (
          <EmptyState>No tooling update jobs have been queued.</EmptyState>
        ) : (
          <div className="border border-[var(--border)]">
            {jobs.map((job) => (
              <div
                key={job.id}
                className="flex items-center justify-between gap-3 border-b border-[var(--border)] p-3 last:border-b-0"
              >
                <div className="min-w-0">
                  <div className="truncate text-sm font-medium">{job.tool_id || job.id}</div>
                  <div className="text-xs text-[var(--text-secondary)]">
                    {job.from_version || '-'} to {job.to_version || '-'} /{' '}
                    {formatTime(job.created_at)}
                  </div>
                </div>
                <StatusPill status={job.status} />
              </div>
            ))}
          </div>
        )}
      </section>
    </div>
  );
}

function LearningTab({ assessments }: { assessments: FactoryLearningAssessment[] }) {
  if (assessments.length === 0) {
    return (
      <EmptyState>
        No self-learning assessments have been recorded. These are created by the dedicated PAVE
        learning task after the work item.
      </EmptyState>
    );
  }
  return (
    <div className="space-y-3">
      {assessments.map((assessment) => (
        <div key={assessment.id} className="border border-[var(--border)] p-4">
          <div className="flex flex-wrap items-center justify-between gap-3">
            <div>
              <div className="text-xs text-[var(--text-secondary)]">
                PAVE task {assessment.pave_task_id || '-'} / {formatTime(assessment.updated_at)}
              </div>
              <div className="mt-1 font-medium">
                Manual changes {assessment.manual_changes_detected ? 'detected' : 'not detected'}
              </div>
            </div>
            <StatusPill status={assessment.status} />
          </div>
          {assessment.diff_summary && (
            <div className="mt-3 text-sm text-[var(--text-secondary)]">
              {assessment.diff_summary}
            </div>
          )}
          <div className="mt-3 grid gap-3 md:grid-cols-2">
            <div>
              <div className="mb-1 text-xs uppercase tracking-normal text-[var(--text-secondary)]">
                Learnings
              </div>
              <JsonPreview value={assessment.learnings} />
            </div>
            <div>
              <div className="mb-1 text-xs uppercase tracking-normal text-[var(--text-secondary)]">
                Second Brain
              </div>
              <div className="border border-[var(--border)] bg-black/20 p-3 text-sm text-[var(--text-secondary)]">
                Document: {assessment.sbkb_document_id || '-'}
                <br />
                Status: {assessment.sbkb_status || '-'}
              </div>
            </div>
          </div>
        </div>
      ))}
    </div>
  );
}
