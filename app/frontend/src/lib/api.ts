/**
 * Typed fetch wrappers for the PAVE Dark Factory portal and inherited chat API.
 */

const BASE = '/api';

/**
 * Thrown when POST /api/conversations/{id}/messages returns 429.
 * Carries the shape of the rate_limit_exceeded JSON body so the chat UI
 * can render a friendly "daily limit hit, resets at HH:MM" message.
 * MISSION §10 invariant #1 is the governing cap (25/24h, hardcoded).
 */
export class RateLimitError extends Error {
  limit: number;
  windowHours: number;
  resetAt: string; // ISO timestamp of oldest_in_window + 24h

  constructor(body: { limit: number; window_hours: number; reset_at: string }) {
    super('rate_limit_exceeded');
    this.limit = body.limit;
    this.windowHours = body.window_hours;
    this.resetAt = body.reset_at;
  }
}

export interface Video {
  id: string;
  title: string;
  description: string;
  url: string;
  created_at: string;
  channel_id?: string;
  channel_title?: string;
  source_type?: 'youtube' | 'dynamous' | string;
  lesson_url?: string;
}

export interface Conversation {
  id: string;
  title: string;
  created_at: string;
  updated_at: string;
  preview?: string | null;
}

export interface Citation {
  chunk_id: string;
  video_id: string;
  video_title: string;
  video_url: string;
  start_seconds: number;
  end_seconds: number;
  snippet: string;
  /**
   * True when the LLM emitted a `[c:<chunk_id>]` marker referencing this
   * chunk in its final answer. Drives the two-tier "Sources cited" /
   * "All sources consulted" render. Optional for backward compatibility
   * with messages persisted before the two-tier system shipped.
   */
  is_cited?: boolean;
  /**
   * Discriminator for the citation rendering split. 'youtube' (default)
   * gets the embedded player + ?t= deep link. 'dynamous' (paid course /
   * workshop content) gets a static link to `lesson_url` because Circle
   * doesn't support timestamp deep links. Optional for backward
   * compatibility with messages persisted before issue #147.
   */
  source_type?: 'youtube' | 'dynamous' | string;
  /**
   * Circle lesson/workshop URL — populated for `source_type === 'dynamous'`,
   * empty for YouTube citations.
   */
  lesson_url?: string;
  /**
   * Number of transcript segments collapsed into this citation (issue #208).
   * Only present for citations generated server-side after collapse.
   */
  segment_count?: number;
}

export interface Message {
  id: string;
  conversation_id: string;
  role: 'user' | 'assistant';
  content: string;
  created_at: string;
  /** RAG citations — only populated for freshly-streamed assistant messages */
  sources?: Citation[];
}

export interface ConversationWithMessages extends Conversation {
  messages: Message[];
}

/**
 * Thrown by `request()` whenever a non-2xx response comes back. Carries the
 * status and parsed `detail` so callers can render friendly UI (e.g.,
 * a real 404 page on a missing conversation, instead of dumping JSON).
 */
export class ApiError extends Error {
  status: number;
  detail: string;

  constructor(status: number, detail: string) {
    super(`API error ${status}: ${detail}`);
    this.name = 'ApiError';
    this.status = status;
    this.detail = detail;
  }
}

// Try to extract `detail` from the FastAPI JSON error envelope, fall
// back to raw text so we still surface unexpected responses.
async function parseErrorDetail(res: Response): Promise<string> {
  const text = await res.text();
  try {
    const parsed = JSON.parse(text) as { detail?: string };
    if (typeof parsed?.detail === 'string') return parsed.detail;
  } catch {
    // not JSON — keep text as-is
  }
  return text;
}

async function request<T>(path: string, options?: RequestInit): Promise<T> {
  const res = await fetch(`${BASE}${path}`, {
    credentials: 'include',
    headers: { 'Content-Type': 'application/json' },
    ...options,
  });
  if (res.status === 401) {
    // Session missing/expired — bounce to login, preserving return path.
    if (typeof window !== 'undefined' && !window.location.pathname.startsWith('/login')) {
      const returnTo = window.location.pathname + window.location.search;
      window.location.assign(`/login?from=${encodeURIComponent(returnTo)}`);
    }
    throw new ApiError(401, 'Not authenticated');
  }
  if (!res.ok) {
    throw new ApiError(res.status, await parseErrorDetail(res));
  }
  return res.json() as Promise<T>;
}

async function requestText(path: string, options?: RequestInit): Promise<string> {
  const res = await fetch(`${BASE}${path}`, {
    credentials: 'include',
    headers: { 'Content-Type': 'application/json' },
    ...options,
  });
  if (res.status === 401) {
    if (typeof window !== 'undefined' && !window.location.pathname.startsWith('/login')) {
      const returnTo = window.location.pathname + window.location.search;
      window.location.assign(`/login?from=${encodeURIComponent(returnTo)}`);
    }
    throw new ApiError(401, 'Not authenticated');
  }
  if (!res.ok) {
    throw new ApiError(res.status, await parseErrorDetail(res));
  }
  return res.text();
}

