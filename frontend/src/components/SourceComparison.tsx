import { useState } from 'react';
import { format, parseISO } from 'date-fns';
import type { SourceEventDetail } from '../types';

interface SourceComparisonProps {
  sources: SourceEventDetail[];
}

function formatDate(dateStr: string): string {
  try {
    return format(parseISO(dateStr), 'dd.MM.yyyy');
  } catch {
    return dateStr;
  }
}

function SourceCard({ source, referenceTitle }: { source: SourceEventDetail; referenceTitle: string }) {
  const [expanded, setExpanded] = useState(false);
  const titleDiffers = source.title !== referenceTitle;
  const descriptionText = source.description ?? '';
  const showToggle = descriptionText.length > 200;

  return (
    <div
      className={`bg-white border rounded-lg p-4 ${titleDiffers ? 'border-l-4 border-l-amber-400' : ''}`}
    >
      {/* Header */}
      <div className="flex items-center gap-2 mb-2">
        <span className="inline-block bg-purple-100 text-purple-800 text-xs px-2 py-0.5 rounded font-medium">
          {source.source_type}
        </span>
        <span className="text-xs text-gray-500">{source.source_code}</span>
        <span className="text-xs font-mono text-gray-400 ml-auto" title={source.id}>
          {source.id.length > 16 ? '...' + source.id.slice(-12) : source.id}
        </span>
      </div>

      {/* Title */}
      <h4 className="font-medium text-sm text-gray-900 mb-2">{source.title}</h4>

      {/* Short description */}
      {source.short_description && (
        <p className="text-sm text-gray-600 mb-2">{source.short_description}</p>
      )}

      {/* Description */}
      {descriptionText && (
        <div className="mb-2">
          <p className="text-sm text-gray-600">
            {expanded || !showToggle
              ? descriptionText
              : descriptionText.slice(0, 200) + '...'}
          </p>
          {showToggle && (
            <button
              onClick={() => setExpanded(!expanded)}
              className="text-xs text-blue-600 hover:text-blue-800 mt-1"
            >
              {expanded ? 'Show less' : 'Show more'}
            </button>
          )}
        </div>
      )}

      {/* Location */}
      {(source.location_city || source.location_name || source.location_street) && (
        <div className="mb-2">
          <span className="text-xs font-medium text-gray-500 uppercase">Location</span>
          <div className="text-sm text-gray-700">
            {source.location_name && <div>{source.location_name}</div>}
            {source.location_street && (
              <div>
                {source.location_street}
                {source.location_street_no ? ' ' + source.location_street_no : ''}
              </div>
            )}
            {(source.location_zipcode || source.location_city) && (
              <div>
                {source.location_zipcode ? source.location_zipcode + ' ' : ''}
                {source.location_city}
                {source.location_district ? ` (${source.location_district})` : ''}
              </div>
            )}
          </div>
        </div>
      )}

      {/* Dates */}
      {source.dates.length > 0 && (
        <div className="mb-2">
          <span className="text-xs font-medium text-gray-500 uppercase">Dates</span>
          <div className="text-sm text-gray-700">
            {source.dates.map((d, i) => (
              <div key={i}>
                {formatDate(d.date)}
                {d.start_time ? ` ${d.start_time}` : ''}
                {d.end_time ? ` - ${d.end_time}` : ''}
              </div>
            ))}
          </div>
        </div>
      )}

      {/* Categories */}
      {source.categories && source.categories.length > 0 && (
        <div className="flex flex-wrap gap-1 mb-2">
          {source.categories.map((cat) => (
            <span
              key={cat}
              className="inline-block bg-blue-100 text-blue-800 text-xs px-2 py-0.5 rounded"
            >
              {cat}
            </span>
          ))}
        </div>
      )}

      {/* Boolean flags */}
      <div className="flex flex-wrap gap-1.5">
        {source.is_family_event && (
          <span className="inline-block bg-green-100 text-green-800 text-xs px-2 py-0.5 rounded">
            Family Event
          </span>
        )}
        {source.is_child_focused && (
          <span className="inline-block bg-green-100 text-green-800 text-xs px-2 py-0.5 rounded">
            Child-focused
          </span>
        )}
        {source.admission_free && (
          <span className="inline-block bg-green-100 text-green-800 text-xs px-2 py-0.5 rounded">
            Free Admission
          </span>
        )}
      </div>
    </div>
  );
}

export function SourceComparison({ sources }: SourceComparisonProps) {
  if (sources.length === 0) {
    return <div className="text-sm text-gray-500 italic py-4">No source events.</div>;
  }

  const referenceTitle = sources[0].title;

  return (
    <div className="grid grid-cols-1 lg:grid-cols-2 xl:grid-cols-3 gap-4">
      {sources.map((source) => (
        <SourceCard key={source.id} source={source} referenceTitle={referenceTitle} />
      ))}
    </div>
  );
}
