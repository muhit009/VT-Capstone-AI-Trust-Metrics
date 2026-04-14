import { useMemo, useState } from 'react';
import {
  User,
  Brain,
  LayoutPanelLeft,
  Database,
  ShieldCheck,
  Save,
  RotateCcw,
  Trash2,
  Info,
} from 'lucide-react';

const defaultSettings = {
  user: {
    displayName: 'Boeing New Hire',
    onboardingTrack: 'General Engineering',
    teamOrg: '',
    experienceLevel: 'New hire',
    aircraftFocus: ['737', '787'],
    units: 'Imperial',
    explanationStyle: 'Balanced',
  },
  assistant: {
    modelProfile: 'default',
    backendTarget: 'default_backend',
    arcModelProfile: 'arc_llama3_8b',
    strictGroundedMode: true,
    allowDraftAnswers: true,
    retrievalDepth: 5,
    responseLength: 350,
    temperature: 0.2,
    topP: 0.9,
    repetitionPenalty: 1.05,
    confidenceVerbosity: 'Technical',
  },
  display: {
    showEvidenceByDefault: true,
    showRawSignalMetrics: true,
    showLatencyMetadata: true,
    expandRightPanelSectionsByDefault: true,
    showInlineCitations: true,
    showRequestMetadata: true,
  },
  data: {
    saveConversationHistory: true,
    persistUserPreferences: true,
    clearDraftOnNewChat: true,
  },
};

function SectionCard({ icon: Icon, title, description, children }) {
  return (
    <section className="rounded-3xl border border-gray-200 bg-white p-6 shadow-sm">
      <div className="flex items-start gap-3">
        <div className="mt-0.5 rounded-2xl bg-slate-100 p-2">
          <Icon className="h-5 w-5 text-slate-700" />
        </div>
        <div>
          <h3 className="text-lg font-semibold text-gray-900">{title}</h3>
          <p className="mt-1 text-sm leading-6 text-gray-600">{description}</p>
        </div>
      </div>

      <div className="mt-6 grid gap-5">{children}</div>
    </section>
  );
}

function Field({ label, hint, children }) {
  return (
    <div className="grid gap-2">
      <label className="text-sm font-medium text-gray-900">{label}</label>
      {children}
      {hint ? <p className="text-xs leading-5 text-gray-500">{hint}</p> : null}
    </div>
  );
}

function Toggle({ checked, onChange, label, hint }) {
  return (
    <label className="flex items-start justify-between gap-4 rounded-2xl border border-gray-200 bg-gray-50 px-4 py-4">
      <div className="min-w-0">
        <div className="text-sm font-medium text-gray-900">{label}</div>
        {hint ? <div className="mt-1 text-xs leading-5 text-gray-500">{hint}</div> : null}
      </div>

      <button
        type="button"
        onClick={() => onChange(!checked)}
        className={[
          'relative mt-0.5 h-6 w-11 shrink-0 rounded-full transition',
          checked ? 'bg-primary-600' : 'bg-gray-300',
        ].join(' ')}
        aria-pressed={checked}
      >
        <span
          className={[
            'absolute top-0.5 h-5 w-5 rounded-full bg-white shadow transition',
            checked ? 'left-[22px]' : 'left-0.5',
          ].join(' ')}
        />
      </button>
    </label>
  );
}

function Input(props) {
  return (
    <input
      {...props}
      className={[
        'w-full rounded-xl border border-gray-200 bg-white px-3 py-2.5 text-sm text-gray-900 outline-none ring-0 placeholder:text-gray-400',
        props.className || '',
      ].join(' ')}
    />
  );
}

function Select(props) {
  return (
    <select
      {...props}
      className={[
        'w-full rounded-xl border border-gray-200 bg-white px-3 py-2.5 text-sm text-gray-900 outline-none ring-0',
        props.className || '',
      ].join(' ')}
    />
  );
}

