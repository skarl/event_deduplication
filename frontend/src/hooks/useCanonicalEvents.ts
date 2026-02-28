import { useQuery, keepPreviousData } from '@tanstack/react-query';
import {
  fetchCanonicalEvents,
  fetchCanonicalEventDetail,
  fetchDistinctCategories,
  fetchDistinctCities,
} from '../api/client';
import type { EventFilters } from '../types';

export function useCanonicalEvents(filters: EventFilters, page: number, size: number = 25) {
  return useQuery({
    queryKey: ['canonical-events', filters, page, size],
    queryFn: () => fetchCanonicalEvents(filters, page, size),
    placeholderData: keepPreviousData,
  });
}

export function useCanonicalEventDetail(id: number) {
  return useQuery({
    queryKey: ['canonical-event', id],
    queryFn: () => fetchCanonicalEventDetail(id),
    enabled: id > 0,
  });
}

export function useDistinctCategories() {
  return useQuery({
    queryKey: ['distinct-categories'],
    queryFn: fetchDistinctCategories,
    staleTime: 300_000, // 5 min — values change only when new events are ingested
  });
}

export function useDistinctCities() {
  return useQuery({
    queryKey: ['distinct-cities'],
    queryFn: fetchDistinctCities,
    staleTime: 300_000,
  });
}
