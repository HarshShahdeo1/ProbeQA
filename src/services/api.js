/**
 * api.js
 *
 * Central API service module for communicating with the ProbeQA FastAPI backend.
 *
 * Why this exists:
 * - Decouples components from HTTP fetch details and URLs.
 * - Centralizes error parsing, timeouts, and response transformations.
 * - Reads environment variables via Vite's `import.meta.env`.
 */

const API_BASE_URL = import.meta.env.VITE_API_BASE_URL || 'http://127.0.0.1:8000';

/**
 * Checks whether the backend FastAPI server is online.
 * @returns {Promise<{ ok: boolean, version?: string, error?: string }>}
 */
export async function checkBackendHealth() {
  try {
    const res = await fetch(`${API_BASE_URL}/health`, {
      method: 'GET',
      headers: { 'Accept': 'application/json' },
    });
    if (!res.ok) {
      return { ok: false, error: `HTTP ${res.status}: ${res.statusText}` };
    }
    const data = await res.json();
    return { ok: true, version: data.version };
  } catch (err) {
    return { ok: false, error: err.message || 'Cannot connect to backend server' };
  }
}

/**
 * Runs a real Playwright test scenario on the backend.
 *
 * @param {Object} params
 * @param {string} params.url - Target URL to test
 * @param {string} [params.instruction] - Optional test instruction
 * @param {string} [params.mode] - Test mode ('smoke' | 'ai-assisted')
 * @param {string} [params.scenario] - Scenario identifier ('smoke' | 'saucedemo_login')
 * @returns {Promise<Object>} Real test execution results from Playwright
 */
export async function executeSmokeTest({ url, instruction = '', mode = 'smoke', scenario = 'smoke' }) {
  const controller = new AbortController();
  // 30-second client-side timeout in case network or backend hangs
  const timeoutId = setTimeout(() => controller.abort(), 30000);

  try {
    const response = await fetch(`${API_BASE_URL}/api/tests/run`, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
        'Accept': 'application/json',
      },
      body: JSON.stringify({
        url: url.trim(),
        instruction: instruction.trim(),
        mode,
        scenario,
      }),
      signal: controller.signal,
    });

    clearTimeout(timeoutId);

    // If backend returned 400 Bad Request (e.g. SSRF block) or 422 Unprocessable Entity
    if (!response.ok) {
      let errorDetail = `Server returned HTTP ${response.status}`;
      try {
        const errorJson = await response.json();
        if (errorJson.detail) {
          errorDetail = Array.isArray(errorJson.detail)
            ? errorJson.detail.map(d => d.msg || JSON.stringify(d)).join(', ')
            : errorJson.detail;
        }
      } catch {
        // If not JSON, use default errorDetail
      }
      throw new Error(errorDetail);
    }

    const data = await response.json();
    return data;
  } catch (err) {
    clearTimeout(timeoutId);
    if (err.name === 'AbortError') {
      throw new Error('Test execution timed out after 30 seconds.');
    }
    if (err.message && err.message.includes('Failed to fetch')) {
      throw new Error(
        `Unable to reach backend at ${API_BASE_URL}. Ensure the FastAPI server is running with 'uvicorn main:app --port 8000'.`
      );
    }
    throw err;
  }
}

/**
 * Generates an AI-synthesized TestPlan from a natural language testing goal.
 * @param {Object} params
 * @param {string} params.goal - User's natural language goal
 * @param {string} [params.target_url] - Optional target URL
 * @returns {Promise<Object>} Structured TestPlan conforming to Pydantic schema
 */
export async function generateTestPlan({ goal, target_url }) {
  try {
    const response = await fetch(`${API_BASE_URL}/api/agent/plan`, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
        'Accept': 'application/json',
      },
      body: JSON.stringify({
        goal: goal.trim(),
        target_url: target_url ? target_url.trim() : null,
      }),
    });

    if (!response.ok) {
      let detail = `Planning service returned HTTP ${response.status}`;
      try {
        const errJson = await response.json();
        if (errJson.detail) detail = errJson.detail;
      } catch {}
      throw new Error(detail);
    }

    return await response.json();
  } catch (err) {
    if (err.message && err.message.includes('Failed to fetch')) {
      throw new Error(`Cannot reach backend planner at ${API_BASE_URL}. Ensure Uvicorn is active.`);
    }
    throw err;
  }
}

/**
 * Executes a human-approved TestPlan through the restricted scenario runner.
 * @param {Object} params
 * @param {string} params.plan_id - Approved plan ID
 * @param {string} params.scenario_id - Registered scenario ID
 * @param {string} params.target_origin - Permitted target origin
 * @returns {Promise<Object>} Real execution results from Playwright
 */
