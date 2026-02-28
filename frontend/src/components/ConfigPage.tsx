import { useState, useEffect, useMemo, useCallback } from 'react';
import { useConfig, useUpdateConfig } from '../hooks/useConfig';
import type {
  ConfigResponse,
  ConfigUpdateRequest,
  ScoringWeights,
  ThresholdConfig,
  DateConfig,
  GeoConfig,
  TitleConfig,
  ClusterConfig,
  AIConfigResponse,
} from '../types';

// --- Toast notification ---

function Toast({ message, onDismiss }: { message: string; onDismiss: () => void }) {
  useEffect(() => {
    const timer = setTimeout(onDismiss, 3000);
    return () => clearTimeout(timer);
  }, [onDismiss]);

  return (
    <div className="fixed top-4 right-4 z-50 bg-green-600 text-white px-4 py-3 rounded-lg shadow-lg text-sm font-medium">
      {message}
    </div>
  );
}

// --- Section wrapper ---

function Section({
  title,
  children,
  onSave,
  saving,
  error,
}: {
  title: string;
  children: React.ReactNode;
  onSave?: () => void;
  saving?: boolean;
  error?: string | null;
}) {
  return (
    <details open className="bg-white rounded-lg shadow-sm border p-6">
      <summary className="text-lg font-semibold text-gray-900 cursor-pointer select-none">
        {title}
      </summary>
      <div className="mt-4 space-y-4">
        {children}
        {error && (
          <div className="text-sm text-red-600 bg-red-50 border border-red-200 rounded px-3 py-2">
            {error}
          </div>
        )}
        {onSave && (
          <div className="pt-2">
            <button
              onClick={onSave}
              disabled={saving}
              className="px-4 py-2 bg-blue-600 text-white text-sm font-medium rounded hover:bg-blue-700 disabled:opacity-50 disabled:cursor-not-allowed"
            >
              {saving ? 'Saving...' : 'Save'}
            </button>
          </div>
        )}
      </div>
    </details>
  );
}

// --- Input helpers ---

function NumberField({
  label,
  value,
  onChange,
  step = '0.05',
  min = '0',
  max,
  note,
}: {
  label: string;
  value: number;
  onChange: (v: number) => void;
  step?: string;
  min?: string;
  max?: string;
  note?: string;
}) {
  return (
    <div>
      <label className="block text-sm font-medium text-gray-700 mb-1">{label}</label>
      <input
        type="number"
        value={value}
        onChange={(e) => onChange(parseFloat(e.target.value) || 0)}
        step={step}
        min={min}
        max={max}
        className="border rounded px-3 py-2 w-full max-w-xs text-sm"
      />
      {note && <p className="text-xs text-gray-500 mt-1">{note}</p>}
    </div>
  );
}

// --- Section components ---

function ScoringWeightsSection({
  data,
  onSave,
  saving,
  error,
}: {
  data: ScoringWeights;
  onSave: (updates: ConfigUpdateRequest) => void;
  saving: boolean;
  error: string | null;
}) {
  const [weights, setWeights] = useState(data);
  useEffect(() => setWeights(data), [data]);

  const sum = useMemo(
    () => +(weights.date + weights.geo + weights.title + weights.description).toFixed(4),
    [weights],
  );

  const update = (field: keyof ScoringWeights, value: number) => {
    setWeights((prev) => ({ ...prev, [field]: value }));
  };

  return (
    <Section
      title="Scoring Weights"
      onSave={() => onSave({ scoring: weights })}
      saving={saving}
      error={error}
    >
      <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
        <NumberField label="Date" value={weights.date} onChange={(v) => update('date', v)} max="1.0" />
        <NumberField label="Geo" value={weights.geo} onChange={(v) => update('geo', v)} max="1.0" />
        <NumberField label="Title" value={weights.title} onChange={(v) => update('title', v)} max="1.0" />
        <NumberField label="Description" value={weights.description} onChange={(v) => update('description', v)} max="1.0" />
      </div>
      <div className={`text-sm font-medium mt-2 ${sum !== 1 ? 'text-yellow-700' : 'text-green-700'}`}>
        Sum: {sum.toFixed(2)}
        {sum !== 1 && (
          <span className="ml-2 bg-yellow-100 text-yellow-800 px-2 py-0.5 rounded text-xs">
            Weights sum to {sum.toFixed(2)} (should be 1.0)
          </span>
        )}
      </div>
    </Section>
  );
}

