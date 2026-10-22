/**
 * Settings.jsx  — Application preferences and future agent configuration
 *
 * Contains:
 *  - UI preferences (theme toggle, notifications)
 *  - Agent configuration placeholders (for future FastAPI backend)
 *  - API key placeholder (with clear "not yet implemented" label)
 */

import { useState } from 'react';
import { Settings2, Bot, Bell, Palette, Key, Info } from 'lucide-react';

function Section({ icon: Icon, title, description, children }) {
  return (
    <div className="bg-white rounded-2xl border border-gray-100 shadow-sm p-5">
      <div className="flex items-center gap-2 mb-1">
        <Icon size={16} className="text-indigo-500" />
        <h2 className="text-sm font-bold text-gray-900">{title}</h2>
      </div>
      {description && <p className="text-xs text-gray-400 mb-4">{description}</p>}
      <div className="mt-4 space-y-4">{children}</div>
    </div>
  );
}

function Toggle({ label, description, checked, onChange }) {
  return (
    <div className="flex items-center justify-between gap-4">
      <div>
        <p className="text-sm font-medium text-gray-800">{label}</p>
        {description && <p className="text-xs text-gray-400 mt-0.5">{description}</p>}
      </div>
      <button
        onClick={() => onChange(!checked)}
        className={`relative w-10 h-5.5 rounded-full transition-colors cursor-pointer flex-shrink-0 ${
          checked ? 'bg-indigo-600' : 'bg-gray-200'
        }`}
        style={{ minWidth: '40px', height: '22px' }}
      >
        <span
          className={`absolute top-0.5 left-0.5 w-4.5 h-4.5 bg-white rounded-full shadow transition-transform ${
            checked ? 'translate-x-[18px]' : 'translate-x-0'
          }`}
          style={{ width: '18px', height: '18px' }}
        />
      </button>
    </div>
  );
}

function InputField({ label, description, placeholder, disabled = false, type = 'text' }) {
  return (
    <div>
      <label className="block text-sm font-medium text-gray-800 mb-1">{label}</label>
      {description && <p className="text-xs text-gray-400 mb-2">{description}</p>}
      <input
        type={type}
        placeholder={placeholder}
        disabled={disabled}
        className="w-full px-3 py-2 text-sm border border-gray-200 rounded-lg bg-gray-50 focus:outline-none focus:ring-2 focus:ring-indigo-400 disabled:opacity-50 disabled:cursor-not-allowed"
      />
    </div>
  );
}

export default function Settings({ theme, onToggleTheme }) {
  const [notifications, setNotifications] = useState(true);
  const [autoEvidence, setAutoEvidence]   = useState(true);
  const [verboseLog, setVerboseLog]       = useState(false);

  return (
    <div className="space-y-5 max-w-2xl">
      {/* ── Header ──────────────────────────────────────────── */}
      <div>
        <h1 className="text-xl font-bold text-gray-900">Settings</h1>
        <p className="text-sm text-gray-500 mt-0.5">Interface preferences and future agent configuration.</p>
      </div>

      {/* ── UI Preferences ──────────────────────────────────── */}
      <Section
        icon={Palette}
        title="Interface"
        description="Visual and notification preferences."
      >
        <Toggle
          label="Dark mode"
          description="Switch to a dark color scheme (partially implemented in this prototype)."
          checked={theme === 'dark'}
          onChange={onToggleTheme}
        />
        <Toggle
          label="Notifications"
          description="Show in-app notifications when a test run completes."
          checked={notifications}
          onChange={setNotifications}
        />
        <Toggle
          label="Auto-show failure evidence"
          description="Automatically expand the failure evidence panel after a failed run."
          checked={autoEvidence}
          onChange={setAutoEvidence}
        />
      </Section>

      {/* ── Agent configuration (future) ─────────────────────── */}
      <Section
        icon={Bot}
        title="Agent Configuration"
        description="These settings will connect to the Python/FastAPI backend in a future version."
      >
        <div className="flex items-start gap-2 p-3 bg-amber-50 border border-amber-100 rounded-xl mb-2">
          <Info size={14} className="text-amber-500 mt-0.5 flex-shrink-0" />
          <p className="text-xs text-amber-700">
            Backend integration is not yet implemented. These fields are shown for UX design purposes only.
            No data is sent or stored.
          </p>
        </div>
        <InputField
          label="Agent backend URL"
          description="Base URL of your FastAPI backend server."
          placeholder="http://localhost:8000"
          disabled
        />
        <Toggle
          label="Verbose agent logging"
          description="Log every browser action step in the run panel."
          checked={verboseLog}
          onChange={setVerboseLog}
        />
      </Section>

      {/* ── API key placeholder ──────────────────────────────── */}
      <Section
        icon={Key}
        title="API Keys"
        description="Never enter real credentials here. This field is a UI placeholder only — no backend exists yet."
      >
        <div className="flex items-start gap-2 p-3 bg-red-50 border border-red-100 rounded-xl mb-2">
          <Info size={14} className="text-red-500 mt-0.5 flex-shrink-0" />
          <p className="text-xs text-red-700">
            Do not enter a real API key here. This is a frontend-only prototype.
            Real key management will be handled server-side in the future backend.
          </p>
        </div>
        <InputField
          label="LLM API Key (future)"
          description="Will be stored securely by the backend — never in the browser."
          placeholder="sk-••••••••••••••••••••"
          type="password"
          disabled
        />
      </Section>

      {/* ── Notifications ────────────────────────────────────── */}
      <Section
        icon={Bell}
        title="Notifications"
        description="Manage how ProbeQA communicates test results."
      >
        <InputField
          label="Email for reports"
          description="Will be used to send test report summaries (future backend feature)."
          placeholder="you@example.com"
          type="email"
          disabled
        />
      </Section>

      {/* ── About ────────────────────────────────────────────── */}
      <Section
        icon={Settings2}
        title="About ProbeQA"
      >
        <div className="space-y-1 text-xs text-gray-500">
          <p><span className="font-medium text-gray-700">Version:</span> 0.1.0 (Frontend prototype)</p>
          <p><span className="font-medium text-gray-700">Stack:</span> React 19 · Vite · Tailwind CSS v4 · Lucide</p>
          <p><span className="font-medium text-gray-700">Planned backend:</span> Python · FastAPI · Playwright · LLM API</p>
          <p className="text-amber-600 font-medium mt-2">
            ⚠ All data shown in this application is demonstration data only.
            No real browser tests have been executed.
          </p>
        </div>
      </Section>
    </div>
  );
}
