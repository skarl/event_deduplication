import { Link, useParams } from 'react-router-dom';
import { format, parseISO } from 'date-fns';
import { useCanonicalEventDetail } from '../hooks/useCanonicalEvents';
import { SourceComparison } from './SourceComparison';
import { ConfidenceIndicator } from './ConfidenceIndicator';

function formatDate(dateStr: string): string {
  try {
    return format(parseISO(dateStr), 'dd.MM.yyyy');
  } catch {
    return dateStr;
  }
}

function formatConfidence(confidence: number | null): string {
  if (confidence === null) return '-';
  return Math.round(confidence * 100) + '%';
}

function ProvenanceHint({ field, provenance }: { field: string; provenance: Record<string, string> | null }) {
  if (!provenance || !provenance[field]) return null;
  return (
    <span className="text-xs text-gray-400 ml-1" title={`Source: ${provenance[field]}`}>
      (from {provenance[field].length > 16 ? '...' + provenance[field].slice(-12) : provenance[field]})
    </span>
  );
}

export function EventDetail() {
  const { id } = useParams<{ id: string }>();
  const eventId = Number(id ?? '0');
  const { data: detail, isLoading, isError, error } = useCanonicalEventDetail(eventId);

  if (isLoading) {
    return <div className="text-center py-12 text-gray-500">Loading event details...</div>;
  }

  if (isError) {
    const is404 = error instanceof Error && error.message.includes('404');
    if (is404) {
      return (
        <div className="text-center py-12">
          <p className="text-gray-600 mb-4">Event not found.</p>
          <Link to="/" className="text-blue-600 hover:underline">Back to list</Link>
        </div>
      );
    }
    return (
      <div className="text-center py-12 text-red-600">
        Error loading event: {error instanceof Error ? error.message : 'Unknown error'}
      </div>
    );
  }

  if (!detail) {
    return null;
  }

  return (
    <div className="space-y-6">
      {/* Back link */}
      <Link to="/" className="text-sm text-blue-600 hover:underline">
        &larr; Back to list
      </Link>

      {/* Section 1: Header */}
      <div className="bg-white rounded-lg shadow-sm border p-6">
        <h2 className="text-2xl font-bold text-gray-900 mb-3">{detail.title}</h2>
        <div className="flex flex-wrap gap-2">
          <span className="inline-block bg-gray-100 text-gray-700 text-sm px-3 py-1 rounded">
            {detail.source_count} source{detail.source_count !== 1 ? 's' : ''}
          </span>
          <span
            className={`inline-block text-sm px-3 py-1 rounded ${
              detail.match_confidence !== null && detail.match_confidence >= 0.8
                ? 'bg-green-100 text-green-800'
                : detail.match_confidence !== null && detail.match_confidence >= 0.5
                  ? 'bg-yellow-100 text-yellow-800'
                  : 'bg-gray-100 text-gray-600'
            }`}
          >
            Confidence: {formatConfidence(detail.match_confidence)}
          </span>
          {detail.needs_review && (
            <span className="inline-block bg-yellow-100 text-yellow-800 text-sm px-3 py-1 rounded font-medium">
              Needs Review
            </span>
          )}
        </div>
      </div>

      {/* Section 2: Event Details */}
      <div className="bg-white rounded-lg shadow-sm border p-6">
        <h3 className="text-lg font-semibold text-gray-900 mb-4">Event Details</h3>
        <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
          {/* Left column: description, highlights */}
          <div className="space-y-4">
            {detail.short_description && (
              <div>
                <span className="text-xs font-medium text-gray-500 uppercase">Summary</span>
                <p className="text-sm text-gray-700 mt-1">{detail.short_description}</p>
                <ProvenanceHint field="short_description" provenance={detail.field_provenance} />
              </div>
            )}
            {detail.description && (
              <div>
                <span className="text-xs font-medium text-gray-500 uppercase">Description</span>
                <p className="text-sm text-gray-700 mt-1 whitespace-pre-line">{detail.description}</p>
                <ProvenanceHint field="description" provenance={detail.field_provenance} />
              </div>
            )}
            {detail.highlights && detail.highlights.length > 0 && (
              <div>
                <span className="text-xs font-medium text-gray-500 uppercase">Highlights</span>
                <ul className="list-disc list-inside mt-1 space-y-1">
                  {detail.highlights.map((h, i) => (
                    <li key={i} className="text-sm text-gray-700">{h}</li>
                  ))}
                </ul>
                <ProvenanceHint field="highlights" provenance={detail.field_provenance} />
              </div>
            )}
          </div>

          {/* Right column: location, dates, categories, flags */}
          <div className="space-y-4">
            {/* Location */}
            {(detail.location_name || detail.location_city || detail.location_street) && (
              <div>
                <span className="text-xs font-medium text-gray-500 uppercase">Location</span>
                <div className="text-sm text-gray-700 mt-1">
                  {detail.location_name && (
                    <div>
                      {detail.location_name}
                      <ProvenanceHint field="location_name" provenance={detail.field_provenance} />
                    </div>
                  )}
                  {detail.location_street && (
                    <div>{detail.location_street}</div>
                  )}
                  {(detail.location_zipcode || detail.location_city) && (
                    <div>
                      {detail.location_zipcode ? detail.location_zipcode + ' ' : ''}
                      {detail.location_city}
                      {detail.location_district ? ` (${detail.location_district})` : ''}
                    </div>
                  )}
                </div>
              </div>
            )}

            {/* Geo coordinates */}
            {detail.geo_latitude !== null && detail.geo_longitude !== null && (
              <div>
                <span className="text-xs font-medium text-gray-500 uppercase">Coordinates</span>
                <div className="text-sm text-gray-700 mt-1">
                  {detail.geo_latitude.toFixed(4)}, {detail.geo_longitude.toFixed(4)}
                  {detail.geo_confidence !== null && (
                    <span className="text-xs text-gray-400 ml-1">
                      (confidence: {Math.round(detail.geo_confidence * 100)}%)
                    </span>
                  )}
                </div>
              </div>
            )}

            {/* Dates */}
            {detail.dates && detail.dates.length > 0 && (
              <div>
                <span className="text-xs font-medium text-gray-500 uppercase">Dates</span>
                <div className="text-sm text-gray-700 mt-1 space-y-0.5">
                  {detail.dates.map((d, i) => (
                    <div key={i}>
                      {formatDate(d.date)}
                      {d.start_time ? ` ${d.start_time}` : ''}
                      {d.end_time ? ` - ${d.end_time}` : ''}
                      {d.end_date && d.end_date !== d.date ? ` to ${formatDate(d.end_date)}` : ''}
                    </div>
                  ))}
                </div>
                <ProvenanceHint field="dates" provenance={detail.field_provenance} />
              </div>
            )}

            {/* Categories */}
            {detail.categories && detail.categories.length > 0 && (
              <div>
                <span className="text-xs font-medium text-gray-500 uppercase">Categories</span>
                <div className="flex flex-wrap gap-1 mt-1">
                  {detail.categories.map((cat) => (
                    <span
                      key={cat}
                      className="inline-block bg-blue-100 text-blue-800 text-xs px-2 py-0.5 rounded"
                    >
                      {cat}
                    </span>
                  ))}
                </div>
                <ProvenanceHint field="categories" provenance={detail.field_provenance} />
              </div>
            )}

            {/* Boolean flags */}
            <div>
              <span className="text-xs font-medium text-gray-500 uppercase">Flags</span>
              <div className="flex flex-wrap gap-1.5 mt-1">
                {detail.is_family_event && (
                  <span className="inline-block bg-green-100 text-green-800 text-xs px-2 py-0.5 rounded">
                    Family Event
                  </span>
                )}
                {detail.is_child_focused && (
                  <span className="inline-block bg-green-100 text-green-800 text-xs px-2 py-0.5 rounded">
                    Child-focused
                  </span>
                )}
                {detail.admission_free && (
                  <span className="inline-block bg-green-100 text-green-800 text-xs px-2 py-0.5 rounded">
                    Free Admission
                  </span>
                )}
                {!detail.is_family_event && !detail.is_child_focused && !detail.admission_free && (
                  <span className="text-sm text-gray-400">None set</span>
                )}
              </div>
            </div>
          </div>
        </div>
      </div>

      {/* Section 3: Source Events */}
      <div className="bg-white rounded-lg shadow-sm border p-6">
        <h3 className="text-lg font-semibold text-gray-900 mb-4">
          Source Events ({detail.sources.length})
        </h3>
        <SourceComparison sources={detail.sources} />
      </div>

      {/* Section 4: Match Confidence */}
      <div className="bg-white rounded-lg shadow-sm border p-6">
        <h3 className="text-lg font-semibold text-gray-900 mb-4">Match Scores</h3>
        <ConfidenceIndicator
          decisions={detail.match_decisions}
          sourceIds={detail.sources.map((s) => s.id)}
        />
      </div>
    </div>
  );
}