function NumberInput(props) {
  return (
    <input
      {...props}
      type="number"
      className={[
        'w-full rounded-xl border border-gray-200 bg-white px-3 py-2.5 text-sm text-gray-900 outline-none ring-0',
        props.className || '',
      ].join(' ')}
    />
  );
}

export default function SettingsPanel() {
  const [settings, setSettings] = useState(defaultSettings);
  const [saveNotice, setSaveNotice] = useState('');

  const updateSection = (section, field, value) => {
    setSettings((current) => ({
      ...current,
      [section]: {
        ...current[section],
        [field]: value,
      },
    }));
    setSaveNotice('');
  };

  const handleAircraftFocusChange = (value) => {
    const list = value
      .split(',')
      .map((item) => item.trim())
      .filter(Boolean);

    setSettings((current) => ({
      ...current,
      user: {
        ...current.user,
        aircraftFocus: list,
      },
    }));
    setSaveNotice('');
  };

  const handleResetDefaults = () => {
    setSettings(defaultSettings);
    setSaveNotice('Settings reset to defaults.');
  };

  const handleSave = () => {
    // Placeholder for future backend persistence.
    // Later this can POST to a /settings endpoint or save locally.
    setSaveNotice('Settings saved locally in UI state. Backend persistence can be added next.');
  };

  const settingsSummary = useMemo(() => {
    return {
      modelSummary: `${settings.assistant.modelProfile} · top_k ${settings.assistant.retrievalDepth} · ${settings.assistant.responseLength} tokens`,
      displaySummary: settings.display.showRawSignalMetrics
        ? 'Technical view enabled'
        : 'Simplified view enabled',
      userSummary: `${settings.user.displayName} · ${settings.user.onboardingTrack}`,
    };
  }, [settings]);

  return (
    <div className="flex min-h-0 min-w-0 flex-1 flex-col bg-white">
      <div className="flex-1 overflow-auto px-6 py-6 lg:px-8">
        <div className="mx-auto max-w-6xl space-y-6">
          <div className="rounded-3xl border border-gray-200 bg-white p-8 shadow-sm">
            <div className="flex flex-col gap-5 lg:flex-row lg:items-start lg:justify-between">
              <div>
                <p className="text-sm font-semibold uppercase tracking-[0.2em] text-primary-700">
                  Settings
                </p>
                <h2 className="mt-3 text-3xl font-semibold text-gray-900">
                  Configure the assistant for your role, interface preferences, and backend behavior.
                </h2>
                <p className="mt-3 max-w-3xl text-base leading-7 text-gray-600">
                  This page is designed to hold real controls that affect explanations, evidence display,
                  conversation behavior, and future model-routing decisions such as VT ARC-backed profiles.
                </p>
              </div>

              <div className="grid gap-3 sm:grid-cols-3 lg:w-[420px]">
                <div className="rounded-2xl border border-gray-200 bg-gray-50 p-4">
                  <div className="text-xs font-semibold uppercase tracking-wide text-gray-500">
                    User
                  </div>
                  <div className="mt-2 text-sm font-medium text-gray-900">
                    {settingsSummary.userSummary}
                  </div>
                </div>

                <div className="rounded-2xl border border-gray-200 bg-gray-50 p-4">
                  <div className="text-xs font-semibold uppercase tracking-wide text-gray-500">
                    Assistant
                  </div>
                  <div className="mt-2 text-sm font-medium text-gray-900">
                    {settingsSummary.modelSummary}
                  </div>
                </div>

                <div className="rounded-2xl border border-gray-200 bg-gray-50 p-4">
                  <div className="text-xs font-semibold uppercase tracking-wide text-gray-500">
                    Display
                  </div>
                  <div className="mt-2 text-sm font-medium text-gray-900">
                    {settingsSummary.displaySummary}
                  </div>
                </div>
              </div>
            </div>

            <div className="mt-6 flex flex-wrap items-center gap-3">
              <button
                type="button"
                onClick={handleSave}
                className="inline-flex items-center gap-2 rounded-xl bg-primary-600 px-4 py-2.5 text-sm font-medium text-white hover:bg-primary-700"
              >
                <Save className="h-4 w-4" />
                Save settings
              </button>

              <button
                type="button"
                onClick={handleResetDefaults}
                className="inline-flex items-center gap-2 rounded-xl border border-gray-200 px-4 py-2.5 text-sm font-medium text-gray-700 hover:bg-gray-50"
              >
                <RotateCcw className="h-4 w-4" />
                Reset defaults
              </button>

              {saveNotice ? <div className="text-sm text-gray-600">{saveNotice}</div> : null}
            </div>
          </div>

          <SectionCard
            icon={User}
            title="User profile"
            description="Use real user information that changes how explanations are framed and which defaults the assistant should prefer."
          >
            <div className="grid gap-5 md:grid-cols-2">
              <Field label="Display name" hint="Shown in the interface and available for future personalization.">
                <Input
                  value={settings.user.displayName}
                  onChange={(e) => updateSection('user', 'displayName', e.target.value)}
                  placeholder="Boeing New Hire"
                />
              </Field>

              <Field label="Onboarding track" hint="Useful for tailoring explanations to your role.">
                <Select
                  value={settings.user.onboardingTrack}
                  onChange={(e) => updateSection('user', 'onboardingTrack', e.target.value)}
                >
                  <option>General Engineering</option>
                  <option>Systems</option>
                  <option>Structures</option>
                  <option>Propulsion</option>
                  <option>Manufacturing</option>
                  <option>Flight Test</option>
                  <option>Supply Chain</option>
                </Select>
              </Field>

              <Field label="Team / organization" hint="Optional, but useful for future routing and saved defaults.">
                <Input
                  value={settings.user.teamOrg}
                  onChange={(e) => updateSection('user', 'teamOrg', e.target.value)}
                  placeholder="Commercial Airplanes / Systems"
                />
              </Field>

              <Field label="Experience level" hint="Helps determine explanation depth.">
                <Select
                  value={settings.user.experienceLevel}
                  onChange={(e) => updateSection('user', 'experienceLevel', e.target.value)}
                >
                  <option>New hire</option>
                  <option>Early career</option>
                  <option>Experienced engineer</option>
                  <option>Manager / reviewer</option>
                </Select>
              </Field>

              <Field
                label="Aircraft families of interest"
                hint="Comma-separated values. These can drive future shortcuts, search defaults, and onboarding recommendations."
              >
                <Input
                  value={settings.user.aircraftFocus.join(', ')}
                  onChange={(e) => handleAircraftFocusChange(e.target.value)}
                  placeholder="737, 787, 777X"
                />
              </Field>

              <Field label="Preferred units" hint="Can affect future answer formatting.">
                <Select
                  value={settings.user.units}
                  onChange={(e) => updateSection('user', 'units', e.target.value)}
                >
                  <option>Imperial</option>
                  <option>Metric</option>
                  <option>Mixed</option>
                </Select>
              </Field>

              <Field label="Explanation style" hint="Controls how technical or concise future answers should feel.">
                <Select
                  value={settings.user.explanationStyle}
                  onChange={(e) => updateSection('user', 'explanationStyle', e.target.value)}
                >
                  <option>Balanced</option>
                  <option>Beginner-friendly</option>
                  <option>Technical</option>
                  <option>Concise</option>
                </Select>
              </Field>
            </div>
          </SectionCard>

          <SectionCard
            icon={Brain}
            title="Assistant behavior"
            description="These settings map cleanly to future backend controls. They are the most useful source of model flexibility, including possible VT ARC-backed routing."
          >
            <div className="grid gap-5 md:grid-cols-2">
              <Field label="Model profile" hint="A user-facing abstraction over whichever backend model the system routes to.">
                <Select
                  value={settings.assistant.modelProfile}
                  onChange={(e) => updateSection('assistant', 'modelProfile', e.target.value)}
                >
                  <option value="default">Default</option>
                  <option value="fast">Fast response</option>
                  <option value="high_confidence">High confidence</option>
                  <option value="technical">Technical depth</option>
                  <option value="arc_profile">VT ARC profile</option>
                </Select>
              </Field>

              <Field label="Backend target" hint="Keep this user-friendly. The backend should translate these labels into actual routing logic.">
                <Select
                  value={settings.assistant.backendTarget}
                  onChange={(e) => updateSection('assistant', 'backendTarget', e.target.value)}
                >
                  <option value="default_backend">Default backend</option>
                  <option value="vt_arc">VT ARC-hosted model</option>
                  <option value="fallback">Fallback backend</option>
                </Select>
              </Field>

              <Field
                label="VT ARC model profile"
                hint="Only meaningful if your backend exposes supported ARC profiles. The frontend should not handle raw cluster details."
              >
                <Select
                  value={settings.assistant.arcModelProfile}
                  onChange={(e) => updateSection('assistant', 'arcModelProfile', e.target.value)}
                >
                  <option value="arc_llama3_8b">ARC - Llama 3 8B</option>
                  <option value="arc_mistral_7b">ARC - Mistral 7B</option>
                  <option value="arc_high_accuracy">ARC - High Accuracy</option>
                </Select>
              </Field>

              <Field label="Confidence verbosity" hint="Controls how much technical detail is shown around trust scoring.">
                <Select
                  value={settings.assistant.confidenceVerbosity}
                  onChange={(e) => updateSection('assistant', 'confidenceVerbosity', e.target.value)}
                >
                  <option>Basic</option>
                  <option>Balanced</option>
                  <option>Technical</option>
                </Select>
              </Field>

              <Field label="Retrieval depth (top_k)" hint="How many evidence chunks should be retrieved by default.">
                <NumberInput
                  min={1}
                  max={20}
                  value={settings.assistant.retrievalDepth}
                  onChange={(e) =>
                    updateSection('assistant', 'retrievalDepth', Number(e.target.value))
                  }
                />
              </Field>

              <Field label="Response length (max tokens)" hint="Useful when you want shorter or more detailed answers.">
                <NumberInput
                  min={50}
                  max={1500}
                  step={25}
                  value={settings.assistant.responseLength}
                  onChange={(e) =>
                    updateSection('assistant', 'responseLength', Number(e.target.value))
                  }
                />
              </Field>

              <Field label="Temperature" hint="Lower values are more deterministic.">
                <NumberInput
                  min={0}
                  max={1}
                  step={0.05}
                  value={settings.assistant.temperature}
                  onChange={(e) =>
                    updateSection('assistant', 'temperature', Number(e.target.value))
                  }
                />
              </Field>

              <Field label="Top-p" hint="Controls token selection diversity when supported by the backend.">
                <NumberInput
                  min={0}
                  max={1}
                  step={0.05}
                  value={settings.assistant.topP}
                  onChange={(e) => updateSection('assistant', 'topP', Number(e.target.value))}
                />
              </Field>

              <Field label="Repetition penalty" hint="Helps reduce repetitive outputs when supported.">
                <NumberInput
                  min={1}
                  max={2}
                  step={0.05}
                  value={settings.assistant.repetitionPenalty}
                  onChange={(e) =>
                    updateSection('assistant', 'repetitionPenalty', Number(e.target.value))
                  }
                />
              </Field>
            </div>

            <div className="grid gap-4 md:grid-cols-2">
              <Toggle
                checked={settings.assistant.strictGroundedMode}
                onChange={(value) => updateSection('assistant', 'strictGroundedMode', value)}
                label="Strict grounded-answer mode"
                hint="Prefer withholding or downgrading answers that are not sufficiently supported by retrieved evidence."
              />

              <Toggle
                checked={settings.assistant.allowDraftAnswers}
                onChange={(value) => updateSection('assistant', 'allowDraftAnswers', value)}
                label="Allow draft answers with warning"
                hint="Useful when you still want an answer shown even if confidence is not high."
              />
            </div>

            <div className="rounded-2xl border border-dashed border-gray-300 bg-slate-50 px-4 py-4 text-sm leading-6 text-gray-600">
              <div className="flex items-start gap-2">
                <Info className="mt-0.5 h-4 w-4 shrink-0 text-slate-600" />
                <span>
                  Recommendation: keep VT ARC selection user-friendly in the UI. Let the backend map
                  “VT ARC profile” to specific cluster resources or models, rather than exposing raw
                  deployment details here.
                </span>
              </div>
            </div>
          </SectionCard>

          <SectionCard
            icon={LayoutPanelLeft}
            title="Interface and evidence display"
            description="These settings affect how much technical detail the user sees and how the right panel behaves by default."
          >
            <div className="grid gap-4 md:grid-cols-2">
              <Toggle
                checked={settings.display.showEvidenceByDefault}
                onChange={(value) => updateSection('display', 'showEvidenceByDefault', value)}
                label="Show evidence by default"
                hint="Keep retrieved sources front-and-center for trust review."
              />

              <Toggle
                checked={settings.display.showRawSignalMetrics}
                onChange={(value) => updateSection('display', 'showRawSignalMetrics', value)}
                label="Show raw signal metrics"
                hint="Expose grounding score, generation confidence, support rate, and other technical values."
              />

              <Toggle
                checked={settings.display.showLatencyMetadata}
                onChange={(value) => updateSection('display', 'showLatencyMetadata', value)}
                label="Show latency metadata"
                hint="Display latency breakdown and related system timing details."
              />

              <Toggle
                checked={settings.display.expandRightPanelSectionsByDefault}
                onChange={(value) =>
                  updateSection('display', 'expandRightPanelSectionsByDefault', value)
                }
                label="Expand right-panel sections by default"
                hint="Useful when users frequently inspect evidence and explanation details."
              />

              <Toggle
                checked={settings.display.showInlineCitations}
                onChange={(value) => updateSection('display', 'showInlineCitations', value)}
                label="Show inline citations"
                hint="Keep source chips visible below the answer card."
              />

              <Toggle
                checked={settings.display.showRequestMetadata}
                onChange={(value) => updateSection('display', 'showRequestMetadata', value)}
                label="Show request metadata"
                hint="Display model, retriever, and request details in the review panel."
              />
            </div>
          </SectionCard>

          <SectionCard
            icon={Database}
            title="Conversation and data preferences"
            description="Keep the page useful even before backend persistence is added by defining how chat history and local UI state should behave."
          >
            <div className="grid gap-4 md:grid-cols-2">
              <Toggle
                checked={settings.data.saveConversationHistory}
                onChange={(value) => updateSection('data', 'saveConversationHistory', value)}
                label="Save conversation history"
                hint="Controls whether chats should be preserved for the user in future iterations."
              />

              <Toggle
                checked={settings.data.persistUserPreferences}
                onChange={(value) => updateSection('data', 'persistUserPreferences', value)}
                label="Persist user preferences"
                hint="Future backend hook for storing settings per user instead of only in local state."
              />

              <Toggle
                checked={settings.data.clearDraftOnNewChat}
                onChange={(value) => updateSection('data', 'clearDraftOnNewChat', value)}
                label="Clear draft on new chat"
                hint="Keep the composer empty whenever a new conversation starts."
              />
            </div>

            <div className="rounded-2xl border border-gray-200 bg-gray-50 p-5">
              <div className="text-sm font-medium text-gray-900">Danger zone</div>
              <p className="mt-1 text-sm leading-6 text-gray-600">
                Keep destructive actions separated so the page remains safe and understandable.
              </p>

              <div className="mt-4 flex flex-wrap gap-3">
                <button
                  type="button"
                  className="inline-flex items-center gap-2 rounded-xl border border-rose-200 bg-rose-50 px-4 py-2.5 text-sm font-medium text-rose-700 hover:bg-rose-100"
                  onClick={() => setSaveNotice('Conversation clearing is not wired yet. This is a placeholder action.')}
                >
                  <Trash2 className="h-4 w-4" />
                  Clear all conversations
                </button>
              </div>
            </div>
          </SectionCard>

         
        </div>
      </div>
    </div>
  );
}