function ThresholdsSection({
  data,
  onSave,
  saving,
  error,
}: {
  data: ThresholdConfig;
  onSave: (updates: ConfigUpdateRequest) => void;
  saving: boolean;
  error: string | null;
}) {
  const [thresholds, setThresholds] = useState(data);
  useEffect(() => setThresholds(data), [data]);

  return (
    <Section
      title="Thresholds"
      onSave={() => onSave({ thresholds })}
      saving={saving}
      error={error}
    >
      <p className="text-xs text-gray-500 italic">
        High = auto-match, Low = auto-reject, Between = ambiguous
      </p>
      <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
        <NumberField
          label="High threshold"
          value={thresholds.high}
          onChange={(v) => setThresholds((p) => ({ ...p, high: v }))}
          max="1.0"
        />
        <NumberField
          label="Low threshold"
          value={thresholds.low}
          onChange={(v) => setThresholds((p) => ({ ...p, low: v }))}
          max="1.0"
        />
      </div>
    </Section>
  );
}

function DateTimeSection({
  data,
  onSave,
  saving,
  error,
}: {
  data: DateConfig;
  onSave: (updates: ConfigUpdateRequest) => void;
  saving: boolean;
  error: string | null;
}) {
  const [dateConfig, setDateConfig] = useState(data);
  useEffect(() => setDateConfig(data), [data]);

  return (
    <Section
      title="Date / Time"
      onSave={() => onSave({ date: dateConfig })}
      saving={saving}
      error={error}
    >
      <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
        <NumberField
          label="Exact match tolerance (minutes)"
          value={dateConfig.time_tolerance_minutes}
          onChange={(v) => setDateConfig((p) => ({ ...p, time_tolerance_minutes: v }))}
          step="1"
        />
        <NumberField
          label="Close match window (minutes)"
          value={dateConfig.time_close_minutes}
          onChange={(v) => setDateConfig((p) => ({ ...p, time_close_minutes: v }))}
          step="1"
        />
        <NumberField
          label="Close time factor"
          value={dateConfig.close_factor}
          onChange={(v) => setDateConfig((p) => ({ ...p, close_factor: v }))}
          max="1.0"
        />
        <NumberField
          label="Far time factor"
          value={dateConfig.far_factor}
          onChange={(v) => setDateConfig((p) => ({ ...p, far_factor: v }))}
          max="1.0"
        />
      </div>
    </Section>
  );
}

function GeoSection({
  data,
  onSave,
  saving,
  error,
}: {
  data: GeoConfig;
  onSave: (updates: ConfigUpdateRequest) => void;
  saving: boolean;
  error: string | null;
}) {
  const [geo, setGeo] = useState(data);
  useEffect(() => setGeo(data), [data]);

  return (
    <Section
      title="Geographic"
      onSave={() => onSave({ geo })}
      saving={saving}
      error={error}
    >
      <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-4">
        <NumberField
          label="Max distance (km)"
          value={geo.max_distance_km}
          onChange={(v) => setGeo((p) => ({ ...p, max_distance_km: v }))}
          step="0.5"
        />
        <NumberField
          label="Min geo confidence"
          value={geo.min_confidence}
          onChange={(v) => setGeo((p) => ({ ...p, min_confidence: v }))}
          max="1.0"
        />
        <NumberField
          label="Neutral score (when no geo data)"
          value={geo.neutral_score}
          onChange={(v) => setGeo((p) => ({ ...p, neutral_score: v }))}
          max="1.0"
        />
      </div>
    </Section>
  );
}

function TitleMatchingSection({
  data,
  onSave,
  saving,
  error,
}: {
  data: TitleConfig;
  onSave: (updates: ConfigUpdateRequest) => void;
  saving: boolean;
  error: string | null;
}) {
  const [title, setTitle] = useState(data);
  useEffect(() => setTitle(data), [data]);

  return (
    <Section
      title="Title Matching"
      onSave={() => onSave({ title: { primary_weight: title.primary_weight, secondary_weight: title.secondary_weight, blend_lower: title.blend_lower, blend_upper: title.blend_upper } })}
      saving={saving}
      error={error}
    >
      <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
        <NumberField
          label="Primary weight"
          value={title.primary_weight}
          onChange={(v) => setTitle((p) => ({ ...p, primary_weight: v }))}
        />
        <NumberField
          label="Secondary weight"
          value={title.secondary_weight}
          onChange={(v) => setTitle((p) => ({ ...p, secondary_weight: v }))}
        />
        <NumberField
          label="Blend lower"
          value={title.blend_lower}
          onChange={(v) => setTitle((p) => ({ ...p, blend_lower: v }))}
        />
        <NumberField
          label="Blend upper"
          value={title.blend_upper}
          onChange={(v) => setTitle((p) => ({ ...p, blend_upper: v }))}
        />
      </div>
      {data.cross_source_type && (
        <div className="mt-4 p-4 bg-gray-50 rounded border">
          <h4 className="text-sm font-medium text-gray-700 mb-2">Cross-source-type overrides (read-only)</h4>
          <div className="grid grid-cols-2 sm:grid-cols-4 gap-3 text-sm text-gray-600">
            <div>Primary: {data.cross_source_type.primary_weight}</div>
            <div>Secondary: {data.cross_source_type.secondary_weight}</div>
            <div>Blend lower: {data.cross_source_type.blend_lower}</div>
            <div>Blend upper: {data.cross_source_type.blend_upper}</div>
          </div>
        </div>
      )}
    </Section>
  );
}

