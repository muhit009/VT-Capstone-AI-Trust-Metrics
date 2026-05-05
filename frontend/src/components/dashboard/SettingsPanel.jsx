/* eslint-disable react/prop-types */

import { useMemo, useState } from 'react';
import { RotateCcw, Save, ShieldCheck, User } from 'lucide-react';
import WeightConfiguration from './WeightConfiguration';

const STORAGE_KEY = 'user_profile';

const [settings, setSettings] = useState(() => {
  try {
    const stored = localStorage.getItem(STORAGE_KEY);
    return stored ? JSON.parse(stored) : defaultSettings;
  } catch {
    return defaultSettings;
  }
});

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
    localStorage.removeItem(STORAGE_KEY);
    setSaveNotice('Profile settings reset to defaults.');
  };

  const handleSave = () => {
    try {
      localStorage.setItem(STORAGE_KEY, JSON.stringify(settings));
      setSaveNotice('Profile settings saved.');
    } catch {
      setSaveNotice('Failed to save settings.');
    }
  };

  const userSummary = useMemo(
    () => `${settings.user.displayName} · ${settings.user.onboardingTrack}`,
    [settings.user.displayName, settings.user.onboardingTrack],
  );

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
                  User profile and confidence preferences
                </h2>
                <p className="mt-3 max-w-3xl text-base leading-7 text-gray-600">
                  Keep this page focused on who the assistant is helping and how confidence should
                  be weighted in the review experience.
                </p>
              </div>

              <div className="rounded-2xl border border-gray-200 bg-gray-50 p-4 lg:w-[260px]">
                <div className="text-xs font-semibold uppercase tracking-wide text-gray-500">
                  Active profile
                </div>
                <div className="mt-2 text-sm font-medium text-gray-900">{userSummary}</div>
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
              <Field
                label="Display name"
                hint="Shown in the interface and available for future personalization."
              >
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

              <Field
                label="Team / organization"
                hint="Optional, but useful for future routing and saved defaults."
              >
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
                hint="Comma-separated values for shortcuts, search defaults, and onboarding recommendations."
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

              <Field
                label="Explanation style"
                hint="Controls how technical or concise future answers should feel."
              >
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
            icon={ShieldCheck}
            title="Confidence weights"
            description="Adjust how grounding and generation confidence contribute to the final confidence score."
          >
            <WeightConfiguration />
          </SectionCard>
        </div>
      </div>
    </div>
  );
}
