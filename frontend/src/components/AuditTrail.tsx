import { format, parseISO } from 'date-fns';
import { useAuditLog } from '../hooks/useReview';
import type { AuditLogEntry } from '../types';

interface AuditTrailProps {
  canonicalEventId: number;
}

function formatActionType(action: string): string {
  switch (action) {
    case 'split': return 'Split';
    case 'merge': return 'Merge';
    case 'review_dismiss': return 'Dismissed';
    default: return action;
  }
}

function actionColor(action: string): string {
  switch (action) {
    case 'split': return 'border-l-blue-500 bg-blue-50';
    case 'merge': return 'border-l-green-500 bg-green-50';
    case 'review_dismiss': return 'border-l-gray-400 bg-gray-50';
    default: return 'border-l-gray-300 bg-gray-50';
  }
}

function actionBadgeColor(action: string): string {
  switch (action) {
    case 'split': return 'bg-blue-100 text-blue-800';
    case 'merge': return 'bg-green-100 text-green-800';
    case 'review_dismiss': return 'bg-gray-100 text-gray-700';
    default: return 'bg-gray-100 text-gray-700';
  }
}

function formatTimestamp(ts: string): string {
  try {
    return format(parseISO(ts), 'dd.MM.yyyy HH:mm');
  } catch {
    return ts;
  }
}

function detailsSummary(entry: AuditLogEntry): string {
  const details = entry.details as Record<string, unknown> | null;
  switch (entry.action_type) {
    case 'split':
      if (entry.source_event_id) {
        return `Detached source ${entry.source_event_id}`;
      }
      return 'Source event split';
    case 'merge':
      if (details?.deleted_canonical_id) {
        return `Merged from canonical #${details.deleted_canonical_id}`;
      }
      return 'Events merged';
    case 'review_dismiss':
      if (details?.reason) {
        return String(details.reason);
      }
      return 'Dismissed from review queue';
    default:
      return '';
  }
}

export function AuditTrail({ canonicalEventId }: AuditTrailProps) {
  const { data, isLoading, isError } = useAuditLog(canonicalEventId);

  if (isLoading) {
    return <div className="text-sm text-gray-500">Loading audit trail...</div>;
  }

  if (isError) {
    return <div className="text-sm text-red-500">Error loading audit trail.</div>;
  }

  if (!data || data.items.length === 0) {
    return <div className="text-sm text-gray-500 italic">No audit history.</div>;
  }

  return (
    <div className="space-y-2">
      {data.items.map((entry) => (
        <div
          key={entry.id}
          className={`border-l-4 rounded-r px-4 py-3 ${actionColor(entry.action_type)}`}
        >
          <div className="flex items-center gap-2 flex-wrap">
            <span className={`text-xs px-2 py-0.5 rounded font-medium ${actionBadgeColor(entry.action_type)}`}>
              {formatActionType(entry.action_type)}
            </span>
            <span className="text-xs text-gray-600">by {entry.operator}</span>
            <span className="text-xs text-gray-400 ml-auto">{formatTimestamp(entry.created_at)}</span>
          </div>
          {detailsSummary(entry) && (
            <p className="text-sm text-gray-700 mt-1">{detailsSummary(entry)}</p>
          )}
        </div>
      ))}
    </div>
  );
}
