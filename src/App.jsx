/**
 * App.jsx  — Root component
 *
 * Manages global state:
 *  - activePage  : which page is currently shown
 *  - testRuns    : combined demo + newly simulated runs
 *  - searchQuery : controlled by Topbar, used by all pages
 *  - selectedEvidence : the failure evidence panel data
 *  - theme       : 'light' | 'dark' (dark is a minimal toggle for now)
 *  - prefilledUrl: pre-fills the New Test form when navigated via "+ New Test"
 *
 * Layout:
 *   [Sidebar fixed left] [Topbar sticky top] [Page content scrollable]
 */

import { useState, useRef, useEffect } from 'react';
import Sidebar   from './components/Sidebar';
import Topbar    from './components/Topbar';
import Overview  from './pages/Overview';
import TestRuns  from './pages/TestRuns';
import Scenarios from './pages/Scenarios';
import Reports   from './pages/Reports';
import Settings  from './pages/Settings';
import { demoTestRuns, demoFailureEvidence, STATUS } from './data/demoData';
import { fetchTestRuns, fetchReportsSummary, getScreenshotUrl } from './services/api';

function formatDbTimestamp(isoStr) {
  if (!isoStr) return 'Just now';
  try {
    const d = new Date(isoStr);
    return d.toLocaleString('en-GB', {
      day: 'numeric',
      month: 'short',
      year: 'numeric',
      hour: '2-digit',
      minute: '2-digit',
      hour12: true,
    });
  } catch {
    return isoStr;
  }
}