function AIMatchingSection({
  data,
  hasApiKey,
  onSave,
  saving,
  error,
}: {
  data: AIConfigResponse;
  hasApiKey: boolean;
  onSave: (updates: ConfigUpdateRequest) => void;
  saving: boolean;
  error: string | null;
}) {
  const [ai, setAi] = useState(data);
  const [apiKey, setApiKey] = useState('');
  const [clearingKey, setClearingKey] = useState(false);
  useEffect(() => { setAi(data); setApiKey(''); setClearingKey(false); }, [data]);

  const handleSave = () => {
    const updates: ConfigUpdateRequest = {
      ai: {
        enabled: ai.enabled,
        model: ai.model,
        temperature: ai.temperature,
        max_output_tokens: ai.max_output_tokens,
        max_concurrent_requests: ai.max_concurrent_requests,
        confidence_threshold: ai.confidence_threshold,
        min_combined_score: ai.min_combined_score,
        max_combined_score: ai.max_combined_score,
        cache_enabled: ai.cache_enabled,
        cost_per_1m_input_tokens: ai.cost_per_1m_input_tokens,
        cost_per_1m_output_tokens: ai.cost_per_1m_output_tokens,
      },
    };
    if (clearingKey) {
      updates.ai_api_key = '';
    } else if (apiKey) {
      updates.ai_api_key = apiKey;
    }
    onSave(updates);
  };

  const handleClearKey = () => {
    setClearingKey(true);
    setApiKey('');
  };

  return (
    <Section title="AI Matching" onSave={handleSave} saving={saving} error={error}>
      {/* Toggle */}
      <div className="flex items-center gap-3">
        <button
          type="button"
          role="switch"
          aria-checked={ai.enabled}
          onClick={() => setAi((p) => ({ ...p, enabled: !p.enabled }))}
          className={`relative inline-flex h-6 w-11 items-center rounded-full transition-colors ${ai.enabled ? 'bg-blue-600' : 'bg-gray-300'}`}
        >
          <span
            className={`inline-block h-4 w-4 rounded-full bg-white transition-transform ${ai.enabled ? 'translate-x-6' : 'translate-x-1'}`}
          />
        </button>
        <span className="text-sm font-medium text-gray-700">
          AI matching {ai.enabled ? 'enabled' : 'disabled'}
        </span>
      </div>

      {/* API Key */}
      <div>
        <label className="block text-sm font-medium text-gray-700 mb-1">Gemini API Key</label>
        <div className="flex gap-2 items-center">
          <input
            type="password"
            value={apiKey}
            onChange={(e) => { setApiKey(e.target.value); setClearingKey(false); }}
            placeholder={
              clearingKey
                ? 'Key will be cleared on save'
                : hasApiKey
                  ? 'Key is set (enter new value to change)'
                  : 'Enter API key'
            }
            className="border rounded px-3 py-2 w-full max-w-sm text-sm"
          />
          {(hasApiKey || apiKey) && !clearingKey && (
            <button
              onClick={handleClearKey}
              className="px-3 py-2 text-sm text-red-600 border border-red-300 rounded hover:bg-red-50"
            >
              Clear Key
            </button>
          )}
          {clearingKey && (
            <span className="text-xs text-red-600 italic">Will be cleared on save</span>
          )}
        </div>
        {hasApiKey && !clearingKey && !apiKey && (
          <p className="text-xs text-green-600 mt-1">API key is configured</p>
        )}
      </div>

      {/* AI Settings */}
      <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-4">
        <div>
          <label className="block text-sm font-medium text-gray-700 mb-1">Model</label>
          <input
            type="text"
            value={ai.model}
            onChange={(e) => setAi((p) => ({ ...p, model: e.target.value }))}
            className="border rounded px-3 py-2 w-full text-sm"
          />
        </div>
        <NumberField
          label="Temperature"
          value={ai.temperature}
          onChange={(v) => setAi((p) => ({ ...p, temperature: v }))}
          min="0"
          max="2.0"
        />
        <NumberField
          label="Max output tokens"
          value={ai.max_output_tokens}
          onChange={(v) => setAi((p) => ({ ...p, max_output_tokens: v }))}
          step="100"
          min="100"
        />
        <NumberField
          label="Max concurrent requests"
          value={ai.max_concurrent_requests}
          onChange={(v) => setAi((p) => ({ ...p, max_concurrent_requests: v }))}
          step="1"
          min="1"
        />
        <NumberField
          label="Confidence threshold"
          value={ai.confidence_threshold}
          onChange={(v) => setAi((p) => ({ ...p, confidence_threshold: v }))}
          max="1.0"
        />
        <NumberField
          label="Min combined score (AI)"
          value={ai.min_combined_score}
          onChange={(v) => setAi((p) => ({ ...p, min_combined_score: v }))}
          max="1.0"
        />
        <NumberField
          label="Max combined score (AI)"
          value={ai.max_combined_score}
          onChange={(v) => setAi((p) => ({ ...p, max_combined_score: v }))}
          max="1.0"
        />
        <div className="flex items-center gap-2 pt-6">
          <input
            type="checkbox"
            id="cache_enabled"
            checked={ai.cache_enabled}
            onChange={(e) => setAi((p) => ({ ...p, cache_enabled: e.target.checked }))}
            className="h-4 w-4 rounded border-gray-300 text-blue-600"
          />
          <label htmlFor="cache_enabled" className="text-sm font-medium text-gray-700">
            Cache enabled
          </label>
        </div>
      </div>

      {/* Cost fields */}
      <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
        <NumberField
          label="Cost per 1M input tokens ($)"
          value={ai.cost_per_1m_input_tokens}
          onChange={(v) => setAi((p) => ({ ...p, cost_per_1m_input_tokens: v }))}
          step="0.01"
        />
        <NumberField
          label="Cost per 1M output tokens ($)"
          value={ai.cost_per_1m_output_tokens}
          onChange={(v) => setAi((p) => ({ ...p, cost_per_1m_output_tokens: v }))}
          step="0.01"
        />
      </div>
    </Section>
  );
}

