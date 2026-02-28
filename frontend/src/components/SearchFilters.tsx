import { useState, type FormEvent } from 'react';
import type { EventFilters } from '../types';

interface SearchFiltersProps {
  filters: EventFilters;
  onFiltersChange: (filters: EventFilters) => void;
}

export function SearchFilters({ filters, onFiltersChange }: SearchFiltersProps) {
  const [localFilters, setLocalFilters] = useState<EventFilters>(filters);

  function handleSubmit(e: FormEvent) {
    e.preventDefault();
    onFiltersChange(localFilters);
  }

  function handleClear() {
    const cleared: EventFilters = {};
    setLocalFilters(cleared);
    onFiltersChange(cleared);
  }

  return (
    <form onSubmit={handleSubmit} className="bg-white rounded-lg shadow-sm border p-4 mb-4">
      <div className="flex flex-wrap gap-3 items-end">
        <div className="flex-1 min-w-[160px]">
          <label className="block text-xs font-medium text-gray-600 mb-1">Title search</label>
          <input
            type="text"
            placeholder="Search events..."
            value={localFilters.q ?? ''}
            onChange={(e) => setLocalFilters({ ...localFilters, q: e.target.value })}
            className="w-full px-3 py-1.5 border border-gray-300 rounded text-sm focus:outline-none focus:ring-1 focus:ring-blue-500 focus:border-blue-500"
          />
        </div>
        <div className="min-w-[120px]">
          <label className="block text-xs font-medium text-gray-600 mb-1">City</label>
          <input
            type="text"
            placeholder="City..."
            value={localFilters.city ?? ''}
            onChange={(e) => setLocalFilters({ ...localFilters, city: e.target.value })}
            className="w-full px-3 py-1.5 border border-gray-300 rounded text-sm focus:outline-none focus:ring-1 focus:ring-blue-500 focus:border-blue-500"
          />
        </div>
        <div className="min-w-[140px]">
          <label className="block text-xs font-medium text-gray-600 mb-1">Date from</label>
          <input
            type="date"
            value={localFilters.date_from ?? ''}
            onChange={(e) => setLocalFilters({ ...localFilters, date_from: e.target.value })}
            className="w-full px-3 py-1.5 border border-gray-300 rounded text-sm focus:outline-none focus:ring-1 focus:ring-blue-500 focus:border-blue-500"
          />
        </div>
        <div className="min-w-[140px]">
          <label className="block text-xs font-medium text-gray-600 mb-1">Date to</label>
          <input
            type="date"
            value={localFilters.date_to ?? ''}
            onChange={(e) => setLocalFilters({ ...localFilters, date_to: e.target.value })}
            className="w-full px-3 py-1.5 border border-gray-300 rounded text-sm focus:outline-none focus:ring-1 focus:ring-blue-500 focus:border-blue-500"
          />
        </div>
        <div className="min-w-[120px]">
          <label className="block text-xs font-medium text-gray-600 mb-1">Category</label>
          <input
            type="text"
            placeholder="Category..."
            value={localFilters.category ?? ''}
            onChange={(e) => setLocalFilters({ ...localFilters, category: e.target.value })}
            className="w-full px-3 py-1.5 border border-gray-300 rounded text-sm focus:outline-none focus:ring-1 focus:ring-blue-500 focus:border-blue-500"
          />
        </div>
        <div className="flex gap-2">
          <button
            type="submit"
            className="px-4 py-1.5 bg-blue-600 text-white text-sm rounded hover:bg-blue-700 focus:outline-none focus:ring-2 focus:ring-blue-500"
          >
            Search
          </button>
          <button
            type="button"
            onClick={handleClear}
            className="px-4 py-1.5 bg-gray-100 text-gray-700 text-sm rounded hover:bg-gray-200 focus:outline-none focus:ring-2 focus:ring-gray-400"
          >
            Clear
          </button>
        </div>
      </div>
    </form>
  );
}
