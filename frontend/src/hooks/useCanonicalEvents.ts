import { useQuery, keepPreviousData } from '@tanstack/react-query';
import { fetchCanonicalEvents, fetchCanonicalEventDetail } from '../api/client';
import type { EventFilters } from '../types';

export function useCanonicalEvents(filters: EventFilters, page: number, size: number = 20) {
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
