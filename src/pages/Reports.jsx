/**
 * Reports.jsx  — Test outcome summaries page (Stage 6A Persistent SQLite Reports)
 *
 * Computes real statistics from SQLite database runs:
 *  - Real total runs, pass rate %, failure count, and average duration
 *  - Scenario breakdown cards (smoke_test, saucedemo workflows, agent loop)
 *  - Distinguishes real SQLite records from baseline demo data
 *
 * Props:
 *   searchQuery     — global search string
 *   reportsSummary  — aggregated metrics from /api/reports/summary
 *   onRefreshHistory— callback to re-query database
 */

import { useState } from 'react';
import {
  BarChart2,
  CheckCircle2,
  XCircle,
  Clock,
  RotateCcw,
  Database,
  Layers,
  ArrowRight,
} from 'lucide-react';
import { demoReports } from '../data/demoData';

function PassBar({ passed, total }) {
  const pct = total > 0 ? Math.round((passed / total) * 100) : 0;
  return (
    <div className="space-y-1">
      <div className="flex justify-between text-[10px] text-gray-500">
        <span className="font-semibold text-gray-700">{pct}% pass rate</span>
        <span>{passed} / {total} runs passed</span>
      </div>
      <div className="h-2 bg-gray-100 rounded-full overflow-hidden">
        <div
          className={`h-full rounded-full transition-all ${
            pct >= 90 ? 'bg-emerald-500' : pct >= 70 ? 'bg-amber-500' : 'bg-red-500'
          }`}
          style={{ width: `${pct}%` }}
        />
      </div>
    </div>
  );
}

function formatScenarioName(scenarioKey) {
  const map = {
    smoke_test: 'General Web Smoke Testing',
    saucedemo_login: 'Direct SauceDemo Login Workflow',
    saucedemo_valid_login: 'SauceDemo Standard User Login & Inventory',
    saucedemo_locked_out_login: 'SauceDemo Locked-Out User Verification',
    saucedemo_invalid_login: 'SauceDemo Invalid Credentials Error Banner',
    observe_act_evaluate_loop: 'Stage 5 Observe–Act–Evaluate Autonomous Agent Loop',
  };
  return map[scenarioKey] || scenarioKey;
}

