import { useQuery } from '@tanstack/react-query';
import { fetchDashboardStats, fetchProcessingHistory } from '../api/client';

export function useDashboardStats(days: number = 30) {
  return useQuery({
    queryKey: ['dashboard-stats', days],
    queryFn: () => fetchDashboardStats(days),
  });
}

export function useProcessingHistory(days: number = 30) {
  return useQuery({
    queryKey: ['processing-history', days],
    queryFn: () => fetchProcessingHistory(days),
  });
}
