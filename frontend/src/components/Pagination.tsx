const PAGE_SIZE_OPTIONS = [25, 50, 100, 200, 0] as const;
const PAGE_SIZE_LABELS: Record<number, string> = { 0: 'ALL', 25: '25', 50: '50', 100: '100', 200: '200' };

interface PaginationProps {
  page: number;
  pages: number;
  total: number;
  size: number;
  onPageChange: (page: number) => void;
  onSizeChange: (size: number) => void;
}

export function Pagination({ page, pages, total, size, onPageChange, onSizeChange }: PaginationProps) {
  return (
    <div className="flex items-center justify-between mt-4 px-1">
      {/* Left: rows-per-page selector */}
      <div className="flex items-center gap-2">
        <span className="text-xs text-gray-500">Rows:</span>
        <select
          value={size}
          onChange={e => onSizeChange(Number(e.target.value))}
          className="text-sm border border-gray-300 rounded px-2 py-1 focus:outline-none focus:ring-1 focus:ring-blue-500"
        >
          {PAGE_SIZE_OPTIONS.map(opt => (
            <option key={opt} value={opt}>{PAGE_SIZE_LABELS[opt]}</option>
          ))}
        </select>
      </div>
      {/* Center: page info */}
      <span className="text-sm text-gray-600">
        Page {page} of {pages} ({total} results)
      </span>
      {/* Right: prev/next */}
      <div className="flex gap-2">
        <button
          onClick={() => onPageChange(page - 1)}
          disabled={page <= 1}
          className="px-3 py-1.5 text-sm border border-gray-300 rounded hover:bg-gray-50 disabled:opacity-40 disabled:cursor-not-allowed"
        >
          Previous
        </button>
        <button
          onClick={() => onPageChange(page + 1)}
          disabled={page >= pages}
          className="px-3 py-1.5 text-sm border border-gray-300 rounded hover:bg-gray-50 disabled:opacity-40 disabled:cursor-not-allowed"
        >
          Next
        </button>
      </div>
    </div>
  );
}
