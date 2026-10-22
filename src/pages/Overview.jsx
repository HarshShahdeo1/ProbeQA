/**
 * Overview.jsx  — Main dashboard page
 *
 * Shows:
 *  - Greeting header
 *  - 4 metric stat cards
 *  - Recent test runs table (compact, 4 rows)
 *  - Run-a-test form (right panel)
 *  - Failure evidence panel (below, conditionally)
 *
 * Props:
 *   testRuns        — array of run objects
 *   onNewRun        — called when a demo run completes (adds to history)
 *   onViewEvidence  — called to show evidence for a failed run
 *   selectedEvidence— {evidence, run} or null
 *   onCloseEvidence — clears the selected evidence
 *   onNavigate      — navigate to another page
 *   newTestRef      — ref forwarded to the form for scroll-to focus
 *   pendingScenario — scenario object to pre-fill (from Scenarios page)
 *   onClearPending  — clears pendingScenario after it has been consumed
 */

import { useEffect } from 'react';
import { PlayCircle, CheckCircle2, XCircle, Timer } from 'lucide-react';
import StatCard       from '../components/StatCard';
import TestRunsTable  from '../components/TestRunsTable';
import NewTestForm    from '../components/NewTestForm';
import FailureEvidence from '../components/FailureEvidence';
import { demoStats }  from '../data/demoData';

// Hour-based greeting
function greeting() {
  const h = new Date().getHours();
  if (h < 12) return 'Good morning';
  if (h < 18) return 'Good afternoon';
  return 'Good evening';
}

export default function Overview({
  testRuns,
  realDbRuns = [],
  reportsSummary,
  onRefreshHistory,
  onNewRun,
  onViewEvidence,
  selectedEvidence,
  onCloseEvidence,
  onNavigate,
  newTestRef,
  pendingScenario,
  onClearPending,
}) {
  // Scroll to the form when navigated from the Scenarios page
  useEffect(() => {
    if (pendingScenario) {
      newTestRef?.current?.scrollIntoView({ behavior: 'smooth', block: 'start' });
    }
  }, [pendingScenario, newTestRef]);

  const hasRealData = reportsSummary && !reportsSummary.is_empty;
  const totalRunsVal = hasRealData ? reportsSummary.total_runs : demoStats.totalRuns;
  const passRateVal = hasRealData ? `${reportsSummary.pass_rate}%` : `${demoStats.passRate}%`;
  const failedVal = hasRealData ? reportsSummary.failed_runs + reportsSummary.error_runs : demoStats.failedTests;
  const avgDurVal = hasRealData ? `${(reportsSummary.avg_duration_ms / 1000).toFixed(1)}s` : demoStats.avgDuration;

  return (
    <div className="space-y-6">

      {/* ── Page header ─────────────────────────────────────── */}
      <div className="flex items-start justify-between">
        <div>
          <h1 className="text-2xl font-bold text-gray-900">
            {greeting()}, Harsh 👋
          </h1>
          <p className="text-sm text-gray-500 mt-0.5">Your agent's testing activity at a glance.</p>
        </div>
        {hasRealData ? (
          <span className="text-xs text-emerald-700 bg-emerald-50 border border-emerald-200 px-2.5 py-1 rounded-full font-semibold flex items-center gap-1.5 shadow-sm">
            <span className="w-1.5 h-1.5 rounded-full bg-emerald-500 animate-pulse"></span>
            Live SQLite Storage ({reportsSummary.total_runs} real runs)
          </span>
        ) : (
          <span className="text-xs text-amber-600 bg-amber-50 border border-amber-200 px-2.5 py-1 rounded-full font-medium">
            Demo Baseline
          </span>
        )}
      </div>

      {/* ── Stat cards ──────────────────────────────────────── */}
      <div className="grid grid-cols-2 lg:grid-cols-4 gap-4">
        <StatCard
          title="Tests Run"
          value={totalRunsVal}
          delta={hasRealData ? `${reportsSummary.total_runs} executed` : demoStats.totalRunsDelta}
          deltaPos={true}
          icon={PlayCircle}
          iconBg="bg-indigo-50"
          iconColor="text-indigo-600"
          sparkColor="#6366f1"
          sparkPoints={[0.4, 0.5, 0.45, 0.6, 0.55, 0.75, 0.8]}
        />
        <StatCard
          title="Pass Rate"
          value={passRateVal}
          delta={hasRealData ? `${reportsSummary.passed_runs} passed` : demoStats.passRateDelta}
          deltaPos={true}
          icon={CheckCircle2}
          iconBg="bg-emerald-50"
          iconColor="text-emerald-600"
          sparkColor="#10b981"
          sparkPoints={[0.7, 0.75, 0.72, 0.8, 0.82, 0.88, 0.94]}
        />
        <StatCard
          title="Failed Tests"
          value={failedVal}
          delta={hasRealData ? `${failedVal} issues detected` : demoStats.failedTestsDelta}
          deltaPos={failedVal === 0}
          icon={XCircle}
          iconBg="bg-red-50"
          iconColor="text-red-500"
          sparkColor="#ef4444"
          sparkPoints={[0.3, 0.5, 0.4, 0.6, 0.35, 0.45, 0.55]}
        />
        <StatCard
          title="Avg. Duration"
          value={avgDurVal}
          delta={hasRealData ? "Real telemetry" : demoStats.avgDurationDelta}
          deltaPos={null}
          icon={Timer}
          iconBg="bg-sky-50"
          iconColor="text-sky-500"
          sparkColor="#0ea5e9"
          sparkPoints={[0.9, 0.7, 0.8, 0.6, 0.65, 0.5, 0.55]}
        />
      </div>

      {/* ── Main two-column area ─────────────────────────────── */}
      <div className="grid grid-cols-1 xl:grid-cols-[1fr_340px] gap-6">

        {/* Recent test runs */}
        <div className="bg-white rounded-2xl border border-gray-100 shadow-sm overflow-hidden">
          <div className="flex items-center justify-between px-5 py-4 border-b border-gray-100">
            <h2 className="text-sm font-bold text-gray-900">Recent test runs</h2>
            <button
              onClick={() => onNavigate('testruns')}
              className="flex items-center gap-1 text-xs text-indigo-600 hover:text-indigo-800 font-medium transition-colors cursor-pointer"
            >
              View all →
            </button>
          </div>
          <TestRunsTable
            runs={testRuns}
            onViewEvidence={onViewEvidence}
            compact={true}
          />
        </div>

        {/* New test form */}
        <div ref={newTestRef}>
          <NewTestForm
            onRunComplete={onNewRun}
            pendingScenario={pendingScenario}
            onClearPending={onClearPending}
          />
        </div>
      </div>

      {/* ── Failure evidence (shown when a failed run is selected) */}
      {selectedEvidence && (
        <FailureEvidence
          evidence={selectedEvidence.evidence}
          run={selectedEvidence.run}
          onClose={onCloseEvidence}
        />
      )}
    </div>
  );
}
