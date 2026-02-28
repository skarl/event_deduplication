import { useState } from 'react';
import { exportEvents } from '../api/client';
import type { ExportParams } from '../types';

export function ExportPage() {
  const [createdAfter, setCreatedAfter] = useState('');
  const [modifiedAfter, setModifiedAfter] = useState('');
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [success, setSuccess] = useState(false);

  const handleClearFilters = () => {
    setCreatedAfter('');
    setModifiedAfter('');
    setError(null);
    setSuccess(false);
  };

  const handleExport = async () => {
    setLoading(true);
    setError(null);
    setSuccess(false);

    const params: ExportParams = {
      created_after: createdAfter || null,
      modified_after: modifiedAfter || null,
    };

    try {
      await exportEvents(params);
      setSuccess(true);
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Export failed');
    } finally {
      setLoading(false);
    }
  };

  return (
    <div>
      <h2 className="text-2xl font-bold text-gray-900 mb-2">Export Events</h2>
      <p className="text-sm text-gray-600 mb-6">
        Export canonical events as JSON files matching the input format.
        Events are split into files of max 200 events each.
      </p>

      <div className="bg-white rounded-lg shadow-sm border p-6 space-y-5">
        <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
          <div>
            <label className="block text-sm font-medium text-gray-700 mb-1">
              Created After
            </label>
            <input
              type="datetime-local"
              value={createdAfter}
              onChange={(e) => setCreatedAfter(e.target.value)}
              className="border rounded px-3 py-2 w-full text-sm"
            />
          </div>
          <div>
            <label className="block text-sm font-medium text-gray-700 mb-1">
              Modified After
            </label>
            <input
              type="datetime-local"
              value={modifiedAfter}
              onChange={(e) => setModifiedAfter(e.target.value)}
              className="border rounded px-3 py-2 w-full text-sm"
            />
          </div>
        </div>

        <div className="flex gap-3">
          <button
            onClick={handleClearFilters}
            className="px-4 py-2 text-sm font-medium text-gray-700 border border-gray-300 rounded hover:bg-gray-50"
          >
            Clear Filters
          </button>
          <button
            onClick={handleExport}
            disabled={loading}
            className="px-4 py-2 bg-blue-600 text-white text-sm font-medium rounded hover:bg-blue-700 disabled:opacity-50 disabled:cursor-not-allowed"
          >
            {loading ? 'Exporting...' : 'Export'}
          </button>
        </div>

        {error && (
          <div className="text-sm text-red-600 bg-red-50 border border-red-200 rounded px-3 py-2">
            {error}
          </div>
        )}

        {success && (
          <div className="text-sm text-green-600 bg-green-50 border border-green-200 rounded px-3 py-2">
            Download started
          </div>
        )}
      </div>
    </div>
  );
}
