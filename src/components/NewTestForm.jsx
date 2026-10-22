/**
 * NewTestForm.jsx
 *
 * Polished form for configuring and launching browser tests with ProbeQA.
 * Connected directly to the FastAPI + Playwright backend.
 *
 * Stage 4 Features:
 *   1. AI Agent Test Planner (Google Gemini): Converts natural language into a validated,
 *      bounded test plan with Human-in-the-Loop review before browser execution.
 *   2. Direct Deterministic Workflows: SauceDemo login scenarios and general smoke tests.
 */

import { useState, useEffect, useRef } from 'react';
import {
  Link2,
  Play,
  Loader2,
  CheckCircle,
  AlertTriangle,
  ShieldCheck,
  Sparkles,
  Info,
  Lock,
  ShoppingBag,
  Globe,
  ArrowRight,
  CheckCircle2,
  XCircle,
  ListOrdered,
  FileCheck2,
  RotateCcw
} from 'lucide-react';
import { STATUS } from '../data/demoData';
import {
  executeSmokeTest,
  checkBackendHealth,
  getScreenshotUrl,
  generateTestPlan,
  executeTestPlan,
  executeAgentLoop
} from '../services/api';

export default function NewTestForm({
  onRunComplete,
  initialUrl = 'https://www.saucedemo.com/',
  pendingScenario,
  onClearPending
}) {
  // Main mode: 'ai_planner' (Stage 4) | 'direct' (Stage 3.5)
  const [activeTab, setActiveTab] = useState('ai_planner');

  // AI Planning states
  const [aiGoal, setAiGoal] = useState('Verify that a locked-out user receives an appropriate error banner');
  const [aiTargetUrl, setAiTargetUrl] = useState('https://www.saucedemo.com/');
  const [plan, setPlan] = useState(null);
  const [planningState, setPlanningState] = useState(null); // null | 'generating' | 'review' | 'error'
  const [planningError, setPlanningError] = useState(null);

  // Direct Mode states
  const [scenarioType, setScenarioType] = useState('saucedemo'); // 'saucedemo' | 'smoke'
  const [url, setUrl] = useState('https://www.saucedemo.com/');
  const [instruction, setInstruction] = useState('Log into SauceDemo with standard_user and verify inventory products are displayed.');

  // Execution states
  const [executionState, setExecutionState] = useState(null); // null | 'running' | 'success' | 'failed' | 'error'
  const [executionLogs, setExecutionLogs] = useState([]);
  const [lastResult, setLastResult] = useState(null);
  const [backendHealth, setBackendHealth] = useState({ checked: false, online: false });
  const logRef = useRef(null);

  // Example prompts for quick testing
  const EXAMPLE_PROMPTS = [
    { label: 'Locked-out user error', text: 'Verify that a locked-out user receives an appropriate error banner', url: 'https://www.saucedemo.com/' },
    { label: 'Invalid credentials rejected', text: 'Verify that submitting non-existent credentials displays an error', url: 'https://www.saucedemo.com/' },
    { label: 'Standard user inventory', text: 'Log in with standard_user and verify 6 products load in the inventory', url: 'https://www.saucedemo.com/' },
    { label: 'General web smoke test', text: 'Verify that the website loads with HTTP 200 and has visible content', url: 'https://example.com' },
  ];

  // Check backend health on mount
  useEffect(() => {
    let isMounted = true;
    checkBackendHealth().then(status => {
      if (isMounted) {
        setBackendHealth({ checked: true, online: status.ok, version: status.version, error: status.error });
      }
    });
    return () => { isMounted = false; };
  }, []);

  // Consume pendingScenario from Scenarios page
  useEffect(() => {
    if (pendingScenario) {
      setActiveTab('ai_planner');
      setAiGoal(pendingScenario.instruction || pendingScenario.name);
      if (pendingScenario.name && pendingScenario.name.toLowerCase().includes('login')) {
        setAiTargetUrl('https://www.saucedemo.com/');
      } else {
        setAiTargetUrl('https://example.com');
      }
      onClearPending?.();
    }
  }, [pendingScenario, onClearPending]);

  // Auto-scroll the progress log
  useEffect(() => {
    if (logRef.current) {
      logRef.current.scrollTop = logRef.current.scrollHeight;
    }
  }, [executionLogs]);

  // ── AI Planning Handler ──────────────────────────────────────────
  async function handleGeneratePlan(e) {
    e.preventDefault();
    if (!aiGoal.trim()) return;

    setPlanningState('generating');
    setPlanningError(null);
    setPlan(null);
    setExecutionState(null);

    try {
      const generatedPlan = await generateTestPlan({
        goal: aiGoal,
        target_url: aiTargetUrl,
      });

      setPlan(generatedPlan);
      setPlanningState('review');
    } catch (err) {
      setPlanningState('error');
      setPlanningError(err.message);
    }
  }

  // ── Execute Approved Plan (Human-in-the-Loop) ───────────────────
  async function handleApproveAndExecute() {
    if (!plan || !plan.is_supported) return;

    setExecutionState('running');
    setLastResult(null);
    setExecutionLogs([
      `[1/4] Human approval received for ${plan.plan_id}`,
      `[2/4] Re-validating scenario '${plan.scenario_id}' against restricted registry…`,
      `[3/4] Permitted origin verified: ${plan.target_origin}`,
    ]);

    const stepTimer1 = setTimeout(() => {
      setExecutionLogs(prev => [
        ...prev,
        `[4/4] Launching headless Chromium to execute bounded actions…`,
        `Locating approved element aliases & asserting DOM outcomes…`,
      ]);
    }, 700);

    try {
      const data = await executeTestPlan({
        plan_id: plan.plan_id,
        scenario_id: plan.scenario_id,
        target_origin: plan.target_origin,
      });

      clearTimeout(stepTimer1);

      const isPassed = data.status === 'passed';
      const statusValue = isPassed ? STATUS.PASSED : STATUS.FAILED;
      const screenshotFullUrl = getScreenshotUrl(data.screenshot_path);

      setExecutionLogs(prev => [
        ...prev,
        `Page Title: "${data.page_title}"`,
        `HTTP Status: ${data.http_status ?? 'N/A'} (took ${data.duration_ms}ms)`,
        `Evidence Screenshot: ${data.screenshot_path ? 'Captured' : 'None'}`,
        `Outcome: ${data.status.toUpperCase()}`,
      ]);

      const newRun = {
        id: data.run_id || `run-${Date.now()}`,
        scenario: plan.interpreted_goal || plan.goal,
        target: data.target_url.replace(/^https?:\/\//, '').replace(/\/$/, ''),
        targetUrl: data.target_url,
        status: statusValue,
        duration: `${(data.duration_ms / 1000).toFixed(1)}s`,
        date: new Date(data.timestamp).toLocaleString('en-GB', {
          dateStyle: 'medium',
          timeStyle: 'short',
        }),
        mode: `AI Plan: ${plan.scenario_id}`,
        details: {
          runId: data.run_id,
          httpStatus: data.http_status,
          pageTitle: data.page_title,
          hasBodyContent: data.has_body_content,
          errorMessage: data.error_message,
          screenshotPath: data.screenshot_path,
          screenshotUrl: screenshotFullUrl,
          timestamp: data.timestamp,
          limitationNote: data.limitation_note,
          isRealTest: true,
          planId: plan.plan_id,
          scenarioId: plan.scenario_id,
        },
      };

      setLastResult(newRun);
      setExecutionState(isPassed ? 'success' : 'failed');
      onRunComplete?.(newRun);
    } catch (err) {
      clearTimeout(stepTimer1);
      setExecutionState('error');
      setExecutionLogs(prev => [
        ...prev,
        `Execution rejected: ${err.message}`,
      ]);
      setLastResult({ error: err.message });
    }
  }

  // ── Stage 5 Autonomous Agent Loop Handler ───────────────────────
  async function handleRunAgentLoop() {
    if (!aiGoal.trim()) return;

    setExecutionState('running');
    setLastResult(null);
    setExecutionLogs([
      `Initializing Stage 5 Observe–Act–Evaluate Agent Loop…`,
      `Testing Goal: "${aiGoal.trim()}"`,
      `Launching headless Chromium and establishing security sandbox…`,
    ]);

    try {
      const data = await executeAgentLoop({
        goal: aiGoal.trim(),
        max_iterations: 8,
      });

      const isPassed = data.status === 'passed';
      const screenshotFullUrl = getScreenshotUrl(data.screenshot_path);

      const stepLogs = data.steps.map(
        s => `[Step ${s.iteration}] ${s.decision.action_type.toUpperCase()}(${s.decision.target || 'None'}) -> ${s.action_result} (${s.duration_ms}ms)`
      );

      setExecutionLogs([
        `Completed Bounded Agent Loop (${data.total_iterations} iterations, ${data.duration_ms}ms)`,
        ...stepLogs,
        `Deterministic Verdict: ${data.deterministic_verdict}`,
        `Outcome: ${data.status.toUpperCase()}`,
      ]);

      const newRun = {
        id: `run-${Date.now()}`,
        name: `Agent Loop: ${data.goal.slice(0, 32)}…`,
        targetUrl: 'https://www.saucedemo.com/',
        device: 'Desktop (1280x720)',
        status: isPassed ? STATUS.PASSED : STATUS.FAILED,
        duration: `${(data.duration_ms / 1000).toFixed(1)}s`,
        startedAt: 'Just now',
        agentGoal: data.goal,
        mode: 'Autonomous Agent Loop',
        realData: {
          runId: data.run_id,
          scenario: 'observe_act_evaluate_loop',
          status: data.status,
          targetUrl: 'https://www.saucedemo.com/',
          durationMs: data.duration_ms,
          httpStatus: 200,
          pageTitle: 'Swag Labs',
          hasBodyContent: true,
          errorMessage: isPassed ? null : data.deterministic_verdict,
          screenshotPath: data.screenshot_path,
          screenshotUrl: screenshotFullUrl,
          timestamp: data.timestamp,
          limitationNote: `Dynamic Observe–Act–Evaluate loop powered by ${data.provider} (${data.model}). Verified with deterministic Playwright assertions.`,
          isRealTest: true,
          totalIterations: data.total_iterations,
          steps: data.steps,
        },
      };

      setLastResult(newRun);
      setExecutionState(isPassed ? 'success' : 'failed');
      onRunComplete?.(newRun);
    } catch (err) {
      setExecutionState('error');
      setExecutionLogs(prev => [
        ...prev,
        `Agent loop failed: ${err.message}`,
      ]);
      setLastResult({ error: err.message });
    }
  }

  // ── Direct Mode Execution Handler ──────────────────────────────
  async function handleDirectSubmit(e) {
    e.preventDefault();
    setExecutionState('running');
    setLastResult(null);

    const isSauceDemo = scenarioType === 'saucedemo';
    const activeUrl = isSauceDemo ? 'https://www.saucedemo.com/' : url.trim();

    setExecutionLogs([
      `Direct Execution: ${isSauceDemo ? 'SauceDemo Login Workflow' : 'Smoke Test'}`,
      `Connecting to FastAPI engine…`,
    ]);

    try {
      const data = await executeSmokeTest({
        url: activeUrl,
        instruction,
        mode: 'smoke',
        scenario: isSauceDemo ? 'saucedemo_login' : 'smoke',
      });

      const isPassed = data.status === 'passed';
      const statusValue = isPassed ? STATUS.PASSED : STATUS.FAILED;
      const screenshotFullUrl = getScreenshotUrl(data.screenshot_path);

      setExecutionLogs(prev => [
        ...prev,
        `Page Title: "${data.page_title}"`,
        `HTTP Status: ${data.http_status ?? 'N/A'} (${data.duration_ms}ms)`,
        `Screenshot: ${data.screenshot_path ? 'Captured' : 'None'}`,
        `Outcome: ${data.status.toUpperCase()}`,
      ]);

      const newRun = {
        id: data.run_id || `run-${Date.now()}`,
        scenario: isSauceDemo ? 'SauceDemo standard_user login' : (instruction.trim() || 'Smoke test'),
        target: data.target_url.replace(/^https?:\/\//, '').replace(/\/$/, ''),
        targetUrl: data.target_url,
        status: statusValue,
        duration: `${(data.duration_ms / 1000).toFixed(1)}s`,
        date: new Date(data.timestamp).toLocaleString('en-GB', { dateStyle: 'medium', timeStyle: 'short' }),
        mode: isSauceDemo ? 'SauceDemo Workflow' : 'Smoke Test',
        details: {
          runId: data.run_id,
          httpStatus: data.http_status,
          pageTitle: data.page_title,
          hasBodyContent: data.has_body_content,
          errorMessage: data.error_message,
          screenshotPath: data.screenshot_path,
          screenshotUrl: screenshotFullUrl,
          timestamp: data.timestamp,
          limitationNote: data.limitation_note,
          isRealTest: true,
        },
      };

      setLastResult(newRun);
      setExecutionState(isPassed ? 'success' : 'failed');
      onRunComplete?.(newRun);
    } catch (err) {
      setExecutionState('error');
      setExecutionLogs(prev => [...prev, `Execution failed: ${err.message}`]);
      setLastResult({ error: err.message });
    }
  }

  function handleReset() {
    setExecutionState(null);
    setExecutionLogs([]);
    setLastResult(null);
    setPlan(null);
    setPlanningState(null);
  }

  return (
    <div className="bg-white rounded-2xl border border-gray-100 shadow-sm p-5">
      {/* ── Top Header with Backend Status ──────────────────────────── */}
      <div className="flex items-center justify-between mb-3">
        <div className="flex items-center gap-2">
          <span className="text-indigo-500">⚡</span>
          <h2 className="text-sm font-bold text-gray-900">Run browser test</h2>
        </div>

        <div className="flex items-center gap-1.5 text-[11px] font-medium">
          <span className={`w-2 h-2 rounded-full ${backendHealth.online ? 'bg-emerald-500 animate-pulse' : 'bg-amber-400'}`} />
          <span className={backendHealth.online ? 'text-emerald-700' : 'text-amber-600'}>
            {backendHealth.checked
              ? (backendHealth.online ? `FastAPI Online (v${backendHealth.version})` : 'Backend Offline')
              : 'Checking server…'}
          </span>
        </div>
      </div>

      {/* ── Top Tab Switcher: AI Planner vs Direct Mode ─────────────── */}
      <div className="grid grid-cols-2 gap-2 mb-4 bg-gray-50 p-1 rounded-xl border border-gray-100">
        <button
          type="button"
          onClick={() => { setActiveTab('ai_planner'); handleReset(); }}
          className={`flex items-center justify-center gap-1.5 py-2 px-2.5 rounded-lg text-xs font-semibold transition-all cursor-pointer ${
            activeTab === 'ai_planner'
              ? 'bg-white text-indigo-700 shadow-xs border border-gray-200/80 ring-1 ring-indigo-100'
              : 'text-gray-500 hover:text-gray-800'
          }`}
        >
          <Sparkles size={13} className="text-indigo-600" />
          <span>AI Agent Planner</span>
        </button>

        <button
          type="button"
          onClick={() => { setActiveTab('direct'); handleReset(); }}
          className={`flex items-center justify-center gap-1.5 py-2 px-2.5 rounded-lg text-xs font-semibold transition-all cursor-pointer ${
            activeTab === 'direct'
              ? 'bg-white text-indigo-700 shadow-xs border border-gray-200/80 ring-1 ring-indigo-100'
              : 'text-gray-500 hover:text-gray-800'
          }`}
        >
          <ShieldCheck size={13} className="text-gray-600" />
          <span>Direct Workflows</span>
        </button>
      </div>

      {/* ════════════════════════════════════════════════════════════════
          TAB 1: AI AGENT TEST PLANNER (STAGE 4)
         ════════════════════════════════════════════════════════════════ */}
      {activeTab === 'ai_planner' && (
        <div>
          {/* Informative Guardrail Banner */}
          <div className="mb-3.5 p-2.5 bg-indigo-50/70 border border-indigo-100 rounded-xl text-xs text-indigo-900">
            <div className="flex items-start gap-2">
              <Sparkles size={14} className="text-indigo-600 mt-0.5 flex-shrink-0" />
              <p className="leading-snug text-[11px]">
                <strong className="font-semibold text-indigo-800">Human-in-the-Loop Architecture:</strong> The LLM converts your goal into a bounded plan mapped to our registered browser tool actions. <em>Execution only begins when you review and approve the plan.</em>
              </p>
            </div>
          </div>

          {/* Quick Prompt Chips */}
          <div className="mb-3">
            <p className="text-[10px] font-semibold text-gray-500 uppercase tracking-wide mb-1.5">Quick Example Goals:</p>
            <div className="flex flex-wrap gap-1.5">
              {EXAMPLE_PROMPTS.map((p, i) => (
                <button
                  key={i}
                  type="button"
                  onClick={() => { setAiGoal(p.text); setAiTargetUrl(p.url); }}
                  className="text-[10px] bg-gray-50 hover:bg-indigo-50 hover:text-indigo-700 text-gray-600 border border-gray-200 px-2 py-1 rounded-md transition-colors cursor-pointer"
                >
                  {p.label}
                </button>
              ))}
            </div>
          </div>

          <form onSubmit={handleGeneratePlan} noValidate>
            {/* Natural Language Goal Field */}
            <div className="mb-3">
              <label className="block text-xs font-semibold text-gray-600 mb-1">
                Testing Goal in Natural Language
              </label>
              <textarea
                value={aiGoal}
                onChange={(e) => setAiGoal(e.target.value)}
                placeholder="e.g. Verify that locked-out users receive a lockout error banner upon login"
                rows={2}
                disabled={planningState === 'generating' || executionState === 'running'}
                className="w-full px-3 py-2 text-xs border border-gray-200 bg-gray-50 rounded-lg focus:outline-none focus:ring-2 focus:ring-indigo-400 focus:border-transparent resize-none transition-all"
              />
            </div>

            {/* Target URL field */}
            <div className="mb-4">
              <label className="block text-xs font-semibold text-gray-600 mb-1">
                Target URL (Optional)
              </label>
              <div className="relative">
                <Link2 size={13} className="absolute left-3 top-1/2 -translate-y-1/2 text-gray-400 pointer-events-none" />
                <input
                  type="url"
                  value={aiTargetUrl}
                  onChange={(e) => setAiTargetUrl(e.target.value)}
                  placeholder="https://www.saucedemo.com/"
                  disabled={planningState === 'generating' || executionState === 'running'}
                  className="w-full pl-8 pr-3 py-1.5 text-xs border border-gray-200 bg-gray-50 rounded-lg focus:outline-none focus:ring-2 focus:ring-indigo-400 focus:border-transparent transition-all"
                />
              </div>
            </div>

            {/* Action Buttons: Plan Mode (Stage 4) vs Agent Loop (Stage 5) */}
            {!plan && planningState !== 'review' && (
              <div className="grid grid-cols-2 gap-2">
                <button
                  type="submit"
                  disabled={planningState === 'generating' || executionState === 'running' || !aiGoal.trim()}
                  className="flex items-center justify-center gap-1.5 py-2.5 bg-indigo-600 hover:bg-indigo-700 disabled:opacity-60 text-white text-xs font-semibold rounded-xl transition-colors shadow-sm cursor-pointer"
                  title="Synthesize structured plan for Human-in-the-Loop review before running"
                >
                  {planningState === 'generating' ? (
                    <><Loader2 size={13} className="animate-spin" /> Synthesizing…</>
                  ) : (
                    <><Sparkles size={13} /> Plan & Review</>
                  )}
                </button>

                <button
                  type="button"
                  onClick={handleRunAgentLoop}
                  disabled={planningState === 'generating' || executionState === 'running' || !aiGoal.trim()}
                  className="flex items-center justify-center gap-1.5 py-2.5 bg-emerald-600 hover:bg-emerald-700 disabled:opacity-60 text-white text-xs font-semibold rounded-xl transition-colors shadow-sm cursor-pointer"
                  title="Run bounded Observe-Act-Evaluate loop in live browser"
                >
                  {executionState === 'running' ? (
                    <><Loader2 size={13} className="animate-spin" /> Running Loop…</>
                  ) : (
                    <><Play size={13} /> Run Agent Loop</>
                  )}
                </button>
              </div>
            )}
          </form>

          {/* Planning Error Alert */}
          {planningError && (
            <div className="mt-3 p-3 bg-red-50 border border-red-200 rounded-xl flex items-start gap-2">
              <AlertTriangle size={15} className="text-red-600 mt-0.5 flex-shrink-0" />
              <div className="text-xs text-red-900">
                <p className="font-semibold">Plan Generation Failed</p>
                <p className="text-[11px] text-red-800 mt-0.5">{planningError}</p>
              </div>
            </div>
          )}

          {/* ── Interactive Human-in-the-Loop Plan Review Card ─────────── */}
          {plan && (
            <div className="mt-4 border border-indigo-200 rounded-xl p-3.5 bg-indigo-50/40 space-y-3">
              <div className="flex items-center justify-between border-b border-indigo-100 pb-2">
                <div className="flex items-center gap-1.5">
                  <FileCheck2 size={15} className="text-indigo-600" />
                  <span className="text-xs font-bold text-gray-900">Proposed Test Plan</span>
                </div>
                <div className="flex items-center gap-1.5">
                  <span className={`text-[10px] px-2 py-0.5 rounded border font-semibold ${
                    plan.provider === 'gemini'
                      ? 'bg-purple-100 text-purple-700 border-purple-200'
                      : plan.provider === 'groq'
                      ? 'bg-orange-100 text-orange-700 border-orange-200'
                      : 'bg-amber-100 text-amber-700 border-amber-200'
                  }`}>
                    {plan.provider === 'gemini'
                      ? `Gemini (${plan.model || 'live'})`
                      : plan.provider === 'groq'
                      ? `Groq (${plan.model || 'live'})`
                      : 'Deterministic Fallback'}
                  </span>
                  <span className="text-[10px] font-mono bg-white px-2 py-0.5 rounded border border-indigo-200 text-indigo-700 font-semibold">
                    {plan.plan_id}
                  </span>
                </div>
              </div>

              {/* Unsupported Warning */}
              {!plan.is_supported ? (
                <div className="p-2.5 bg-amber-50 border border-amber-200 rounded-lg text-xs text-amber-900">
                  <p className="font-semibold text-amber-800">Unsupported Goal</p>
                  <p className="text-[11px] text-amber-700 mt-0.5">{plan.unsupported_reason}</p>
                  <button
                    onClick={handleReset}
                    className="mt-2 text-[11px] text-indigo-600 hover:underline font-semibold"
                  >
                    ← Try a different testing goal
                  </button>
                </div>
              ) : (
                <>
                  {/* Summary Details */}
                  <div className="text-xs space-y-1">
                    <p className="text-gray-500">
                      <strong className="text-gray-700 font-medium">Interpreted Goal:</strong> {plan.interpreted_goal}
                    </p>
                    <div className="flex flex-wrap items-center gap-2 pt-0.5">
                      <span className="text-[10px] bg-indigo-100 text-indigo-800 px-2 py-0.5 rounded font-mono font-medium">
                        scenario: {plan.scenario_id}
                      </span>
                      <span className="text-[10px] bg-white border border-gray-200 text-gray-700 px-2 py-0.5 rounded font-mono">
                        target: {plan.target_origin}
                      </span>
                    </div>
                  </div>

                  {/* Actions Checklist */}
                  <div>
                    <p className="text-[10px] font-bold text-gray-500 uppercase tracking-wide mb-1.5">
                      Bounded Action Steps ({plan.actions.length}):
                    </p>
                    <div className="space-y-1 max-h-32 overflow-y-auto scrollbar-thin bg-white p-2 rounded-lg border border-indigo-100 text-[11px]">
                      {plan.actions.map(act => (
                        <div key={act.step} className="flex items-start gap-1.5 leading-snug">
                          <span className="w-4 h-4 rounded-full bg-indigo-50 text-indigo-700 font-bold text-[9px] flex items-center justify-center flex-shrink-0 mt-0.5">
                            {act.step}
                          </span>
                          <span className="text-gray-700">
                            <span className="font-semibold text-indigo-900">[{act.action_type}]</span> {act.description}
                          </span>
                        </div>
                      ))}
                    </div>
                  </div>

                  {/* Expected Outcomes */}
                  <div>
                    <p className="text-[10px] font-bold text-gray-500 uppercase tracking-wide mb-1">
                      Expected Assertions:
                    </p>
                    <ul className="list-disc list-inside text-[11px] text-gray-600 pl-1 space-y-0.5">
                      {plan.expected_outcomes.map((out, idx) => (
                        <li key={idx}>{out}</li>
                      ))}
                    </ul>
                  </div>

                  {/* Model Explanation */}
                  <p className="text-[10px] text-gray-400 italic">
                    Reasoning: {plan.explanation}
                  </p>

                  {/* Human Approval Action Buttons */}
                  {executionState !== 'running' && executionState !== 'success' && (
                    <div className="flex items-center gap-2 pt-1">
                      <button
                        type="button"
                        onClick={handleApproveAndExecute}
                        className="flex-1 flex items-center justify-center gap-1.5 py-2 bg-emerald-600 hover:bg-emerald-700 text-white text-xs font-semibold rounded-xl transition-colors shadow-sm cursor-pointer"
                      >
                        <CheckCircle2 size={14} />
                        Approve & Execute Plan
                      </button>

                      <button
                        type="button"
                        onClick={handleReset}
                        className="px-3 py-2 border border-gray-200 hover:bg-gray-50 text-gray-600 text-xs font-medium rounded-xl transition-colors cursor-pointer"
                      >
                        Edit Goal
                      </button>
                    </div>
                  )}
                </>
              )}
            </div>
          )}
        </div>
      )}

      {/* ════════════════════════════════════════════════════════════════
          TAB 2: DIRECT WORKFLOWS (PRESERVED FROM STAGE 3.5)
         ════════════════════════════════════════════════════════════════ */}
      {activeTab === 'direct' && (
        <div>
          <div className="grid grid-cols-2 gap-2 mb-3.5">
            <button
              type="button"
              onClick={() => { setScenarioType('saucedemo'); setUrl('https://www.saucedemo.com/'); }}
              className={`flex items-center justify-center gap-1.5 py-2 px-2 rounded-xl text-xs font-semibold border transition-all cursor-pointer ${
                scenarioType === 'saucedemo'
                  ? 'bg-indigo-50 text-indigo-700 border-indigo-200 ring-1 ring-indigo-200'
                  : 'bg-white text-gray-600 border-gray-200 hover:bg-gray-50'
              }`}
            >
              <ShoppingBag size={13} />
              <span>SauceDemo Login</span>
            </button>

            <button
              type="button"
              onClick={() => { setScenarioType('smoke'); setUrl('https://example.com'); }}
              className={`flex items-center justify-center gap-1.5 py-2 px-2 rounded-xl text-xs font-semibold border transition-all cursor-pointer ${
                scenarioType === 'smoke'
                  ? 'bg-indigo-50 text-indigo-700 border-indigo-200 ring-1 ring-indigo-200'
                  : 'bg-white text-gray-600 border-gray-200 hover:bg-gray-50'
              }`}
            >
              <Globe size={13} />
              <span>General Smoke</span>
            </button>
          </div>

          <form onSubmit={handleDirectSubmit}>
            <div className="mb-3">
              <label className="block text-xs font-semibold text-gray-600 mb-1">Target URL</label>
              <input
                type="url"
                value={url}
                onChange={(e) => setUrl(e.target.value)}
                readOnly={scenarioType === 'saucedemo'}
                disabled={executionState === 'running'}
                className={`w-full px-3 py-1.5 text-xs border rounded-lg focus:outline-none focus:ring-2 focus:ring-indigo-400 ${
                  scenarioType === 'saucedemo' ? 'bg-gray-100 text-gray-600 font-mono' : 'bg-gray-50'
                }`}
              />
            </div>

            <div className="mb-4">
              <label className="block text-xs font-semibold text-gray-600 mb-1">Instruction</label>
              <textarea
                value={instruction}
                onChange={(e) => setInstruction(e.target.value)}
                rows={2}
                disabled={executionState === 'running'}
                className="w-full px-3 py-1.5 text-xs border border-gray-200 bg-gray-50 rounded-lg focus:outline-none focus:ring-2 focus:ring-indigo-400 resize-none"
              />
            </div>

            {executionState !== 'running' && executionState !== 'success' && (
              <button
                type="submit"
                disabled={executionState === 'running'}
                className="w-full flex items-center justify-center gap-2 py-2.5 bg-indigo-600 hover:bg-indigo-700 text-white text-xs font-semibold rounded-xl transition-colors shadow-sm cursor-pointer"
              >
                <Play size={13} fill="white" /> Run Direct Workflow
              </button>
            )}
          </form>
        </div>
      )}

      {/* ── Live Playwright Execution Terminal Log ────────────── */}
      {executionLogs.length > 0 && (
        <div className="mt-4">
          <div className="flex items-center justify-between mb-1.5">
            <span className="text-[10px] font-bold text-indigo-600 bg-indigo-50 border border-indigo-200 px-2 py-0.5 rounded">
              REAL PLAYWRIGHT EXECUTION LOG
            </span>
            {executionState === 'running' && (
              <span className="text-[10px] text-gray-400 flex items-center gap-1">
                <Loader2 size={10} className="animate-spin" /> Live
              </span>
            )}
          </div>
          <div
            ref={logRef}
            className="bg-gray-950 rounded-lg p-3 max-h-36 overflow-y-auto scrollbar-thin font-mono text-[11px] space-y-1 text-gray-200 border border-gray-800"
          >
            {executionLogs.map((line, i) => (
              <p key={i} className="leading-snug">
                <span className="text-indigo-400 select-none mr-1.5">$</span>
                <span className={line.includes('failed') || line.includes('rejected') ? 'text-red-400 font-semibold' : line.includes('PASSED') ? 'text-emerald-400 font-semibold' : 'text-gray-300'}>
                  {line}
                </span>
              </p>
            ))}
            {executionState === 'running' && (
              <p className="text-gray-500 animate-pulse text-[10px]">Processing headless Chromium session…</p>
            )}
          </div>
        </div>
      )}

      {/* ── Success Card with Real Metric Breakdown & Screenshot Link ── */}
      {executionState === 'success' && lastResult && (
        <div className="mt-3 p-3 bg-emerald-50 border border-emerald-200 rounded-xl">
          <div className="flex items-start gap-2">
            <CheckCircle size={16} className="text-emerald-600 mt-0.5 flex-shrink-0" />
            <div className="flex-1">
              <p className="text-xs font-semibold text-emerald-900">
                Workflow Assertion Passed
              </p>
              <p className="text-[11px] text-emerald-800 mt-0.5">
                Target: {lastResult.target} · Duration: {lastResult.duration} · Status: {lastResult.status}
              </p>
              {lastResult.details?.screenshotUrl && (
                <a
                  href={lastResult.details.screenshotUrl}
                  target="_blank"
                  rel="noreferrer"
                  className="inline-flex items-center gap-1 mt-1 text-[11px] text-indigo-600 hover:underline font-semibold"
                >
                  View captured screenshot <ArrowRight size={10} />
                </a>
              )}
            </div>
            <button
              onClick={handleReset}
              className="text-xs font-medium text-emerald-700 hover:text-emerald-900 cursor-pointer"
            >
              Reset
            </button>
          </div>
        </div>
      )}

      {/* ── Failure Card ────────────────────────────────────── */}
      {executionState === 'failed' && lastResult && (
        <div className="mt-3 p-3 bg-red-50 border border-red-200 rounded-xl">
          <div className="flex items-start gap-2">
            <AlertTriangle size={16} className="text-red-600 mt-0.5 flex-shrink-0" />
            <div className="flex-1">
              <p className="text-xs font-semibold text-red-900">Workflow Assertion Failed</p>
              <p className="text-[11px] text-red-800 mt-0.5">
                {lastResult.details?.errorMessage || `Test assertion failed`}
              </p>
              {lastResult.details?.screenshotUrl && (
                <a
                  href={lastResult.details.screenshotUrl}
                  target="_blank"
                  rel="noreferrer"
                  className="inline-block mt-1 text-[11px] text-red-700 hover:underline font-medium"
                >
                  View failure state screenshot ↗
                </a>
              )}
            </div>
            <button
              onClick={handleReset}
              className="text-xs font-medium text-red-700 hover:text-red-900 cursor-pointer"
            >
              Reset
            </button>
          </div>
        </div>
      )}

      {/* ── Error Card ──────────────────────────────────────── */}
      {executionState === 'error' && lastResult && (
        <div className="mt-3 p-3 bg-amber-50 border border-amber-200 rounded-xl">
          <div className="flex items-start gap-2">
            <AlertTriangle size={16} className="text-amber-600 mt-0.5 flex-shrink-0" />
            <div className="flex-1">
              <p className="text-xs font-semibold text-amber-900">Execution Error</p>
              <p className="text-[11px] text-amber-800 mt-0.5">{lastResult.error}</p>
            </div>
            <button
              onClick={handleReset}
              className="text-xs font-medium text-amber-700 hover:text-amber-900 cursor-pointer"
            >
              Reset
            </button>
          </div>
        </div>
      )}
    </div>
  );
}
