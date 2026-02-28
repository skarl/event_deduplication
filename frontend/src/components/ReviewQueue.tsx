import { useCallback, useMemo } from 'react';
import { Link, useSearchParams } from 'react-router-dom';
import { useReviewQueue, useDismissEvent } from '../hooks/useReview';
import { Pagination } from './Pagination';

function formatConfidence(confidence: number | null): string {
  if (confidence === null) return '-';
  return Math.round(confidence * 100) + '%';
}

function confidenceColor(confidence: number | null): string {
  if (confidence === null) return 'text-gray-500';
  if (confidence >= 0.8) return 'text-green-700';
  if (confidence >= 0.5) return 'text-yellow-700';
  return 'text-red-700';
}

export function ReviewQueue() {
  const [searchParams, setSearchParams] = useSearchParams();
  const page = Number(searchParams.get('page') ?? '1');

  const { data, isLoading, isError, error } = useReviewQueue(page);
  const dismissMutation = useDismissEvent();

  const handlePageChange = useCallback(
    (newPage: number) => {
      const params = new URLSearchParams();
      if (newPage > 1) params.set('page', String(newPage));
      setSearchParams(params);
    },
    [setSearchParams],
  );

  const handleDismiss = useCallback(
    (eventId: number) => {
      if (!confirm('Dismiss this event from the review queue?')) return;
      dismissMutation.mutate({ eventId });
    },
    [dismissMutation],
  );

  const totalLabel = useMemo(() => {
    if (!data) return '';
    return String(data.total);
  }, [data]);

  return (
    <div>
      {/* Header */}
      <div className="flex items-center gap-3 mb-4">
        <h2 className="text-2xl font-bold text-gray-900">Review Queue</h2>
        {totalLabel && (
          <span className="inline-block bg-yellow-100 text-yellow-800 text-sm px-2.5 py-0.5 rounded-full font-medium">
            {totalLabel}
          </span>
        )}
      </div>

      {isLoading && (
        <div className="text-center py-12 text-gray-500">Loading review queue...</div>
      )}

      {isError && (
        <div className="text-center py-12 text-red-600">
          Error loading review queue: {error instanceof Error ? error.message : 'Unknown error'}
        </div>
      )}

      {data && data.items.length === 0 && (
        <div className="text-center py-12 text-gray-500">No events need review.</div>
      )}

      {data && data.items.length > 0 && (
        <>
          <div className="bg-white rounded-lg shadow-sm border overflow-hidden">
            <table className="w-full">
              <thead>
                <tr className="border-b bg-gray-50 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                  <th className="px-4 py-3">Title</th>
                  <th className="px-4 py-3">City</th>
                  <th className="px-4 py-3 text-center">Confidence</th>
                  <th className="px-4 py-3 text-center">Sources</th>
                  <th className="px-4 py-3 text-center">Status</th>
                  <th className="px-4 py-3 text-right">Actions</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-gray-100">
                {data.items.map((event) => (
                  <tr key={event.id} className="hover:bg-gray-50">
                    <td className="px-4 py-3">
                      <Link
                        to={`/events/${event.id}`}
                        className="text-blue-600 hover:text-blue-800 hover:underline font-medium text-sm"
                      >
                        {event.title}
                      </Link>
                    </td>
                    <td className="px-4 py-3 text-sm text-gray-600">
                      {event.location_city ?? '-'}
                    </td>
                    <td className="px-4 py-3 text-sm text-center">
                      <span className={confidenceColor(event.match_confidence)}>
                        {formatConfidence(event.match_confidence)}
                      </span>
                    </td>
                    <td className="px-4 py-3 text-sm text-gray-600 text-center">
                      {event.source_count}
                    </td>
                    <td className="px-4 py-3 text-center">
                      {event.needs_review && (
                        <span className="inline-block bg-yellow-100 text-yellow-800 text-xs px-2 py-0.5 rounded font-medium">
                          Review
                        </span>
                      )}
                    </td>
                    <td className="px-4 py-3 text-right">
                      <button
                        onClick={() => handleDismiss(event.id)}
                        disabled={dismissMutation.isPending}
                        className="text-xs px-2.5 py-1 bg-gray-100 text-gray-600 border border-gray-200 rounded hover:bg-gray-200 disabled:opacity-50"
                      >
                        Dismiss
                      </button>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>

          <Pagination
            page={data.page}
            pages={data.pages}
            total={data.total}
            onPageChange={handlePageChange}
          />
        </>
      )}
    </div>
  );
}