export default function Reports({ searchQuery, reportsSummary, onRefreshHistory }) {
  const [viewMode, setViewMode] = useState('auto'); // 'auto', 'real', 'demo'
  const hasRealData = reportsSummary && !reportsSummary.is_empty && reportsSummary.total_runs > 0;
  const isViewingReal = viewMode === 'real' || (viewMode === 'auto' && hasRealData);

  const q = (searchQuery || '').toLowerCase();

  // Filter real scenario reports
  const realScenarios = (reportsSummary?.scenario_reports || []).filter(r =>
    !q || r.scenario.toLowerCase().includes(q) || formatScenarioName(r.scenario).toLowerCase().includes(q)
  );

  // Filter demo reports
  const visibleDemo = demoReports.filter(r =>
    !q || r.title.toLowerCase().includes(q)
  );

  return (
    <div className="space-y-5">
      {/* ── Header ──────────────────────────────────────────── */}
      <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-3">
        <div>
          <h1 className="text-xl font-bold text-gray-900">Reports & Analytics</h1>
          <p className="text-sm text-gray-500 mt-0.5">
            Aggregated test outcome telemetry calculated directly from persistent execution logs.
          </p>
        </div>

        {/* View Mode Switcher & Refresh */}
        <div className="flex items-center gap-2">
          {hasRealData && (
            <div className="flex bg-gray-100 p-0.5 rounded-xl border border-gray-200 text-xs font-medium">
              <button
                type="button"
                onClick={() => setViewMode('real')}
                className={`px-3 py-1 rounded-lg transition-all cursor-pointer ${
                  isViewingReal
                    ? 'bg-white text-emerald-800 shadow-sm font-semibold'
                    : 'text-gray-600 hover:text-gray-900'
                }`}
              >
                ● Live SQLite ({reportsSummary.total_runs})
              </button>
              <button
                type="button"
                onClick={() => setViewMode('demo')}
                className={`px-3 py-1 rounded-lg transition-all cursor-pointer ${
                  !isViewingReal
                    ? 'bg-white text-gray-800 shadow-sm font-semibold'
                    : 'text-gray-600 hover:text-gray-900'
                }`}
              >
                Demo Baseline
              </button>
            </div>
          )}

          {onRefreshHistory && (
            <button
              type="button"
              onClick={onRefreshHistory}
              title="Refresh reports from SQLite database"
              className="p-2 bg-white border border-gray-200 hover:bg-gray-50 text-gray-600 rounded-xl transition-colors shadow-sm cursor-pointer"
            >
              <RotateCcw size={14} />
            </button>
          )}
        </div>
      </div>

      {/* ── Summary Banner ──────────────────────────────────── */}
      {isViewingReal && hasRealData ? (
        <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
          <div className="bg-white rounded-2xl border border-gray-100 shadow-sm p-4 flex items-center gap-3">
            <div className="w-10 h-10 rounded-xl flex items-center justify-center bg-indigo-50 text-indigo-600">
              <Database size={18} />
            </div>
            <div>
              <p className="text-xs text-gray-500 font-medium">Total Real Runs</p>
              <p className="text-xl font-bold text-gray-900">{reportsSummary.total_runs}</p>
            </div>
          </div>

          <div className="bg-white rounded-2xl border border-gray-100 shadow-sm p-4 flex items-center gap-3">
            <div className="w-10 h-10 rounded-xl flex items-center justify-center bg-emerald-50 text-emerald-600">
              <CheckCircle2 size={18} />
            </div>
            <div>
              <p className="text-xs text-gray-500 font-medium">Passed Assertions</p>
              <p className="text-xl font-bold text-emerald-700">{reportsSummary.passed_runs}</p>
            </div>
          </div>

          <div className="bg-white rounded-2xl border border-gray-100 shadow-sm p-4 flex items-center gap-3">
            <div className="w-10 h-10 rounded-xl flex items-center justify-center bg-red-50 text-red-500">
              <XCircle size={18} />
            </div>
            <div>
              <p className="text-xs text-gray-500 font-medium">Failures / Errors</p>
              <p className="text-xl font-bold text-red-600">
                {reportsSummary.failed_runs + reportsSummary.error_runs}
              </p>
            </div>
          </div>

          <div className="bg-white rounded-2xl border border-gray-100 shadow-sm p-4 flex items-center gap-3">
            <div className="w-10 h-10 rounded-xl flex items-center justify-center bg-sky-50 text-sky-600">
              <Clock size={18} />
            </div>
            <div>
              <p className="text-xs text-gray-500 font-medium">Avg Duration</p>
              <p className="text-xl font-bold text-gray-900">
                {(reportsSummary.avg_duration_ms / 1000).toFixed(1)}s
              </p>
            </div>
          </div>
        </div>
      ) : (
        <div className="grid grid-cols-3 gap-4">
          <div className="bg-white rounded-2xl border border-gray-100 shadow-sm p-4 flex items-center gap-3">
            <div className="w-9 h-9 rounded-xl flex items-center justify-center bg-indigo-50 text-indigo-600">
              <BarChart2 size={17} />
            </div>
            <div>
              <p className="text-xs text-gray-500">Demo Reports</p>
              <p className="text-xl font-bold text-gray-900">{demoReports.length}</p>
            </div>
          </div>
          <div className="bg-white rounded-2xl border border-gray-100 shadow-sm p-4 flex items-center gap-3">
            <div className="w-9 h-9 rounded-xl flex items-center justify-center bg-emerald-50 text-emerald-600">
              <CheckCircle2 size={17} />
            </div>
            <div>
              <p className="text-xs text-gray-500">Demo Passed</p>
              <p className="text-xl font-bold text-gray-900">
                {demoReports.reduce((a, r) => a + r.passed, 0)}
              </p>
            </div>
          </div>
          <div className="bg-white rounded-2xl border border-gray-100 shadow-sm p-4 flex items-center gap-3">
            <div className="w-9 h-9 rounded-xl flex items-center justify-center bg-red-50 text-red-500">
              <XCircle size={17} />
            </div>
            <div>
              <p className="text-xs text-gray-500">Demo Failed</p>
              <p className="text-xl font-bold text-gray-900">
                {demoReports.reduce((a, r) => a + r.failed, 0)}
              </p>
            </div>
          </div>
        </div>
      )}

      {/* ── Report Cards Section ─────────────────────────────── */}
      {isViewingReal ? (
        realScenarios.length === 0 ? (
          <div className="bg-white rounded-2xl border border-gray-100 shadow-sm flex flex-col items-center justify-center py-16 text-center p-6">
            <Database size={28} className="text-gray-300 mb-2" />
            <p className="text-sm font-semibold text-gray-800">No matching persistent reports in SQLite</p>
            <p className="text-xs text-gray-500 mt-1 max-w-sm">
              Execute a test run via the Overview form or run an autonomous agent loop to generate persistent telemetry records.
            </p>
          </div>
        ) : (
          <div className="space-y-3">
            {realScenarios.map((sc, idx) => (
              <div
                key={sc.scenario || idx}
                className="bg-white rounded-2xl border border-gray-100 shadow-sm p-5 hover:border-indigo-100 hover:shadow-md transition-all"
              >
                <div className="flex items-start justify-between gap-4 mb-3">
                  <div>
                    <div className="flex items-center gap-2">
                      <p className="text-sm font-bold text-gray-900">
                        {formatScenarioName(sc.scenario)}
                      </p>
                      <span className="text-[10px] bg-emerald-50 text-emerald-700 font-semibold px-2 py-0.5 rounded border border-emerald-200">
                        SQLite
                      </span>
                    </div>
                    <p className="text-xs text-gray-400 mt-0.5 flex items-center gap-1 font-mono">
                      <Clock size={11} />
                      Scenario key: {sc.scenario} · Avg: {(sc.avg_duration_ms / 1000).toFixed(1)}s
                    </p>
                  </div>

                  <span className="text-xs font-semibold px-2.5 py-1 rounded-lg bg-gray-50 text-gray-700 border border-gray-200">
                    {sc.total} {sc.total === 1 ? 'Run' : 'Runs'} Total
                  </span>
                </div>

                <PassBar passed={sc.passed} total={sc.total} />

                <div className="mt-3.5 flex items-center justify-between text-xs pt-1 border-t border-gray-50">
                  <div className="flex items-center gap-4">
                    <span className="flex items-center gap-1 text-emerald-600 font-medium">
                      <CheckCircle2 size={13} />
                      {sc.passed} Passed
                    </span>
                    <span className="flex items-center gap-1 text-red-500 font-medium">
                      <XCircle size={13} />
                      {sc.failed} Failed
                    </span>
                  </div>
                  <span className="text-[11px] text-gray-400">
                    Calculated from real Playwright DOM assertions
                  </span>
                </div>
              </div>
            ))}
          </div>
        )
      ) : (
        /* Baseline demo reports display */
        <div className="space-y-3">
          {visibleDemo.map(rep => (
            <div
              key={rep.id}
              className="bg-white rounded-2xl border border-gray-100 shadow-sm p-5 hover:border-indigo-100 hover:shadow-md transition-all"
            >
              <div className="flex items-start justify-between gap-4 mb-3">
                <div>
                  <div className="flex items-center gap-2">
                    <p className="text-sm font-semibold text-gray-900">{rep.title}</p>
                    <span className="text-[10px] bg-amber-50 text-amber-700 font-medium px-2 py-0.5 rounded border border-amber-200">
                      Demo
                    </span>
                  </div>
                  <p className="text-xs text-gray-400 mt-0.5 flex items-center gap-1">
                    <Clock size={10} />
                    {rep.createdAt} · Total duration: {rep.duration}
                  </p>
                </div>
              </div>

              <PassBar passed={rep.passed} total={rep.total} />

              <div className="mt-3 flex items-center gap-4 text-xs">
                <span className="flex items-center gap-1 text-emerald-600">
                  <CheckCircle2 size={12} />
                  {rep.passed} Passed
                </span>
                <span className="flex items-center gap-1 text-red-500">
                  <XCircle size={12} />
                  {rep.failed} Failed
                </span>
              </div>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}