function mapDbRecordToRun(record) {
  const isPassed = record.status === 'passed';
  const cleanTarget = record.target_origin
    ? record.target_origin.replace(/^https?:\/\//, '').replace(/\/$/, '')
    : 'target';

  return {
    id: record.run_id,
    scenario: record.goal || record.scenario,
    target: cleanTarget,
    status: isPassed ? STATUS.PASSED : STATUS.FAILED,
    duration: `${(record.duration_ms / 1000).toFixed(1)}s`,
    date: formatDbTimestamp(record.started_at),
    mode: record.mode === 'agent_loop' ? 'Autonomous Loop' : record.mode === 'planned' ? 'AI-Planned' : 'Smoke Test',
    isRealTest: true,
    details: {
      runId: record.run_id,
      scenario: record.scenario,
      status: record.status,
      targetUrl: record.target_origin,
      durationMs: record.duration_ms,
      httpStatus: record.http_status,
      pageTitle: record.page_title,
      hasBodyContent: record.has_body_content,
      errorMessage: record.error_message,
      screenshotPath: record.screenshot_path,
      screenshotUrl: getScreenshotUrl(record.screenshot_path),
      timestamp: record.started_at,
      limitationNote: record.limitation_note,
      isRealTest: true,
      totalIterations: record.total_iterations,
      steps: record.action_trace,
      provider: record.provider,
      model: record.model,
    },
  };
}

export default function App() {
  // ── Navigation ────────────────────────────────────────────────────────
  const [activePage, setActivePage] = useState('overview');

  // ── Real test runs loaded from SQLite database ────────────────────────
  const [realDbRuns, setRealDbRuns] = useState([]);
  const [reportsSummary, setReportsSummary] = useState(null);
  const [isLoadingHistory, setIsLoadingHistory] = useState(true);

  async function loadHistory() {
    setIsLoadingHistory(true);
    try {
      const data = await fetchTestRuns({ limit: 50 });
      if (data && data.items) {
        const mapped = data.items.map(mapDbRecordToRun);
        setRealDbRuns(mapped);
      }
      const summary = await fetchReportsSummary();
      setReportsSummary(summary);
    } catch (err) {
      console.warn('Failed to load history from database:', err);
    } finally {
      setIsLoadingHistory(false);
    }
  }

  useEffect(() => {
    loadHistory();
  }, []);

  // Combined: real runs from SQLite first, followed by baseline demo runs
  const testRuns = [...realDbRuns, ...demoTestRuns];

  // ── Search ────────────────────────────────────────────────────────────
  const [searchQuery, setSearchQuery] = useState('');

  // ── Failure evidence panel ────────────────────────────────────────────
  // Stores { evidence, run } or null
  const [selectedEvidence, setSelectedEvidence] = useState(null);

  // ── Theme ─────────────────────────────────────────────────────────────
  const [theme, setTheme] = useState('light');

  // ── Ref to scroll to the New Test form ────────────────────────────────
  const newTestRef = useRef(null);

  // ── Handlers ──────────────────────────────────────────────────────────

  function handleNavigate(page) {
    setActivePage(page);
    setSearchQuery('');
    setSelectedEvidence(null);
  }

  function handleNewTest() {
    if (activePage !== 'overview') {
      setActivePage('overview');
      setTimeout(() => {
        newTestRef.current?.scrollIntoView({ behavior: 'smooth', block: 'start' });
      }, 100);
    } else {
      newTestRef.current?.scrollIntoView({ behavior: 'smooth', block: 'start' });
    }
  }

  function handleNewRun() {
    // Automatically re-query database to keep all tabs & components in sync
    loadHistory();
  }

  function handleViewEvidence(run) {
    // If this run has real backend details and evidence, display the genuine data
    if (run.details) {
      setSelectedEvidence({
        evidence: {
          runId: run.details.runId,
          errorSummary: run.details.errorMessage || `Assertion check failed on ${run.targetUrl || run.target}`,
          failingStep: run.details.errorMessage ? 'Navigation & Response Verification' : 'DOM Content Assertion',
          expected: 'HTTP 200 with non-empty rendered body content',
          actual: run.details.errorMessage || `HTTP Status: ${run.details.httpStatus ?? 'None'}, Body content: ${run.details.hasBodyContent ? 'Valid' : 'Empty'}`,
          targetUrl: run.targetUrl || ('https://' + run.target),
          timestamp: run.date,
          screenshotFile: run.details.screenshotPath || 'run_screenshot.png',
          screenshotUrl: run.details.screenshotUrl,
          logFile: `playwright-${run.id}.log`,
          isRealTest: true,
          pageTitle: run.details.pageTitle,
          limitationNote: run.details.limitationNote,
          steps: run.details.steps,
        },
        run,
      });
    } else {
      // Legacy demo run clicked
      setSelectedEvidence({ evidence: demoFailureEvidence, run });
    }
    // Scroll to bottom on small screens
    setTimeout(() => {
      window.scrollTo({ top: document.body.scrollHeight, behavior: 'smooth' });
    }, 100);
  }

  function handleCloseEvidence() {
    setSelectedEvidence(null);
  }

  function handleSelectScenario(scenario) {
    // Navigate to overview and pre-fill form
    setActivePage('overview');
    // After navigation, the Overview will render NewTestForm
    // We pass the instruction as state below via a simple approach
    setPendingScenario(scenario);
  }

  const [pendingScenario, setPendingScenario] = useState(null);

  // Clear pending scenario once it's been consumed by the form
  function handleClearPending() {
    setPendingScenario(null);
  }

  // ── Render ────────────────────────────────────────────────────────────
  return (
    <div className={`min-h-screen ${theme === 'dark' ? 'bg-gray-900' : 'bg-gray-50'}`}>
      {/* Fixed sidebar */}
      <Sidebar activePage={activePage} onNavigate={handleNavigate} />

      {/* Main area: offset left by sidebar width */}
      <div className="ml-56 flex flex-col min-h-screen">
        {/* Sticky topbar */}
        <Topbar
          searchQuery={searchQuery}
          onSearchChange={setSearchQuery}
          onNewTest={handleNewTest}
          theme={theme}
          onToggleTheme={() => setTheme(t => t === 'light' ? 'dark' : 'light')}
        />

        {/* Scrollable page content */}
        <main className="flex-1 p-6">
          {activePage === 'overview' && (
            <Overview
              testRuns={testRuns}
              realDbRuns={realDbRuns}
              reportsSummary={reportsSummary}
              onRefreshHistory={loadHistory}
              onNewRun={handleNewRun}
              onViewEvidence={handleViewEvidence}
              selectedEvidence={selectedEvidence}
              onCloseEvidence={handleCloseEvidence}
              onNavigate={handleNavigate}
              newTestRef={newTestRef}
              pendingScenario={pendingScenario}
              onClearPending={handleClearPending}
            />
          )}
          {activePage === 'testruns' && (
            <TestRuns
              testRuns={testRuns}
              realDbRuns={realDbRuns}
              searchQuery={searchQuery}
              onViewEvidence={handleViewEvidence}
              selectedEvidence={selectedEvidence}
              onCloseEvidence={handleCloseEvidence}
            />
          )}
          {activePage === 'scenarios' && (
            <Scenarios
              searchQuery={searchQuery}
              onSelectScenario={handleSelectScenario}
            />
          )}
          {activePage === 'reports' && (
            <Reports
              searchQuery={searchQuery}
              reportsSummary={reportsSummary}
              onRefreshHistory={loadHistory}
            />
          )}
          {activePage === 'settings' && (
            <Settings
              theme={theme}
              onToggleTheme={() => setTheme(t => t === 'light' ? 'dark' : 'light')}
            />
          )}
        </main>
      </div>
    </div>
  );
}
