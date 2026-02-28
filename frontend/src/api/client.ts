import type {
  CanonicalEventDetail, CanonicalEventSummary, EventFilters, PaginatedResponse,
  SplitRequest, SplitResponse, MergeRequest, MergeResponse,
  DismissRequest, AuditLogEntry, DashboardStats, ProcessingHistoryEntry,
} from '../types';

const API_BASE = '/api';

export async function fetchCanonicalEvents(
  filters: EventFilters,
  page: number = 1,
  size: number = 20,
): Promise<PaginatedResponse<CanonicalEventSummary>> {
  const params = new URLSearchParams();
  params.set('page', String(page));
  params.set('size', String(size));
  if (filters.q) params.set('q', filters.q);
  if (filters.city) params.set('city', filters.city);
  if (filters.date_from) params.set('date_from', filters.date_from);
  if (filters.date_to) params.set('date_to', filters.date_to);
  if (filters.category) params.set('category', filters.category);

  const res = await fetch(`${API_BASE}/canonical-events?${params}`);
  if (!res.ok) throw new Error(`API error: ${res.status}`);
  return res.json();
}

export async function fetchCanonicalEventDetail(id: number): Promise<CanonicalEventDetail> {
  const res = await fetch(`${API_BASE}/canonical-events/${id}`);
  if (!res.ok) throw new Error(`API error: ${res.status}`);
  return res.json();
}

// --- Review operations ---

export async function fetchReviewQueue(
  page: number = 1,
  size: number = 20,
  minSources: number = 1,
): Promise<PaginatedResponse<CanonicalEventSummary>> {
  const params = new URLSearchParams({
    page: String(page),
    size: String(size),
    min_sources: String(minSources),
  });
  const res = await fetch(`${API_BASE}/review/queue?${params}`);
  if (!res.ok) throw new Error(`API error: ${res.status}`);
  return res.json();
}

export async function splitEvent(request: SplitRequest): Promise<SplitResponse> {
  const res = await fetch(`${API_BASE}/review/split`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(request),
  });
  if (!res.ok) {
    const err = await res.json().catch(() => ({ detail: `HTTP ${res.status}` }));
    throw new Error(err.detail || `API error: ${res.status}`);
  }
  return res.json();
}

export async function mergeEvents(request: MergeRequest): Promise<MergeResponse> {
  const res = await fetch(`${API_BASE}/review/merge`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(request),
  });
  if (!res.ok) {
    const err = await res.json().catch(() => ({ detail: `HTTP ${res.status}` }));
    throw new Error(err.detail || `API error: ${res.status}`);
  }
  return res.json();
}

export async function dismissFromQueue(
  eventId: number,
  request: DismissRequest = {},
): Promise<{ status: string }> {
  const res = await fetch(`${API_BASE}/review/queue/${eventId}/dismiss`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(request),
  });
  if (!res.ok) throw new Error(`API error: ${res.status}`);
  return res.json();
}

export async function fetchAuditLog(
  page: number = 1,
  size: number = 20,
  canonicalEventId?: number,
  actionType?: string,
): Promise<PaginatedResponse<AuditLogEntry>> {
  const params = new URLSearchParams({ page: String(page), size: String(size) });
  if (canonicalEventId) params.set('canonical_event_id', String(canonicalEventId));
  if (actionType) params.set('action_type', actionType);
  const res = await fetch(`${API_BASE}/audit-log?${params}`);
  if (!res.ok) throw new Error(`API error: ${res.status}`);
  return res.json();
}

// --- Dashboard ---

export async function fetchDashboardStats(days: number = 30): Promise<DashboardStats> {
  const res = await fetch(`${API_BASE}/dashboard/stats?days=${days}`);
  if (!res.ok) throw new Error(`API error: ${res.status}`);
  return res.json();
}

export async function fetchProcessingHistory(
  days: number = 30,
  granularity: string = 'day',
): Promise<ProcessingHistoryEntry[]> {
  const res = await fetch(`${API_BASE}/dashboard/processing-history?days=${days}&granularity=${granularity}`);
  if (!res.ok) throw new Error(`API error: ${res.status}`);
  return res.json();
}

// --- Search helper for merge/split dialogs ---

export async function searchCanonicalEvents(
  q: string,
  size: number = 10,
): Promise<PaginatedResponse<CanonicalEventSummary>> {
  const params = new URLSearchParams({ q, page: '1', size: String(size) });
  const res = await fetch(`${API_BASE}/canonical-events?${params}`);
  if (!res.ok) throw new Error(`API error: ${res.status}`);
  return res.json();
}
