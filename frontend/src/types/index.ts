export interface EventDate {
  date: string;
  start_time: string | null;
  end_time: string | null;
  end_date: string | null;
}

export interface CanonicalEventSummary {
  id: number;
  title: string;
  location_city: string | null;
  dates: EventDate[] | null;
  categories: string[] | null;
  source_count: number;
  match_confidence: number | null;
  needs_review: boolean;
}

export interface SourceEventDetail {
  id: string;
  title: string;
  short_description: string | null;
  description: string | null;
  highlights: string[] | null;
  location_name: string | null;
  location_city: string | null;
  location_district: string | null;
  location_street: string | null;
  location_street_no: string | null;
  location_zipcode: string | null;
  geo_latitude: number | null;
  geo_longitude: number | null;
  geo_confidence: number | null;
  source_type: string;
  source_code: string;
  categories: string[] | null;
  is_family_event: boolean | null;
  is_child_focused: boolean | null;
  admission_free: boolean | null;
  dates: EventDate[];
}

export interface MatchDecision {
  id: number;
  source_event_id_a: string;
  source_event_id_b: string;
  combined_score: number;
  date_score: number;
  geo_score: number;
  title_score: number;
  description_score: number;
  decision: string;
  tier: string;
}

export interface CanonicalEventDetail {
  id: number;
  title: string;
  short_description: string | null;
  description: string | null;
  highlights: string[] | null;
  location_name: string | null;
  location_city: string | null;
  location_district: string | null;
  location_street: string | null;
  location_zipcode: string | null;
  geo_latitude: number | null;
  geo_longitude: number | null;
  geo_confidence: number | null;
  dates: EventDate[] | null;
  categories: string[] | null;
  is_family_event: boolean | null;
  is_child_focused: boolean | null;
  admission_free: boolean | null;
  field_provenance: Record<string, string> | null;
  source_count: number;
  match_confidence: number | null;
  needs_review: boolean;
  sources: SourceEventDetail[];
  match_decisions: MatchDecision[];
}

export interface PaginatedResponse<T> {
  items: T[];
  total: number;
  page: number;
  size: number;
  pages: number;
}

export interface EventFilters {
  q?: string;
  city?: string;
  date_from?: string;
  date_to?: string;
  category?: string;
}

// --- Review operation types ---

export interface SplitRequest {
  canonical_event_id: number;
  source_event_id: string;
  target_canonical_id?: number | null;
  operator?: string;
}

export interface SplitResponse {
  original_canonical_id: number;
  new_canonical_id: number | null;
  target_canonical_id: number | null;
  original_deleted: boolean;
}

export interface MergeRequest {
  source_canonical_id: number;
  target_canonical_id: number;
  operator?: string;
}

export interface MergeResponse {
  surviving_canonical_id: number;
  deleted_canonical_id: number;
  new_source_count: number;
}

export interface DismissRequest {
  operator?: string;
  reason?: string;
}

export interface AuditLogEntry {
  id: number;
  action_type: string;
  canonical_event_id: number | null;
  source_event_id: string | null;
  operator: string;
  details: Record<string, unknown> | null;
  created_at: string;
}

// --- Dashboard types ---

export interface FileProcessingStats {
  total_files: number;
  total_events: number;
  completed: number;
  errors: number;
}

export interface MatchDistribution {
  match: number;
  no_match: number;
  ambiguous: number;
}

export interface CanonicalStats {
  total: number;
  needs_review: number;
  avg_confidence: number | null;
}

export interface DashboardStats {
  files: FileProcessingStats;
  matches: MatchDistribution;
  canonicals: CanonicalStats;
}

export interface ProcessingHistoryEntry {
  date: string;
  files_processed: number;
  events_ingested: number;
  errors: number;
}