function ClusteringSection({
  data,
  onSave,
  saving,
  error,
}: {
  data: ClusterConfig;
  onSave: (updates: ConfigUpdateRequest) => void;
  saving: boolean;
  error: string | null;
}) {
  const [cluster, setCluster] = useState(data);
  useEffect(() => setCluster(data), [data]);

  return (
    <Section
      title="Clustering"
      onSave={() => onSave({ cluster })}
      saving={saving}
      error={error}
    >
      <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
        <NumberField
          label="Max cluster size"
          value={cluster.max_cluster_size}
          onChange={(v) => setCluster((p) => ({ ...p, max_cluster_size: v }))}
          step="1"
          min="2"
        />
        <NumberField
          label="Min internal similarity"
          value={cluster.min_internal_similarity}
          onChange={(v) => setCluster((p) => ({ ...p, min_internal_similarity: v }))}
          max="1.0"
        />
      </div>
    </Section>
  );
}

// --- Read-only advanced sections ---

function AdvancedSections({ config }: { config: ConfigResponse }) {
  return (
    <>
      <details className="bg-white rounded-lg shadow-sm border p-6">
        <summary className="text-lg font-semibold text-gray-900 cursor-pointer select-none">
          Category Weights (read-only)
        </summary>
        <div className="mt-4 space-y-3">
          <div>
            <h4 className="text-sm font-medium text-gray-700 mb-1">Priority order</h4>
            <p className="text-sm text-gray-600">
              {config.category_weights.priority.length > 0
                ? config.category_weights.priority.join(', ')
                : 'No priority categories configured'}
            </p>
          </div>
          {Object.keys(config.category_weights.overrides).length > 0 && (
            <div>
              <h4 className="text-sm font-medium text-gray-700 mb-1">Weight overrides</h4>
              <div className="overflow-x-auto">
                <table className="text-sm text-gray-600 border-collapse">
                  <thead>
                    <tr className="border-b">
                      <th className="text-left pr-4 py-1 font-medium">Category</th>
                      <th className="text-right px-2 py-1 font-medium">Date</th>
                      <th className="text-right px-2 py-1 font-medium">Geo</th>
                      <th className="text-right px-2 py-1 font-medium">Title</th>
                      <th className="text-right px-2 py-1 font-medium">Desc</th>
                    </tr>
                  </thead>
                  <tbody>
                    {Object.entries(config.category_weights.overrides).map(([cat, w]) => (
                      <tr key={cat} className="border-b">
                        <td className="pr-4 py-1">{cat}</td>
                        <td className="text-right px-2 py-1">{w.date}</td>
                        <td className="text-right px-2 py-1">{w.geo}</td>
                        <td className="text-right px-2 py-1">{w.title}</td>
                        <td className="text-right px-2 py-1">{w.description}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            </div>
          )}
          {Object.keys(config.category_weights.overrides).length === 0 && (
            <p className="text-sm text-gray-500 italic">No weight overrides configured.</p>
          )}
        </div>
      </details>

      <details className="bg-white rounded-lg shadow-sm border p-6">
        <summary className="text-lg font-semibold text-gray-900 cursor-pointer select-none">
          Field Strategies (read-only)
        </summary>
        <div className="mt-4 overflow-x-auto">
          <table className="text-sm text-gray-600 border-collapse w-full">
            <thead>
              <tr className="border-b">
                <th className="text-left pr-4 py-1 font-medium">Field</th>
                <th className="text-left px-2 py-1 font-medium">Strategy</th>
              </tr>
            </thead>
            <tbody>
              {Object.entries(config.canonical.field_strategies).map(([field, strategy]) => (
                <tr key={field} className="border-b">
                  <td className="pr-4 py-1 font-mono text-xs">{field}</td>
                  <td className="px-2 py-1">{strategy}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </details>
    </>
  );
}

// --- Main ConfigPage ---

export function ConfigPage() {
  const { data: config, isLoading, isError, error: queryError } = useConfig();
  const mutation = useUpdateConfig();

  const [toast, setToast] = useState<string | null>(null);
  const [sectionError, setSectionError] = useState<string | null>(null);

  const handleSave = useCallback(
    (updates: ConfigUpdateRequest) => {
      setSectionError(null);
      mutation.mutate(updates, {
        onSuccess: () => setToast('Configuration saved successfully'),
        onError: (err) => setSectionError(err instanceof Error ? err.message : 'Save failed'),
      });
    },
    [mutation],
  );

  const dismissToast = useCallback(() => setToast(null), []);

  if (isLoading) {
    return <div className="text-center py-12 text-gray-500">Loading configuration...</div>;
  }

  if (isError) {
    return (
      <div className="text-center py-12 text-red-600">
        Error loading configuration: {queryError instanceof Error ? queryError.message : 'Unknown error'}
      </div>
    );
  }

  if (!config) return null;

  return (
    <div>
      {toast && <Toast message={toast} onDismiss={dismissToast} />}

      {/* Header */}
      <div className="flex items-center justify-between mb-6">
        <h2 className="text-2xl font-bold text-gray-900">Configuration</h2>
        {config.updated_at && (
          <span className="text-xs text-gray-500">
            Last updated: {new Date(config.updated_at).toLocaleString()}
          </span>
        )}
      </div>

      {/* Sections */}
      <div className="space-y-4">
        <ScoringWeightsSection
          data={config.scoring}
          onSave={handleSave}
          saving={mutation.isPending}
          error={sectionError}
        />

        <ThresholdsSection
          data={config.thresholds}
          onSave={handleSave}
          saving={mutation.isPending}
          error={sectionError}
        />

        <DateTimeSection
          data={config.date}
          onSave={handleSave}
          saving={mutation.isPending}
          error={sectionError}
        />

        <GeoSection
          data={config.geo}
          onSave={handleSave}
          saving={mutation.isPending}
          error={sectionError}
        />

        <TitleMatchingSection
          data={config.title}
          onSave={handleSave}
          saving={mutation.isPending}
          error={sectionError}
        />

        <AIMatchingSection
          data={config.ai}
          hasApiKey={config.has_api_key}
          onSave={handleSave}
          saving={mutation.isPending}
          error={sectionError}
        />

        <ClusteringSection
          data={config.cluster}
          onSave={handleSave}
          saving={mutation.isPending}
          error={sectionError}
        />

        <AdvancedSections config={config} />
      </div>
    </div>
  );
}
