import { useState, useEffect } from 'react';
import { useQuery } from '@tanstack/react-query';
import { searchCanonicalEvents } from '../api/client';
import { useSplitEvent } from '../hooks/useReview';
import type { CanonicalEventSummary } from '../types';

interface SplitDialogProps {
  canonicalEventId: number;
  sourceEventId: string;
  sourceTitle: string;
  onClose: () => void;
  onSuccess: () => void;
}

export function SplitDialog({ canonicalEventId, sourceEventId, sourceTitle, onClose, onSuccess }: SplitDialogProps) {
  const [mode, setMode] = useState<'new' | 'existing'>('new');
  const [searchQuery, setSearchQuery] = useState('');
  const [debouncedQuery, setDebouncedQuery] = useState('');
  const [selectedTarget, setSelectedTarget] = useState<CanonicalEventSummary | null>(null);
  const [operator, setOperator] = useState('');
  const [errorMsg, setErrorMsg] = useState('');

  const splitMutation = useSplitEvent();

  // Debounce search input
  useEffect(() => {
    const timer = setTimeout(() => setDebouncedQuery(searchQuery), 300);
    return () => clearTimeout(timer);
  }, [searchQuery]);

  const { data: searchResults } = useQuery({
    queryKey: ['search-canonicals', debouncedQuery],
    queryFn: () => searchCanonicalEvents(debouncedQuery),
    enabled: debouncedQuery.length >= 2,
  });

  async function handleSubmit() {
    setErrorMsg('');
    try {
      await splitMutation.mutateAsync({
        canonical_event_id: canonicalEventId,
        source_event_id: sourceEventId,
        target_canonical_id: mode === 'existing' && selectedTarget ? selectedTarget.id : undefined,
        operator: operator || undefined,
      });
      onSuccess();
    } catch (err) {
      setErrorMsg(err instanceof Error ? err.message : 'Split operation failed');
    }
  }

  return (
    <div className="fixed inset-0 bg-black/50 z-50 flex items-center justify-center p-4" onClick={onClose}>
      <div
        className="bg-white rounded-lg shadow-xl max-w-lg w-full max-h-[90vh] overflow-y-auto"
        onClick={(e) => e.stopPropagation()}
      >
        {/* Header */}
        <div className="px-6 py-4 border-b">
          <h3 className="text-lg font-semibold text-gray-900">Split Source Event</h3>
          <p className="text-sm text-gray-600 mt-1">
            Detaching: <span className="font-medium">{sourceTitle}</span>
          </p>
        </div>

        {/* Body */}
        <div className="px-6 py-4 space-y-4">
          {/* Mode selection */}
          <div className="space-y-2">
            <label className="flex items-center gap-2 cursor-pointer">
              <input
                type="radio"
                name="split-mode"
                checked={mode === 'new'}
                onChange={() => { setMode('new'); setSelectedTarget(null); }}
                className="text-blue-600"
              />
              <span className="text-sm text-gray-700">Create new canonical event</span>
            </label>
            <label className="flex items-center gap-2 cursor-pointer">
              <input
                type="radio"
                name="split-mode"
                checked={mode === 'existing'}
                onChange={() => setMode('existing')}
                className="text-blue-600"
              />
              <span className="text-sm text-gray-700">Assign to existing canonical event</span>
            </label>
          </div>

          {/* Search for existing */}
          {mode === 'existing' && (
            <div className="space-y-2">
              <input
                type="text"
                placeholder="Search canonical events..."
                value={searchQuery}
                onChange={(e) => setSearchQuery(e.target.value)}
                className="w-full px-3 py-2 border border-gray-300 rounded text-sm focus:outline-none focus:ring-1 focus:ring-blue-500 focus:border-blue-500"
              />
              {searchResults && searchResults.items.length > 0 && (
                <div className="border rounded max-h-48 overflow-y-auto divide-y">
                  {searchResults.items
                    .filter((item) => item.id !== canonicalEventId)
                    .map((item) => (
                      <button
                        key={item.id}
                        onClick={() => setSelectedTarget(item)}
                        className={`w-full text-left px-3 py-2 text-sm hover:bg-blue-50 ${
                          selectedTarget?.id === item.id ? 'bg-blue-50 border-l-2 border-l-blue-500' : ''
                        }`}
                      >
                        <div className="font-medium text-gray-900">{item.title}</div>
                        <div className="text-xs text-gray-500">
                          {item.location_city ?? 'No city'} -- {item.source_count} source{item.source_count !== 1 ? 's' : ''}
                        </div>
                      </button>
                    ))}
                </div>
              )}
              {debouncedQuery.length >= 2 && searchResults && searchResults.items.filter((i) => i.id !== canonicalEventId).length === 0 && (
                <p className="text-xs text-gray-500 italic">No matching events found.</p>
              )}
              {selectedTarget && (
                <div className="bg-blue-50 border border-blue-200 rounded px-3 py-2 text-sm">
                  Selected: <span className="font-medium">{selectedTarget.title}</span> (#{selectedTarget.id})
                </div>
              )}
            </div>
          )}

          {/* Operator */}
          <div>
            <label className="block text-xs font-medium text-gray-600 mb-1">Operator (optional)</label>
            <input
              type="text"
              placeholder="Your name..."
              value={operator}
              onChange={(e) => setOperator(e.target.value)}
              className="w-full px-3 py-1.5 border border-gray-300 rounded text-sm focus:outline-none focus:ring-1 focus:ring-blue-500 focus:border-blue-500"
            />
          </div>

          {/* Error */}
          {errorMsg && (
            <div className="bg-red-50 border border-red-200 rounded px-3 py-2 text-sm text-red-700">
              {errorMsg}
            </div>
          )}
        </div>

        {/* Footer */}
        <div className="px-6 py-4 border-t flex justify-end gap-2">
          <button
            onClick={onClose}
            className="px-4 py-2 text-sm text-gray-700 bg-gray-100 rounded hover:bg-gray-200"
          >
            Cancel
          </button>
          <button
            onClick={handleSubmit}
            disabled={splitMutation.isPending || (mode === 'existing' && !selectedTarget)}
            className="px-4 py-2 text-sm text-white bg-blue-600 rounded hover:bg-blue-700 disabled:opacity-50 disabled:cursor-not-allowed"
          >
            {splitMutation.isPending ? 'Splitting...' : 'Split'}
          </button>
        </div>
      </div>
    </div>
  );
}
