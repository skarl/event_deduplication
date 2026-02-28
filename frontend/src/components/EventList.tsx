import { useCallback, useMemo } from 'react';
import { Link, useSearchParams } from 'react-router-dom';
import { format, parseISO } from 'date-fns';
import { useCanonicalEvents } from '../hooks/useCanonicalEvents';
import { SearchFilters } from './SearchFilters';
import { Pagination } from './Pagination';
import type { EventFilters, SortColumn, SortDir } from '../types';

function parseFiltersFromParams(params: URLSearchParams): EventFilters {
  return {
    q:          params.get('q') ?? undefined,
    cities:     params.getAll('city'),
    categories: params.getAll('category'),
    date_from:  params.get('date_from') ?? undefined,
    date_to:    params.get('date_to') ?? undefined,
    sort_by:    (params.get('sort_by') ?? 'title') as SortColumn,
    sort_dir:   (params.get('sort_dir') ?? 'asc') as SortDir,
  };
}

function filtersToParams(filters: EventFilters, page: number, size: number): URLSearchParams {
  const params = new URLSearchParams();
  if (filters.q) params.set('q', filters.q);
  filters.cities?.forEach(c => params.append('city', c));
  filters.categories?.forEach(c => params.append('category', c));
  if (filters.date_from) params.set('date_from', filters.date_from);
  if (filters.date_to) params.set('date_to', filters.date_to);
  if (filters.sort_by && filters.sort_by !== 'title') params.set('sort_by', filters.sort_by);
  if (filters.sort_dir && filters.sort_dir !== 'asc') params.set('sort_dir', filters.sort_dir);
  if (size !== 25) params.set('size', String(size));
  if (page > 1) params.set('page', String(page));
  return params;
}

function formatDate(dateStr: string): string {
  try { return format(parseISO(dateStr), 'dd.MM.yyyy'); }
  catch { return dateStr; }
}

function formatConfidence(confidence: number | null): string {
  if (confidence === null) return '-';
  return Math.round(confidence * 100) + '%';
}

interface SortableHeaderProps {
  label: string;
  column: SortColumn;
  currentSort: SortColumn;
  currentDir: SortDir;
  onSort: (col: SortColumn) => void;
  align?: 'left' | 'center';
}

function SortableHeader({ label, column, currentSort, currentDir, onSort, align = 'left' }: SortableHeaderProps) {
  const isActive = column === currentSort;
  const indicator = isActive ? (currentDir === 'asc' ? ' \u25b2' : ' \u25bc') : ' \u2195';
  return (
    <th
      className={`px-4 py-3 cursor-pointer select-none hover:bg-gray-100 ${align === 'center' ? 'text-center' : ''}`}
      onClick={() => onSort(column)}
    >
      <span className="inline-flex items-center gap-0.5">
        {label}{indicator}
      </span>
    </th>
  );
}

export function EventList() {
  const [searchParams, setSearchParams] = useSearchParams();

  const filters = useMemo(() => parseFiltersFromParams(searchParams), [searchParams]);
  const page = Number(searchParams.get('page') ?? '1');
  // size=0 means ALL in the UI; convert to 10000 for the API
  const sizeParam = Number(searchParams.get('size') ?? '25');
  const apiSize = sizeParam === 0 ? 10000 : sizeParam;

  const { data, isLoading, isError, error } = useCanonicalEvents(filters, page, apiSize);

  const handleFiltersChange = useCallback(
    (newFilters: EventFilters) => {
      setSearchParams(filtersToParams(newFilters, 1, sizeParam));
    },
    [setSearchParams, sizeParam],
  );

  const handlePageChange = useCallback(
    (newPage: number) => {
      setSearchParams(filtersToParams(filters, newPage, sizeParam));
    },
    [setSearchParams, filters, sizeParam],
  );

  const handleSortChange = useCallback(
    (column: SortColumn) => {
      const newDir: SortDir =
        filters.sort_by === column && filters.sort_dir === 'asc' ? 'desc' : 'asc';
      setSearchParams(
        filtersToParams({ ...filters, sort_by: column, sort_dir: newDir }, 1, sizeParam)
      );
    },
    [setSearchParams, filters, sizeParam],
  );

  const handleSizeChange = useCallback(
    (newSize: number) => {
      // Always reset to page 1 when changing page size
      setSearchParams(filtersToParams(filters, 1, newSize));
    },
    [setSearchParams, filters],
  );

  const sortBy = filters.sort_by ?? 'title';
  const sortDir = filters.sort_dir ?? 'asc';

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
                  <SortableHeader label="Title"      column="title"        currentSort={sortBy} currentDir={sortDir} onSort={handleSortChange} />
                  <SortableHeader label="City"       column="city"         currentSort={sortBy} currentDir={sortDir} onSort={handleSortChange} />
                  <SortableHeader label="Date"       column="date"         currentSort={sortBy} currentDir={sortDir} onSort={handleSortChange} />
                  <SortableHeader label="Categories" column="categories"   currentSort={sortBy} currentDir={sortDir} onSort={handleSortChange} />
                  <SortableHeader label="Sources"    column="source_count" currentSort={sortBy} currentDir={sortDir} onSort={handleSortChange} align="center" />
                  <SortableHeader label="Confidence" column="confidence"   currentSort={sortBy} currentDir={sortDir} onSort={handleSortChange} align="center" />
                  <SortableHeader label="Review"     column="review"       currentSort={sortBy} currentDir={sortDir} onSort={handleSortChange} align="center" />
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
                      {event.ai_assisted && (
                        <span className="ml-1.5 inline-block bg-purple-100 text-purple-800 text-xs px-1.5 py-0.5 rounded font-medium align-middle">
                          AI
                        </span>
                      )}
                    </td>
                    <td className="px-4 py-3 text-sm text-gray-600">{event.location_city ?? '-'}</td>
                    <td className="px-4 py-3 text-sm text-gray-600">
                      {event.dates && event.dates.length > 0 ? formatDate(event.dates[0].date) : '-'}
                    </td>
                    <td className="px-4 py-3">
                      <div className="flex flex-wrap gap-1">
                        {event.categories?.map(cat => (
                          <span key={cat} className="inline-block bg-blue-100 text-blue-800 text-xs px-2 py-0.5 rounded">
                            {cat}
                          </span>
                        ))}
                      </div>
                    </td>
                    <td className="px-4 py-3 text-sm text-gray-600 text-center">{event.source_count}</td>
                    <td className="px-4 py-3 text-sm text-center">
                      <span className={
                        event.match_confidence !== null && event.match_confidence >= 0.8
                          ? 'text-green-700'
                          : event.match_confidence !== null && event.match_confidence >= 0.5
                            ? 'text-yellow-700'
                            : 'text-gray-500'
                      }>
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
            size={sizeParam}
            onPageChange={handlePageChange}
            onSizeChange={handleSizeChange}
          />
        </>
      )}
    </div>
  );
}
