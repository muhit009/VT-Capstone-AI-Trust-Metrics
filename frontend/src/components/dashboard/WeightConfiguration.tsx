import { useState, useEffect } from 'react';
import { Scale, Save, RotateCcw, CheckCircle, AlertCircle, Loader2 } from 'lucide-react';
import { weightsService } from '../../services/api';

const STORAGE_KEY = 'groundcheck_weight_config';

const PRESETS: Record<string, { label: string; grounding: number; generation: number }> = {
  conservative: { label: 'Conservative', grounding: 0.80, generation: 0.20 },
  default:      { label: 'Default',      grounding: 0.70, generation: 0.30 },
  balanced:     { label: 'Balanced',     grounding: 0.50, generation: 0.50 },
};

const SAMPLE = { grounding: 0.85, generation: 0.72 };

function tierOf(score: number) {
  if (score >= 70) return { label: 'HIGH',   className: 'text-green-700  bg-green-50  border-green-200'  };
  if (score >= 40) return { label: 'MEDIUM', className: 'text-yellow-700 bg-yellow-50 border-yellow-200' };
  return               { label: 'LOW',    className: 'text-red-700    bg-red-50    border-red-200'    };
}

function loadLocalFallback(): { grounding: number; generation: number } {
  try {
    const raw = localStorage.getItem(STORAGE_KEY);
    if (raw) {
      const parsed = JSON.parse(raw);
      if (typeof parsed.grounding === 'number' && typeof parsed.generation === 'number') {
        return parsed;
      }
    }
  } catch {}
  return { grounding: 0.70, generation: 0.30 };
}

