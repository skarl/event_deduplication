import { useState, type FormEvent } from 'react';
import type { EventFilters } from '../types';
import { ChipSelector } from './ChipSelector';
import { useDistinctCategories, useDistinctCities } from '../hooks/useCanonicalEvents';

interface SearchFiltersProps {
  filters: EventFilters;
  onFiltersChange: (filters: EventFilters) => void;
}

export function SearchFilters({ filters, onFiltersChange }: SearchFiltersProps) {
  // Local state only for text fields that require form submit
  const [localQ, setLocalQ] = useState(filters.q ?? '');
  const [localDateFrom, setLocalDateFrom] = useState(filters.date_from ?? '');
  const [localDateTo, setLocalDateTo] = useState(filters.date_to ?? '');

  const { data: categoryOptions = [] } = useDistinctCategories();
  const { data: cityOptions = [] } = useDistinctCities();

  function handleSubmit(e: FormEvent) {
    e.preventDefault();
    onFiltersChange({
      ...filters,
      q: localQ || undefined,
      date_from: localDateFrom || undefined,
      date_to: localDateTo || undefined,
    });
  }

  function handleClear() {
    setLocalQ('');
    setLocalDateFrom('');
    setLocalDateTo('');
    onFiltersChange({});
  }

  return (
    <form onSubmit={handleSubmit} className="bg-white rounded-lg shadow-sm border p-4 mb-4">
      <div className="flex flex-wrap gap-3 items-end">
        <div className="flex-1 min-w-[160px]">
          <label className="block text-xs font-medium text-gray-600 mb-1">Title search</label>
          <input
            type="text"
            placeholder="Search events..."
            value={localQ}
            onChange={e => setLocalQ(e.target.value)}
            className="w-full px-3 py-1.5 border border-gray-300 rounded text-sm focus:outline-none focus:ring-1 focus:ring-blue-500 focus:border-blue-500"
          />
        </div>
        <ChipSelector
          label="City"
          options={cityOptions}
          selected={filters.cities ?? []}
          onChange={cities => onFiltersChange({ ...filters, cities })}
          placeholder="Add city..."
        />
        <div className="min-w-[140px]">
          <label className="block text-xs font-medium text-gray-600 mb-1">Date from</label>
          <input
            type="date"
            value={localDateFrom}
            onChange={e => setLocalDateFrom(e.target.value)}
            className="w-full px-3 py-1.5 border border-gray-300 rounded text-sm focus:outline-none focus:ring-1 focus:ring-blue-500 focus:border-blue-500"
          />
        </div>
        <div className="min-w-[140px]">
          <label className="block text-xs font-medium text-gray-600 mb-1">Date to</label>
          <input
            type="date"
            value={localDateTo}
            onChange={e => setLocalDateTo(e.target.value)}
            className="w-full px-3 py-1.5 border border-gray-300 rounded text-sm focus:outline-none focus:ring-1 focus:ring-blue-500 focus:border-blue-500"
          />
        </div>
        <ChipSelector
          label="Category"
          options={categoryOptions}
          selected={filters.categories ?? []}
          onChange={categories => onFiltersChange({ ...filters, categories })}
          placeholder="Add category..."
        />
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
