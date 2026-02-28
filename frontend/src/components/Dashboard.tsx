import { useState, useMemo } from 'react';
import { useDashboardStats, useProcessingHistory } from '../hooks/useDashboard';

function formatPercent(value: number | null): string {
  if (value === null) return '-';
  return Math.round(value * 100) + '%';
}

interface StatCardProps {
  title: string;
  value: string | number;
  subtitle?: string;
  color?: string;
}

function StatCard({ title, value, subtitle, color = 'text-gray-900' }: StatCardProps) {
  return (
    <div className="bg-white rounded-lg shadow-sm border p-5">
      <div className="text-xs font-medium text-gray-500 uppercase tracking-wider">{title}</div>
      <div className={`text-2xl font-bold mt-1 ${color}`}>{value}</div>
      {subtitle && <div className="text-xs text-gray-500 mt-1">{subtitle}</div>}
    </div>
  );
}

export function Dashboard() {
  const [days, setDays] = useState(30);
  const { data: stats, isLoading: statsLoading, isError: statsError } = useDashboardStats(days);
  const { data: history, isLoading: historyLoading } = useProcessingHistory(days);

  const matchTotal = useMemo(() => {
    if (!stats) return 0;
    return stats.matches.match + stats.matches.no_match + stats.matches.ambiguous;
  }, [stats]);

  const historyMax = useMemo(() => {
    if (!history || history.length === 0) return 1;
    return Math.max(...history.map((h) => Math.max(h.files_processed, h.events_ingested)), 1);
  }, [history]);

  return (
    <div>
      {/* Header */}
      <div className="flex items-center justify-between mb-6">
        <h2 className="text-2xl font-bold text-gray-900">Processing Dashboard</h2>
        <div className="flex gap-1">
          {[7, 30, 90].map((d) => (
            <button
              key={d}
              onClick={() => setDays(d)}
              className={`px-3 py-1.5 text-sm rounded ${
                days === d
                  ? 'bg-blue-600 text-white'
                  : 'bg-gray-100 text-gray-600 hover:bg-gray-200'
              }`}
            >
              {d}d
            </button>
          ))}
        </div>
      </div>

      {statsLoading && (
        <div className="text-center py-12 text-gray-500">Loading dashboard...</div>
      )}

      {statsError && (
        <div className="text-center py-12 text-red-600">Error loading dashboard data.</div>
      )}

      {stats && (
        <>
          {/* Stats cards */}
          <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-4 mb-8">
            <StatCard
              title="Files Processed"
              value={stats.files.total_files}
              subtitle={`${stats.files.completed} completed / ${stats.files.errors} errors`}
            />
            <StatCard
              title="Events Ingested"
              value={stats.files.total_events}
            />
            <StatCard
              title="Canonical Events"
              value={stats.canonicals.total}
              subtitle={`${stats.canonicals.needs_review} needing review`}
              color={stats.canonicals.needs_review > 0 ? 'text-yellow-700' : 'text-gray-900'}
            />
            <StatCard
              title="Avg Confidence"
              value={formatPercent(stats.canonicals.avg_confidence)}
              color={
                stats.canonicals.avg_confidence !== null && stats.canonicals.avg_confidence >= 0.8
                  ? 'text-green-700'
                  : stats.canonicals.avg_confidence !== null && stats.canonicals.avg_confidence >= 0.5
                    ? 'text-yellow-700'
                    : 'text-gray-900'
              }
            />
          </div>

          {/* Match Distribution */}
          <div className="bg-white rounded-lg shadow-sm border p-6 mb-8">
            <h3 className="text-lg font-semibold text-gray-900 mb-4">Match Distribution</h3>
            {matchTotal === 0 ? (
              <p className="text-sm text-gray-500 italic">No match decisions recorded.</p>
            ) : (
              <div className="space-y-3">
                {/* Match */}
                <div className="flex items-center gap-3">
                  <span className="text-sm text-gray-600 w-24 text-right shrink-0">Match</span>
                  <div className="flex-1 bg-gray-200 rounded h-6 overflow-hidden">
                    <div
                      className="bg-green-500 rounded h-6 transition-all"
                      style={{ width: `${(stats.matches.match / matchTotal) * 100}%` }}
                    />
                  </div>
                  <span className="text-sm text-gray-700 w-16 shrink-0">{stats.matches.match}</span>
                </div>
                {/* No Match */}
                <div className="flex items-center gap-3">
                  <span className="text-sm text-gray-600 w-24 text-right shrink-0">No Match</span>
                  <div className="flex-1 bg-gray-200 rounded h-6 overflow-hidden">
                    <div
                      className="bg-gray-400 rounded h-6 transition-all"
                      style={{ width: `${(stats.matches.no_match / matchTotal) * 100}%` }}
                    />
                  </div>
                  <span className="text-sm text-gray-700 w-16 shrink-0">{stats.matches.no_match}</span>
                </div>
                {/* Ambiguous */}
                <div className="flex items-center gap-3">
                  <span className="text-sm text-gray-600 w-24 text-right shrink-0">Ambiguous</span>
                  <div className="flex-1 bg-gray-200 rounded h-6 overflow-hidden">
                    <div
                      className="bg-yellow-500 rounded h-6 transition-all"
                      style={{ width: `${(stats.matches.ambiguous / matchTotal) * 100}%` }}
                    />
                  </div>
                  <span className="text-sm text-gray-700 w-16 shrink-0">{stats.matches.ambiguous}</span>
                </div>
              </div>
            )}
          </div>
        </>
      )}

      {/* Processing History */}
      <div className="bg-white rounded-lg shadow-sm border p-6">
        <h3 className="text-lg font-semibold text-gray-900 mb-4">Processing History</h3>
        {historyLoading && (
          <div className="text-sm text-gray-500">Loading history...</div>
        )}
        {history && history.length === 0 && (
          <p className="text-sm text-gray-500 italic">No processing data available.</p>
        )}
        {history && history.length > 0 && (
          <div className="space-y-2">
            {/* Legend */}
            <div className="flex gap-4 mb-3 text-xs text-gray-500">
              <div className="flex items-center gap-1">
                <div className="w-3 h-3 bg-blue-500 rounded" />
                <span>Files processed</span>
              </div>
              <div className="flex items-center gap-1">
                <div className="w-3 h-3 bg-indigo-400 rounded" />
                <span>Events ingested</span>
              </div>
              <div className="flex items-center gap-1">
                <div className="w-3 h-3 bg-red-500 rounded" />
                <span>Errors</span>
              </div>
            </div>
            {history.map((entry) => (
              <div key={entry.date} className="flex items-center gap-3">
                <span className="text-xs text-gray-500 w-20 shrink-0 text-right">{entry.date}</span>
                <div className="flex-1 flex gap-1">
                  {/* Files bar */}
                  <div
                    className="bg-blue-500 rounded h-4 transition-all"
                    style={{ width: `${(entry.files_processed / historyMax) * 50}%`, minWidth: entry.files_processed > 0 ? '4px' : '0px' }}
                    title={`${entry.files_processed} files`}
                  />
                  {/* Events bar */}
                  <div
                    className="bg-indigo-400 rounded h-4 transition-all"
                    style={{ width: `${(entry.events_ingested / historyMax) * 50}%`, minWidth: entry.events_ingested > 0 ? '4px' : '0px' }}
                    title={`${entry.events_ingested} events`}
                  />
                  {/* Error indicator */}
                  {entry.errors > 0 && (
                    <div
                      className="bg-red-500 rounded h-4 px-1 flex items-center"
                      title={`${entry.errors} errors`}
                    >
                      <span className="text-white text-[10px] font-medium">{entry.errors}</span>
                    </div>
                  )}
                </div>
                <span className="text-xs text-gray-500 w-24 shrink-0">
                  {entry.files_processed}f / {entry.events_ingested}e
                </span>
              </div>
            ))}
          </div>
        )}
      </div>
    </div>
  );
}
