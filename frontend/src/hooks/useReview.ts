import { useMutation, useQuery, useQueryClient, keepPreviousData } from '@tanstack/react-query';
import {
  fetchReviewQueue, splitEvent, mergeEvents, dismissFromQueue, fetchAuditLog,
} from '../api/client';
import type { SplitRequest, MergeRequest, DismissRequest } from '../types';

export function useReviewQueue(page: number, size: number = 20, minSources: number = 1) {
  return useQuery({
    queryKey: ['review-queue', page, size, minSources],
    queryFn: () => fetchReviewQueue(page, size, minSources),
    placeholderData: keepPreviousData,
  });
}

export function useSplitEvent() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (params: SplitRequest) => splitEvent(params),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['canonical-events'] });
      queryClient.invalidateQueries({ queryKey: ['canonical-event'] });
      queryClient.invalidateQueries({ queryKey: ['review-queue'] });
      queryClient.invalidateQueries({ queryKey: ['audit-log'] });
      queryClient.invalidateQueries({ queryKey: ['dashboard-stats'] });
      queryClient.invalidateQueries({ queryKey: ['processing-history'] });
    },
  });
}

export function useMergeEvents() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (params: MergeRequest) => mergeEvents(params),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['canonical-events'] });
      queryClient.invalidateQueries({ queryKey: ['canonical-event'] });
      queryClient.invalidateQueries({ queryKey: ['review-queue'] });
      queryClient.invalidateQueries({ queryKey: ['audit-log'] });
      queryClient.invalidateQueries({ queryKey: ['dashboard-stats'] });
      queryClient.invalidateQueries({ queryKey: ['processing-history'] });
    },
  });
}

export function useDismissEvent() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: ({ eventId, ...request }: DismissRequest & { eventId: number }) =>
      dismissFromQueue(eventId, request),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['review-queue'] });
      queryClient.invalidateQueries({ queryKey: ['canonical-event'] });
      queryClient.invalidateQueries({ queryKey: ['audit-log'] });
      queryClient.invalidateQueries({ queryKey: ['dashboard-stats'] });
    },
  });
}

export function useAuditLog(canonicalEventId?: number, page: number = 1, size: number = 20) {
  return useQuery({
    queryKey: ['audit-log', canonicalEventId, page, size],
    queryFn: () => fetchAuditLog(page, size, canonicalEventId),
    placeholderData: keepPreviousData,
  });
}
