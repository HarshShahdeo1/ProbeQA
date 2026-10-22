/**
 * FailureEvidence.jsx
 *
 * Displays failure evidence and diagnostic data for a test run.
 * Supports both real Playwright browser screenshots and baseline demo placeholders.
 *
 * Props:
 *   evidence — structured evidence object
 *   run      — associated run object
 *   onClose  — optional callback to dismiss the panel
 */

import { useState } from 'react';
import { AlertCircle, FileImage, FileText, ExternalLink, X, CheckCircle2 } from 'lucide-react';

export default function FailureEvidence({ evidence, run, onClose }) {
  const [imageError, setImageError] = useState(false);

  if (!evidence) {
    return (
      <div className="bg-white rounded-2xl border border-gray-100 shadow-sm p-6 flex flex-col items-center justify-center text-center min-h-32">
        <AlertCircle size={24} className="text-gray-300 mb-2" />
        <p className="text-sm text-gray-500">No failure evidence selected.</p>
        <p className="text-xs text-gray-400 mt-1">Click "Evidence" on a failed test run to view details.</p>
      </div>
    );
  }

  const isReal = Boolean(evidence.isRealTest);

  return (
    <div className="bg-white rounded-2xl border border-gray-100 shadow-sm overflow-hidden">
      {/* ── Header ──────────────────────────────────────────── */}
      <div className="flex items-center gap-2 px-5 py-4 border-b border-gray-100">
        <div className={`w-7 h-7 rounded-lg flex items-center justify-center flex-shrink-0 ${isReal ? 'bg-indigo-50 text-indigo-600' : 'bg-red-50 text-red-500'}`}>
          <AlertCircle size={14} />
        </div>
        <div className="min-w-0">
          <h2 className="text-sm font-bold text-gray-900">Execution evidence & diagnostics</h2>
          <p className="text-xs text-gray-400">
            Browser screenshot, assertion outcomes, and HTTP diagnostic logs.
            {isReal ? (
              <span className="ml-1.5 text-emerald-600 font-semibold bg-emerald-50 px-1.5 py-0.5 rounded text-[10px] border border-emerald-200">
                REAL PLAYWRIGHT EVIDENCE
              </span>
            ) : (
              <span className="ml-1.5 text-amber-600 font-semibold bg-amber-50 px-1.5 py-0.5 rounded text-[10px] border border-amber-200">
                DEMO DATA
              </span>
            )}
          </p>
        </div>
        <div className="ml-auto flex items-center gap-2">
          {evidence.screenshotUrl && (
            <a
              href={evidence.screenshotUrl}
              target="_blank"
              rel="noreferrer"
              className="flex items-center gap-1 text-xs text-indigo-600 hover:text-indigo-800 transition-colors cursor-pointer"
            >
              Open screenshot <ExternalLink size={10} />
            </a>
          )}
          {onClose && (
            <button
              onClick={onClose}
              className="w-7 h-7 rounded-lg flex items-center justify-center text-gray-400 hover:bg-gray-100 transition-colors cursor-pointer"
            >
              <X size={14} />
            </button>
          )}
        </div>
      </div>

      <div className="p-5 grid grid-cols-1 lg:grid-cols-2 gap-5">
        {/* ── Screenshot container ────────────────────────────── */}
        <div className="flex flex-col gap-2">
          <div className="flex items-center justify-between">
            <p className="text-xs font-semibold text-gray-500 uppercase tracking-wide">
              {isReal ? 'Playwright Captured Screenshot' : 'Browser Screenshot'}
            </p>
            {evidence.screenshotUrl && (
              <span className="text-[10px] text-gray-400">1280 × 800 Viewport</span>
            )}
          </div>

          {/* Browser chrome wrapper */}
          <div className="border border-gray-200 rounded-xl overflow-hidden bg-gray-50 shadow-inner flex flex-col">
            {/* Browser toolbar */}
            <div className="bg-gray-100 border-b border-gray-200 px-3 py-2 flex items-center gap-2">
              <div className="flex gap-1.5">
                <span className="w-2.5 h-2.5 rounded-full bg-red-400" />
                <span className="w-2.5 h-2.5 rounded-full bg-amber-400" />
                <span className="w-2.5 h-2.5 rounded-full bg-emerald-400" />
              </div>
              <div className="flex-1 bg-white border border-gray-200 rounded px-2 py-0.5 text-[10px] text-gray-500 font-mono truncate">
                {evidence.targetUrl}
              </div>
            </div>

            {/* Real screenshot or demo fallback */}
            {evidence.screenshotUrl && !imageError ? (
              <div className="p-2 bg-gray-900/5 flex items-center justify-center min-h-56">
                <img
                  src={evidence.screenshotUrl}
                  alt={`Screenshot of ${evidence.targetUrl}`}
                  className="max-h-80 w-full object-contain rounded shadow-sm border border-gray-200"
                  onError={() => setImageError(true)}
                />
              </div>
            ) : (
              /* Simulated mock page content (for baseline demo rows or if image fails) */
              <div className="p-4 min-h-48 flex flex-col">
                <div className="flex items-center justify-between mb-4 pb-2 border-b border-gray-200">
                  <span className="text-xs font-bold text-gray-700">DemoShop</span>
                  <div className="flex gap-3">
                    {['Home', 'Products', 'Cart', 'Login'].map(l => (
                      <span key={l} className="text-[10px] text-gray-500">{l}</span>
                    ))}
                  </div>
                </div>

                <div className="max-w-xs mx-auto w-full space-y-3">
                  <p className="text-sm font-semibold text-gray-800 text-center">Login to your account</p>
                  <div>
                    <p className="text-[10px] text-gray-500 mb-0.5">Email</p>
                    <div className="h-7 bg-white border border-gray-200 rounded px-2 flex items-center text-[10px] text-gray-500">
                      user@example.com
                    </div>
                  </div>
                  <div>
                    <p className="text-[10px] text-gray-500 mb-0.5">Password</p>
                    <div className="h-7 bg-white border border-red-300 rounded px-2 flex items-center text-[10px] text-red-400">
                      ••••••••••••
                    </div>
                  </div>
                  <div className="flex items-center gap-1 text-[10px] text-red-500">
                    <AlertCircle size={9} />
                    Invalid credentials. Please try again.
                  </div>
                  <div className="h-7 bg-indigo-600 rounded flex items-center justify-center text-[10px] text-white font-semibold">
                    Login
                  </div>
                </div>

                <div className="mt-auto pt-3 flex items-center gap-1.5 text-[10px] text-red-500 border-t border-red-100">
                  <AlertCircle size={10} />
                  <span>Assertion failed at this step — error message was not detected</span>
                </div>
              </div>
            )}
          </div>

          {/* File link footer */}
          <div className="flex items-center gap-3 mt-1">
            {evidence.screenshotUrl ? (
              <a
                href={evidence.screenshotUrl}
                target="_blank"
                rel="noreferrer"
                className="flex items-center gap-1 text-[11px] text-indigo-600 hover:text-indigo-800 transition-colors"
              >
                <FileImage size={11} />
                {evidence.screenshotFile}
              </a>
            ) : (
              <span className="flex items-center gap-1 text-[11px] text-gray-500">
                <FileImage size={11} />
                {evidence.screenshotFile}
              </span>
            )}
            <span className="flex items-center gap-1 text-[11px] text-gray-400">
              <FileText size={11} />
              {evidence.logFile || 'execution.log'}
            </span>
          </div>
        </div>

        {/* ── Error & assertion details ───────────────────────── */}
        <div className="flex flex-col gap-4">
          {/* Summary Banner */}
          <div className={`p-3 rounded-xl border ${isReal && !evidence.errorSummary?.includes('failed') ? 'bg-emerald-50 border-emerald-100' : 'bg-red-50 border-red-100'}`}>
            <p className={`text-[10px] font-bold uppercase tracking-wide mb-1 ${isReal && !evidence.errorSummary?.includes('failed') ? 'text-emerald-700' : 'text-red-600'}`}>
              Diagnostic Status
            </p>
            <p className={`text-sm font-medium ${isReal && !evidence.errorSummary?.includes('failed') ? 'text-emerald-900' : 'text-red-800'}`}>
              {evidence.errorSummary}
            </p>
          </div>

          {/* Structured Key-Value Table */}
          <div>
            <p className="text-xs font-semibold text-gray-500 uppercase tracking-wide mb-2">Execution Breakdown</p>
            <div className="space-y-2 border border-gray-100 rounded-xl p-3 bg-gray-50/50">
              {[
                { label: 'Step',        value: evidence.failingStep },
                { label: 'Expected',    value: evidence.expected },
                { label: 'Actual',      value: evidence.actual },
                { label: 'Target URL',  value: evidence.targetUrl, mono: true },
                { label: 'Timestamp',   value: evidence.timestamp },
                { label: 'Screenshot',  value: evidence.screenshotFile, link: evidence.screenshotUrl },
                ...(evidence.pageTitle ? [{ label: 'Page Title', value: `"${evidence.pageTitle}"` }] : []),
              ].map(({ label, value, mono, link }) => (
                <div key={label} className="grid grid-cols-[85px_1fr] gap-2 text-xs">
                  <span className="text-gray-400 font-medium pt-0.5">{label}</span>
                  {link ? (
                    <a
                      href={link}
                      target="_blank"
                      rel="noreferrer"
                      className="text-left text-indigo-600 hover:text-indigo-800 flex items-center gap-1 truncate"
                    >
                      <FileImage size={10} />
                      <span className="truncate">{value}</span>
                    </a>
                  ) : (
                    <span className={`text-gray-800 break-all ${mono ? 'font-mono text-[11px]' : ''}`}>
                      {value}
                    </span>
                  )}
                </div>
              ))}
            </div>
          </div>

          {/* Stage 5 Agent Loop Trace if available */}
          {evidence.steps && evidence.steps.length > 0 && (
            <div>
              <p className="text-xs font-semibold text-gray-500 uppercase tracking-wide mb-2">
                Agent Loop Trace ({evidence.steps.length} steps)
              </p>
              <div className="space-y-1.5 max-h-48 overflow-y-auto bg-gray-50 p-2.5 rounded-xl border border-gray-100 text-[11px]">
                {evidence.steps.map(s => (
                  <div key={s.iteration} className="bg-white p-2 rounded-lg border border-gray-100 space-y-0.5">
                    <div className="flex items-center justify-between font-mono text-[10px]">
                      <span className="font-semibold text-indigo-700">
                        Step {s.iteration}: {s.decision.action_type.toUpperCase()}({s.decision.target || 'None'})
                      </span>
                      <span className="text-gray-400">{s.duration_ms}ms</span>
                    </div>
                    <p className="text-gray-600 italic text-[10px]">Thought: {s.decision.thought}</p>
                    <p className="text-emerald-700 font-medium text-[10px]">Result: {s.action_result}</p>
                  </div>
                ))}
              </div>
            </div>
          )}

          {/* Associated scenario text */}
          {run && (
            <div className="p-3 bg-gray-50 rounded-xl border border-gray-100">
              <p className="text-[10px] font-bold text-gray-400 uppercase tracking-wide mb-1">Scenario / Goal</p>
              <p className="text-xs text-gray-700 font-medium">{run.scenario}</p>
            </div>
          )}

          {/* Scope note */}
          {evidence.limitationNote && (
            <p className="text-[10px] text-gray-400 italic">
              Note: {evidence.limitationNote}
            </p>
          )}
        </div>
      </div>
    </div>
  );
}