export default function WeightConfiguration() {
  const [weights, setWeights]       = useState(loadLocalFallback);
  const [status, setStatus]         = useState<'idle' | 'loading' | 'saving' | 'saved' | 'error'>('loading');
  const [errorMsg, setErrorMsg]     = useState<string | null>(null);
  const [isDefault, setIsDefault]   = useState(true);

  // Load weights from API on mount
  useEffect(() => {
    weightsService.get()
      .then((res) => {
        setWeights({ grounding: (res as any).weight_grounding, generation: (res as any).weight_generation });
        setIsDefault((res as any).is_default);
        setStatus('idle');
      })
      .catch(() => {
        // API unavailable — use localStorage fallback silently
        setStatus('idle');
      });
  }, []);

  const activePreset =
    Object.entries(PRESETS).find(([, p]) => Math.abs(p.grounding - weights.grounding) < 0.001)?.[0] ?? null;

  const setGrounding = (raw: number) => {
    const grounding   = Math.round(raw * 100) / 100;
    const generation  = Math.round((1 - grounding) * 100) / 100;
    setWeights({ grounding, generation });
    setStatus('idle');
    setErrorMsg(null);
  };

  const applyPreset = (key: string) => {
    const p = PRESETS[key];
    setWeights({ grounding: p.grounding, generation: p.generation });
    setStatus('idle');
    setErrorMsg(null);
  };

  const handleSave = async () => {
    setStatus('saving');
    setErrorMsg(null);
    try {
      const res = await weightsService.save(weights.grounding, weights.generation);
      setIsDefault((res as any).is_default);
      localStorage.setItem(STORAGE_KEY, JSON.stringify(weights));
      setStatus('saved');
      setTimeout(() => setStatus('idle'), 2500);
    } catch (err: unknown) {
      // Fall back to localStorage-only persistence
      localStorage.setItem(STORAGE_KEY, JSON.stringify(weights));
      const detail = (err as { response?: { data?: { detail?: string } } })?.response?.data?.detail;
      setErrorMsg(detail ?? 'Could not reach backend — saved to browser storage only.');
      setStatus('error');
    }
  };

  const handleReset = async () => {
    try {
      await weightsService.reset();
    } catch {
      // Ignore API errors on reset
    }
    setWeights({ grounding: 0.70, generation: 0.30 });
    setIsDefault(true);
    localStorage.removeItem(STORAGE_KEY);
    setStatus('idle');
    setErrorMsg(null);
  };

  const previewScore = Math.round(
    (weights.grounding * SAMPLE.grounding + weights.generation * SAMPLE.generation) * 100,
  );
  const tier = tierOf(previewScore);

  return (
    <section className="rounded-3xl border border-gray-200 bg-white p-6 shadow-sm">
      {/* Header */}
      <div className="flex items-start gap-3">
        <div className="mt-0.5 rounded-2xl bg-slate-100 p-2">
          <Scale className="h-5 w-5 text-slate-700" />
        </div>
        <div>
          <h3 className="text-lg font-semibold text-gray-900">Confidence signal weights</h3>
          <p className="mt-1 text-sm leading-6 text-gray-600">
            Adjust how much each signal contributes to the final confidence score.
            Weights are linked and always sum to 100%.{' '}
            {!isDefault && (
              <span className="font-medium text-primary-700">Custom weights are active.</span>
            )}
          </p>
        </div>
      </div>

      <div className="mt-6 grid gap-6">

        {/* Preset buttons */}
        <div className="grid gap-2">
          <label className="text-sm font-medium text-gray-900">Presets</label>
          <div className="flex flex-wrap gap-2">
            {Object.entries(PRESETS).map(([key, preset]) => (
              <button
                key={key}
                type="button"
                onClick={() => applyPreset(key)}
                className={[
                  'rounded-xl border px-4 py-2 text-sm font-medium transition',
                  activePreset === key
                    ? 'border-primary-300 bg-primary-50 text-primary-700'
                    : 'border-gray-200 bg-white text-gray-700 hover:bg-gray-50',
                ].join(' ')}
              >
                {preset.label}
              </button>
            ))}
          </div>
          <p className="text-xs leading-5 text-gray-500">
            Conservative prioritises document grounding. Balanced treats both signals equally.
          </p>
        </div>

        {/* Sliders */}
        <div className="grid gap-5">
          {/* Grounding */}
          <div className="grid gap-2">
            <div className="flex items-center justify-between">
              <label className="text-sm font-medium text-gray-900">Grounding score</label>
              <span className="text-sm font-semibold tabular-nums text-gray-900">
                {(weights.grounding * 100).toFixed(0)}%
              </span>
            </div>
            <input
              type="range"
              min={0.05}
              max={0.95}
              step={0.05}
              value={weights.grounding}
              onChange={(e) => setGrounding(Number(e.target.value))}
              className="h-2 w-full cursor-pointer accent-blue-600"
            />
            <p className="text-xs leading-5 text-gray-500">
              NLI-based signal — how well the answer is supported by retrieved documents.
            </p>
          </div>

          {/* Generation confidence */}
          <div className="grid gap-2">
            <div className="flex items-center justify-between">
              <label className="text-sm font-medium text-gray-900">Generation confidence</label>
              <span className="text-sm font-semibold tabular-nums text-gray-900">
                {(weights.generation * 100).toFixed(0)}%
              </span>
            </div>
            <input
              type="range"
              min={0.05}
              max={0.95}
              step={0.05}
              value={weights.generation}
              onChange={(e) => setGrounding(1 - Number(e.target.value))}
              className="h-2 w-full cursor-pointer accent-blue-600"
            />
            <p className="text-xs leading-5 text-gray-500">
              Token probability signal — the model's own certainty about its output.
            </p>
          </div>
        </div>

        {/* Weight distribution bar */}
        <div className="grid gap-1.5">
          <div className="flex justify-between text-xs font-medium text-gray-500">
            <span>Grounding</span>
            <span>Generation confidence</span>
          </div>
          <div className="flex h-3 overflow-hidden rounded-full bg-gray-100">
            <div
              className="bg-blue-600 transition-all duration-200"
              style={{ width: `${weights.grounding * 100}%` }}
            />
            <div
              className="bg-blue-200 transition-all duration-200"
              style={{ width: `${weights.generation * 100}%` }}
            />
          </div>
          <div className="flex justify-between text-xs text-gray-400">
            <span>{(weights.grounding * 100).toFixed(0)}%</span>
            <span className="font-medium text-gray-500">Sum: 100%</span>
            <span>{(weights.generation * 100).toFixed(0)}%</span>
          </div>
        </div>

        {/* Live preview */}
        <div className="rounded-2xl border border-gray-200 bg-gray-50 p-5">
          <div className="text-sm font-medium text-gray-900">Live preview</div>
          <p className="mt-1 text-xs leading-5 text-gray-500">
            Sample inputs: grounding = {SAMPLE.grounding}, generation = {SAMPLE.generation}
          </p>
          <div className="mt-4 flex items-center gap-4">
            <div className="text-4xl font-bold tabular-nums text-gray-900">{previewScore}</div>
            <div>
              <span className={['inline-flex items-center rounded-lg border px-2.5 py-1 text-xs font-semibold', tier.className].join(' ')}>
                {tier.label} confidence
              </span>
              <p className="mt-1.5 text-xs text-gray-500">
                {(weights.grounding * SAMPLE.grounding * 100).toFixed(0)} (grounding)
                &nbsp;+&nbsp;
                {(weights.generation * SAMPLE.generation * 100).toFixed(0)} (generation)
              </p>
            </div>
          </div>
        </div>

        {/* Error banner */}
        {status === 'error' && errorMsg && (
          <div className="flex items-start gap-2 rounded-2xl border border-red-200 bg-red-50 px-4 py-3">
            <AlertCircle className="mt-0.5 h-4 w-4 shrink-0 text-red-600" />
            <p className="text-sm text-red-700">{errorMsg}</p>
          </div>
        )}

        {/* Actions */}
        <div className="flex flex-wrap items-center gap-3">
          <button
            type="button"
            onClick={handleSave}
            disabled={status === 'saving' || status === 'loading'}
            className="inline-flex items-center gap-2 rounded-xl bg-primary-600 px-4 py-2.5 text-sm font-medium text-white hover:bg-primary-700 disabled:opacity-50 disabled:cursor-not-allowed"
          >
            {status === 'saving' ? (
              <Loader2 className="h-4 w-4 animate-spin" />
            ) : status === 'saved' ? (
              <CheckCircle className="h-4 w-4" />
            ) : (
              <Save className="h-4 w-4" />
            )}
            {status === 'saving' ? 'Saving…' : status === 'saved' ? 'Saved' : 'Save configuration'}
          </button>

          <button
            type="button"
            onClick={handleReset}
            disabled={status === 'saving' || status === 'loading'}
            className="inline-flex items-center gap-2 rounded-xl border border-gray-200 px-4 py-2.5 text-sm font-medium text-gray-700 hover:bg-gray-50 disabled:opacity-50 disabled:cursor-not-allowed"
          >
            <RotateCcw className="h-4 w-4" />
            Reset to default
          </button>

          {status === 'saved' && (
            <span className="text-sm text-gray-500">Saved — applied to all subsequent queries.</span>
          )}
        </div>

      </div>
    </section>
  );
}
