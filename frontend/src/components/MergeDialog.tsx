import { useState, useEffect } from 'react';
import { useNavigate } from 'react-router-dom';
import { useQuery } from '@tanstack/react-query';
import { searchCanonicalEvents } from '../api/client';
import { useMergeEvents } from '../hooks/useReview';
import type { CanonicalEventSummary } from '../types';

interface MergeDialogProps {
  canonicalEventId: number;
  canonicalTitle: string;
  onClose: () => void;
  onSuccess: () => void;
}

export function MergeDialog({ canonicalEventId, canonicalTitle, onClose, onSuccess }: MergeDialogProps) {
  const navigate = useNavigate();
  const [searchQuery, setSearchQuery] = useState('');
  const [debouncedQuery, setDebouncedQuery] = useState('');
  const [selectedTarget, setSelectedTarget] = useState<CanonicalEventSummary | null>(null);
  const [operator, setOperator] = useState('');
  const [errorMsg, setErrorMsg] = useState('');

  const mergeMutation = useMergeEvents();

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
    if (!selectedTarget) return;
    setErrorMsg('');
    try {
      const result = await mergeMutation.mutateAsync({
        source_canonical_id: canonicalEventId,
        target_canonical_id: selectedTarget.id,
        operator: operator || undefined,
      });
      onSuccess();
      // Navigate to the surviving event since current one is deleted
      navigate(`/events/${result.surviving_canonical_id}`);
    } catch (err) {
      setErrorMsg(err instanceof Error ? err.message : 'Merge operation failed');
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
          <h3 className="text-lg font-semibold text-gray-900">Merge with Another Event</h3>
          <p className="text-sm text-gray-600 mt-1">
            Current event: <span className="font-medium">{canonicalTitle}</span>
          </p>
        </div>

        {/* Body */}
        <div className="px-6 py-4 space-y-4">
          {/* Search */}
          <div className="space-y-2">
            <label className="block text-xs font-medium text-gray-600 mb-1">
              Search for target canonical event
            </label>
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
          </div>

          {/* Direction indicator */}
          {selectedTarget && (
            <div className="bg-orange-50 border border-orange-200 rounded px-4 py-3">
              <p className="text-sm text-orange-800">
                Merging <span className="font-medium">{canonicalTitle}</span>{' '}
                <span className="text-orange-600">INTO</span>{' '}
                <span className="font-medium">{selectedTarget.title}</span>
              </p>
              <p className="text-xs text-orange-600 mt-1">
                The current event will be deleted. Its sources will be transferred to the target event.
              </p>
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
            disabled={mergeMutation.isPending || !selectedTarget}
            className="px-4 py-2 text-sm text-white bg-orange-600 rounded hover:bg-orange-700 disabled:opacity-50 disabled:cursor-not-allowed"
          >
            {mergeMutation.isPending ? 'Merging...' : 'Merge'}
          </button>
        </div>
      </div>
    </div>
  );
}