export async function executeTestPlan({ plan_id, scenario_id, target_origin }) {
  try {
    const response = await fetch(`${API_BASE_URL}/api/agent/execute`, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
        'Accept': 'application/json',
      },
      body: JSON.stringify({
        plan_id,
        scenario_id,
        target_origin,
      }),
    });

    if (!response.ok) {
      let detail = `Execution engine returned HTTP ${response.status}`;
      try {
        const errJson = await response.json();
        if (errJson.detail) detail = errJson.detail;
      } catch {}
      throw new Error(detail);
    }

    return await response.json();
  } catch (err) {
    if (err.message && err.message.includes('Failed to fetch')) {
      throw new Error(`Cannot reach execution backend at ${API_BASE_URL}.`);
    }
    throw err;
  }
}

/**
 * Runs the live Stage 5 Observe-Act-Evaluate Agent Loop on the backend.
 * @param {Object} params
 * @param {string} params.goal - Testing goal
 * @param {number} [params.max_iterations] - Safety limit (default: 8)
 * @returns {Promise<Object>} Full step-by-step agent execution result
 */
export async function executeAgentLoop({ goal, max_iterations = 8 }) {
  try {
    const response = await fetch(`${API_BASE_URL}/api/agent/loop/run`, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
        'Accept': 'application/json',
      },
      body: JSON.stringify({
        goal: goal.trim(),
        max_iterations,
      }),
    });

    if (!response.ok) {
      let detail = `Agent loop returned HTTP ${response.status}`;
      try {
        const errJson = await response.json();
        if (errJson.detail) detail = errJson.detail;
      } catch {}
      throw new Error(detail);
    }

    return await response.json();
  } catch (err) {
    if (err.message && err.message.includes('Failed to fetch')) {
      throw new Error(`Cannot reach agent backend at ${API_BASE_URL}. Ensure Uvicorn is active.`);
    }
    throw err;
  }
}

/**
 * Constructs a full URL for an evidence screenshot.
 * @param {string} screenshotPath - e.g. "evidence/run_abc123.png"
 * @returns {string|null} Full HTTP URL
 */
export function getScreenshotUrl(screenshotPath) {
  if (!screenshotPath) return null;
  // If path already starts with http, return it directly
  if (screenshotPath.startsWith('http://') || screenshotPath.startsWith('https://')) {
    return screenshotPath;
  }
  // Remove leading slash if any
  const cleanPath = screenshotPath.startsWith('/') ? screenshotPath.slice(1) : screenshotPath;
  return `${API_BASE_URL}/${cleanPath}`;
}

/**
 * Fetches paginated real test run records from SQLite database.
 * @param {Object} [params]
 * @param {number} [params.limit=50]
 * @param {number} [params.offset=0]
 * @param {string|null} [params.status=null]
 * @returns {Promise<{ items: Array, total: number, limit: number, offset: number }>}
 */
export async function fetchTestRuns({ limit = 50, offset = 0, status = null } = {}) {
  try {
    const params = new URLSearchParams({ limit, offset });
    if (status) params.append('status', status);

    const res = await fetch(`${API_BASE_URL}/api/runs?${params.toString()}`, {
      method: 'GET',
      headers: { 'Accept': 'application/json' },
    });
    if (!res.ok) {
      throw new Error(`HTTP ${res.status}: ${res.statusText}`);
    }
    return await res.json();
  } catch (err) {
    console.warn('Could not fetch runs from database:', err.message);
    return { items: [], total: 0, limit, offset };
  }
}

/**
 * Fetches detailed persistent test run record by its unique run_id.
 * @param {string} runId
 * @returns {Promise<Object>}
 */
export async function fetchRunDetails(runId) {
  const res = await fetch(`${API_BASE_URL}/api/runs/${encodeURIComponent(runId)}`, {
    method: 'GET',
    headers: { 'Accept': 'application/json' },
  });
  if (!res.ok) {
    throw new Error(`Failed to fetch run details for ${runId}: HTTP ${res.status}`);
  }
  return await res.json();
}

/**
 * Fetches real aggregate reporting statistics calculated from SQLite test runs.
 * @returns {Promise<Object>}
 */
export async function fetchReportsSummary() {
  try {
    const res = await fetch(`${API_BASE_URL}/api/reports/summary`, {
      method: 'GET',
      headers: { 'Accept': 'application/json' },
    });
    if (!res.ok) {
      throw new Error(`HTTP ${res.status}: ${res.statusText}`);
    }
    return await res.json();
  } catch (err) {
    console.warn('Could not fetch reports summary from database:', err.message);
    return {
      total_runs: 0,
      passed_runs: 0,
      failed_runs: 0,
      error_runs: 0,
      pass_rate: 0,
      avg_duration_ms: 0,
      scenario_reports: [],
      recent_runs: [],
      is_empty: true,
    };
  }
}
