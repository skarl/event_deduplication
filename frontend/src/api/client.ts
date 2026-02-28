import type { CanonicalEventDetail, CanonicalEventSummary, EventFilters, PaginatedResponse } from '../types';

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
