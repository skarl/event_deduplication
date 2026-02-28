import { useCallback, useMemo } from 'react';
import { Link, useSearchParams } from 'react-router-dom';
import { format, parseISO } from 'date-fns';
import { useCanonicalEvents } from '../hooks/useCanonicalEvents';
import { SearchFilters } from './SearchFilters';
import { Pagination } from './Pagination';
import type { EventFilters } from '../types';

function parseFiltersFromParams(params: URLSearchParams): EventFilters {
  const filters: EventFilters = {};
  const q = params.get('q');
  const city = params.get('city');
  const date_from = params.get('date_from');
  const date_to = params.get('date_to');
  const category = params.get('category');
  if (q) filters.q = q;
  if (city) filters.city = city;
  if (date_from) filters.date_from = date_from;
  if (date_to) filters.date_to = date_to;
  if (category) filters.category = category;
  return filters;
}

function filtersToParams(filters: EventFilters, page: number): URLSearchParams {
  const params = new URLSearchParams();
  if (filters.q) params.set('q', filters.q);
  if (filters.city) params.set('city', filters.city);
  if (filters.date_from) params.set('date_from', filters.date_from);
  if (filters.date_to) params.set('date_to', filters.date_to);
  if (filters.category) params.set('category', filters.category);
  if (page > 1) params.set('page', String(page));
  return params;
}

function formatDate(dateStr: string): string {
  try {
    return format(parseISO(dateStr), 'dd.MM.yyyy');
  } catch {
    return dateStr;
  }
}

function formatConfidence(confidence: number | null): string {
  if (confidence === null) return '-';
  return Math.round(confidence * 100) + '%';
}

export function EventList() {
  const [searchParams, setSearchParams] = useSearchParams();

  const filters = useMemo(() => parseFiltersFromParams(searchParams), [searchParams]);
  const page = Number(searchParams.get('page') ?? '1');

  const { data, isLoading, isError, error } = useCanonicalEvents(filters, page);

  const handleFiltersChange = useCallback(
    (newFilters: EventFilters) => {
      setSearchParams(filtersToParams(newFilters, 1));
    },
    [setSearchParams],
  );

  const handlePageChange = useCallback(
    (newPage: number) => {
      setSearchParams(filtersToParams(filters, newPage));
    },
    [setSearchParams, filters],
  );

  return (
    <div>
      <SearchFilters filters={filters} onFiltersChange={handleFiltersChange} />

      {isLoading && (
        <div className="text-center py-12 text-gray-500">Loading events...</div>
      )}

      {isError && (
        <div className="text-center py-12 text-red-600">
          Error loading events: {error instanceof Error ? error.message : 'Unknown error'}
        </div>
      )}

      {data && data.items.length === 0 && (
        <div className="text-center py-12 text-gray-500">No events found.</div>
      )}

      {data && data.items.length > 0 && (
        <>
          <div className="bg-white rounded-lg shadow-sm border overflow-hidden">
            <table className="w-full">
              <thead>
                <tr className="border-b bg-gray-50 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                  <th className="px-4 py-3">Title</th>
                  <th className="px-4 py-3">City</th>
                  <th className="px-4 py-3">Date</th>
                  <th className="px-4 py-3">Categories</th>
                  <th className="px-4 py-3 text-center">Sources</th>
                  <th className="px-4 py-3 text-center">Confidence</th>
                  <th className="px-4 py-3 text-center">Review</th>
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
                    <td className="px-4 py-3 text-sm text-gray-600">
                      {event.dates && event.dates.length > 0
                        ? formatDate(event.dates[0].date)
                        : '-'}
                    </td>
                    <td className="px-4 py-3">
                      <div className="flex flex-wrap gap-1">
                        {event.categories?.map((cat) => (
                          <span
                            key={cat}
                            className="inline-block bg-blue-100 text-blue-800 text-xs px-2 py-0.5 rounded"
                          >
                            {cat}
                          </span>
                        ))}
                      </div>
                    </td>
                    <td className="px-4 py-3 text-sm text-gray-600 text-center">
                      {event.source_count}
                    </td>
                    <td className="px-4 py-3 text-sm text-center">
                      <span
                        className={
                          event.match_confidence !== null && event.match_confidence >= 0.8
                            ? 'text-green-700'
                            : event.match_confidence !== null && event.match_confidence >= 0.5
                              ? 'text-yellow-700'
                              : 'text-gray-500'
                        }
                      >
                        {formatConfidence(event.match_confidence)}
                      </span>
                    </td>
                    <td className="px-4 py-3 text-center">
                      {event.needs_review && (
                        <span className="inline-block bg-yellow-100 text-yellow-800 text-xs px-2 py-0.5 rounded font-medium">
                          Review
                        </span>
                      )}
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
