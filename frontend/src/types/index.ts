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
