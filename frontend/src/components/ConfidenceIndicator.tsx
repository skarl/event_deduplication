import type { MatchDecision } from '../types';

interface ConfidenceIndicatorProps {
  decisions: MatchDecision[];
  sourceIds: string[];
}

function scoreColor(score: number): string {
  if (score >= 0.8) return 'bg-green-500';
  if (score >= 0.5) return 'bg-yellow-500';
  return 'bg-red-500';
}

function truncateId(id: string): string {
  return id.length > 12 ? '...' + id.slice(-8) : id;
}

interface ScoreBarProps {
  label: string;
  score: number;
}

function ScoreBar({ label, score }: ScoreBarProps) {
  return (
    <div className="flex items-center gap-2">
      <span className="text-xs text-gray-500 w-24 text-right shrink-0">{label}</span>
      <div className="flex-1 bg-gray-200 rounded h-4 overflow-hidden">
        <div
          className={`${scoreColor(score)} rounded h-4 transition-all`}
          style={{ width: `${Math.round(score * 100)}%` }}
        />
      </div>
      <span className="text-xs text-gray-700 w-10 shrink-0">{Math.round(score * 100)}%</span>
    </div>
  );
}

function TierBadge({ tier }: { tier: string }) {
  const styles: Record<string, string> = {
    ai: 'bg-purple-100 text-purple-800',
    ai_low_confidence: 'bg-orange-100 text-orange-800',
    ai_unexpected: 'bg-red-100 text-red-800',
    deterministic: 'bg-gray-100 text-gray-600',
  };
  const labels: Record<string, string> = {
    ai: 'AI',
    ai_low_confidence: 'AI (low confidence)',
    ai_unexpected: 'AI (unexpected)',
    deterministic: 'Deterministic',
  };
  return (
    <span
      className={`text-xs px-2 py-0.5 rounded font-medium ${styles[tier] || styles.deterministic}`}
    >
      {labels[tier] || tier}
    </span>
  );
}

export function ConfidenceIndicator({ decisions, sourceIds }: ConfidenceIndicatorProps) {
  if (decisions.length === 0) {
    return (
      <div className="text-sm text-gray-500 italic py-4">
        {sourceIds.length <= 1
          ? 'Single source -- no match scores'
          : 'No match decisions recorded'}
      </div>
    );
  }

  return (
    <div className="space-y-6">
      {decisions.map((d) => (
        <div key={d.id} className="bg-white border rounded-lg p-4">
          <div className="flex items-center gap-2 mb-3">
            <span className="text-xs font-mono bg-gray-100 px-2 py-0.5 rounded">
              {truncateId(d.source_event_id_a)}
            </span>
            <span className="text-xs text-gray-400">vs</span>
            <span className="text-xs font-mono bg-gray-100 px-2 py-0.5 rounded">
              {truncateId(d.source_event_id_b)}
            </span>
            <span className="ml-auto flex items-center gap-1.5">
              <span className="text-xs text-gray-500">{d.decision}</span>
              <TierBadge tier={d.tier} />
            </span>
          </div>
          <div className="space-y-1.5">
            <ScoreBar label="Title" score={d.title_score} />
            <ScoreBar label="Date" score={d.date_score} />
            <ScoreBar label="Geo" score={d.geo_score} />
            <ScoreBar label="Description" score={d.description_score} />
            <div className="pt-1 border-t mt-2">
              <ScoreBar label="Combined" score={d.combined_score} />
            </div>
          </div>
        </div>
      ))}
    </div>
  );
}