// Conversations
export const getConversations = () => request<Conversation[]>('/conversations');
export const searchConversations = (q: string) =>
  request<Conversation[]>(`/conversations/search?q=${encodeURIComponent(q)}`);
export const createConversation = () =>
  request<Conversation>('/conversations', { method: 'POST', body: '{}' });
export const getConversation = (id: string) =>
  request<ConversationWithMessages>(`/conversations/${id}`);
export const deleteConversation = (id: string) =>
  fetch(`${BASE}/conversations/${id}`, { method: 'DELETE', credentials: 'include' });
export const renameConversation = (id: string, title: string) =>
  request<Conversation>(`/conversations/${id}`, {
    method: 'PATCH',
    body: JSON.stringify({ title }),
  });

// Videos
export const getVideos = () => request<Video[]>('/videos');

export interface IngestVideoBody {
  title: string;
  description: string;
  url: string;
  transcript: string;
}

export interface IngestVideoResponse {
  video_id: string;
  chunks_created: number;
  status: string;
}

export const ingestVideo = (body: IngestVideoBody) =>
  request<IngestVideoResponse>('/ingest', {
    method: 'POST',
    body: JSON.stringify(body),
  });

// Health
export const getHealth = () =>
  request<{ status: string; video_count: number; chunk_count: number; db_path: string }>('/health');

// ─── Admin ────────────────────────────────────────────────────────────────
// All /api/admin/* endpoints require the configured ADMIN_USER_EMAIL; the
// backend returns 403 for any other authenticated user. Callers should gate
// UI with `useAuth().user?.is_admin` first, but never rely on it for security.

export interface AdminVideo extends Video {
  chunk_count: number;
}

export interface AdminVideosResponse {
  videos: AdminVideo[];
}

export interface AddVideoResponse {
  video_id: string;
  chunks_created: number;
  status: string;
}

export interface SyncChannelResponse {
  sync_run_id: string;
  status: string;
  videos_total: number;
  videos_new: number;
  videos_error: number;
}

export const listAdminVideos = () => request<AdminVideosResponse>('/admin/videos');

export const searchAdminVideos = (q: string) =>
  request<AdminVideosResponse>(`/admin/videos/search?q=${encodeURIComponent(q)}`);

export const addVideoByUrl = (url: string) =>
  request<AddVideoResponse>('/admin/videos', {
    method: 'POST',
    body: JSON.stringify({ url }),
  });

export const deleteVideo = async (id: string): Promise<void> => {
  const res = await fetch(`${BASE}/admin/videos/${id}`, {
    method: 'DELETE',
    credentials: 'include',
  });
  if (!res.ok) {
    throw new ApiError(res.status, await parseErrorDetail(res));
  }
};

export const resyncVideo = (id: string) =>
  request<AddVideoResponse>(`/admin/videos/${id}/re-sync`, { method: 'POST' });

export const syncChannel = () =>
  request<SyncChannelResponse>('/admin/videos/sync-channel', { method: 'POST' });

// ─── PAVE Factory ────────────────────────────────────────────────────────

export type FactoryStatus =
  | 'ready'
  | 'running'
  | 'queued'
  | 'claimed'
  | 'stalled'
  | 'paused'
  | 'failed'
  | 'suspended'
  | 'completed'
  | string;

export interface FactorySummary {
  instances_total: number;
  instances_ready: number;
  instances_paused: number;
  runs_active: number;
  runs_stalled: number;
  runs_failed: number;
  tooling_updates_available: number;
  learning_pending: number;
  stalled_mcp_count: number;
}

export interface FactoryConfig {
  board_name: string;
  execution_staff_code: string;
  guardian_staff_code: string;
  scout_dry_run: boolean;
  archon_execute: boolean;
}

export interface FactoryInstance {
  id: string;
  name: string;
  host_name: string;
  staff_code: string;
  detected_staff_code?: string | null;
  board_name: string;
  status: FactoryStatus;
  is_paused: boolean;
  paused_reason?: string | null;
  version?: string | null;
  process_id?: string | null;
  capabilities: Record<string, unknown>;
  config: Record<string, unknown>;
  last_heartbeat_at?: string | null;
  updated_at: string;
}

export interface FactoryMcpReadiness {
  id: string;
  instance_id?: string | null;
  mcp_name: string;
  status: FactoryStatus;
  detail?: string | null;
  auth_subject?: string | null;
  reauth_url?: string | null;
  last_checked_at: string;
  expires_at?: string | null;
  metadata: Record<string, unknown>;
}

export interface FactoryRun {
  id: string;
  instance_id?: string | null;
  pave_task_id?: string | null;
  pave_work_item_id?: string | null;
  pave_incident_id?: string | null;
  pave_task_title: string;
  pave_board_name: string;
  staff_code: string;
  status: FactoryStatus;
  phase: string;
  failure_reason?: string | null;
  workflow_id?: string | null;
  workflow_name?: string | null;
  e_doc_report_id?: string | null;
  e_doc_status?: string | null;
  dashboard_log: FactoryRunEvent[];
  metadata: Record<string, unknown>;
  updated_at: string;
  created_at: string;
}

export interface FactoryRunEvent {
  id?: string;
  run_id?: string;
  instance_id?: string | null;
  level: string;
  phase: string;
  message: string;
  payload?: Record<string, unknown>;
  created_at: string;
}

export interface FactoryRunRepository {
  id: string;
  run_id: string;
  repo_name: string;
  repo_path: string;
  remote_url: string;
  base_branch: string;
  branch_name: string;
  status: FactoryStatus;
  pr_url?: string | null;
  build_status?: string | null;
  test_status?: string | null;
}

export interface FactoryArtifact {
  id: string;
  run_id?: string | null;
  repository_id?: string | null;
  category: string;
  name: string;
  status: FactoryStatus;
  storage_uri?: string | null;
  content_type?: string | null;
  summary?: string | null;
  created_at: string;
}

export interface FactoryCriticReport {
  id: string;
  run_id: string;
  node_id: string;
  status: FactoryStatus;
  summary?: string | null;
  findings: Array<Record<string, unknown>>;
  score?: number | null;
  created_at: string;
}

export interface FactoryEdocUpload {
  id: string;
  run_id: string;
  status: FactoryStatus;
  document_id?: string | null;
  file_name: string;
  full_log_included: boolean;
  critic_output_included: boolean;
  error_message?: string | null;
}

export interface FactoryRunDetail {
  run: FactoryRun;
  events: FactoryRunEvent[];
  repositories: FactoryRunRepository[];
  artifacts: FactoryArtifact[];
  critic_reports: FactoryCriticReport[];
  edoc_uploads: FactoryEdocUpload[];
}

export interface FactoryTool {
  id: string;
  instance_id?: string | null;
  tool_type: string;
  name: string;
  installed_version?: string | null;
  latest_version?: string | null;
  status: FactoryStatus;
  source_url?: string | null;
  update_available: boolean;
  last_checked_at?: string | null;
  metadata: Record<string, unknown>;
}

export interface FactoryToolingJob {
  id: string;
  instance_id?: string | null;
  tool_id?: string | null;
  status: FactoryStatus;
  from_version?: string | null;
  to_version?: string | null;
  error_message?: string | null;
  created_at: string;
}

export interface FactoryLearningAssessment {
  id: string;
  run_id?: string | null;
  pave_task_id?: string | null;
  status: FactoryStatus;
  manual_changes_detected: boolean;
  diff_summary?: string | null;
  learnings: Array<Record<string, unknown>>;
  sbkb_document_id?: string | null;
  sbkb_status?: string | null;
  updated_at: string;
}

export const getFactorySummary = () => request<FactorySummary>('/factory/dashboard/summary');
export const getFactoryConfig = () => request<FactoryConfig>('/factory/dashboard/config');
export const getFactoryStalled = () =>
  request<{ mcps: FactoryMcpReadiness[]; runs: FactoryRun[] }>('/factory/dashboard/stalled');
export const getFactoryQueue = () => request<{ runs: FactoryRun[] }>('/factory/dashboard/queue');
export const getFactoryThroughput = () =>
  request<{ days: Array<Record<string, unknown>> }>('/factory/dashboard/throughput');
export const listFactoryInstances = () =>
  request<{ instances: FactoryInstance[] }>('/factory/instances');
export const pauseFactoryInstance = (id: string, reason: string) =>
  request<FactoryInstance>(`/factory/instances/${id}/pause`, {
    method: 'POST',
    body: JSON.stringify({ reason }),
  });
export const resumeFactoryInstance = (id: string) =>
  request<FactoryInstance>(`/factory/instances/${id}/resume`, { method: 'POST' });
export const listFactoryMcpReadiness = () =>
  request<{ mcps: FactoryMcpReadiness[] }>('/factory/mcps/readiness');
export const requestFactoryMcpReauth = (
  mcpName: string,
  instanceId?: string | null,
  reauthUrl?: string | null,
) =>
  request<Record<string, unknown>>('/factory/mcps/reauth', {
    method: 'POST',
    body: JSON.stringify({
      mcp_name: mcpName,
      instance_id: instanceId,
      reauth_url: reauthUrl,
    }),
  });
export const listFactoryRuns = () => request<{ runs: FactoryRun[] }>('/factory/runs');
export const getFactoryRun = (runId: string) => request<FactoryRunDetail>(`/factory/runs/${runId}`);
export const getFactoryEvidenceReport = (runId: string) =>
  requestText(`/factory/runs/${runId}/evidence-report`);
export const listFactoryTooling = () =>
  request<{ tools: FactoryTool[]; update_jobs: FactoryToolingJob[] }>('/factory/tooling');
export const checkLatestFactoryTooling = () =>
  request<{ tools: FactoryTool[] }>('/factory/tooling/check-latest', { method: 'POST' });
export const updateFactoryTooling = (toolId: string, toVersion?: string | null) =>
  request<FactoryToolingJob>(`/factory/tooling/${toolId}/update`, {
    method: 'POST',
    body: JSON.stringify({ to_version: toVersion }),
  });
export const listFactoryLearningAssessments = () =>
  request<{ assessments: FactoryLearningAssessment[] }>('/factory/learning-assessments');
