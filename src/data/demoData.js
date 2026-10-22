/**
 * demoData.js
 *
 * All sample data used throughout the ProbeQA frontend.
 *
 * WHY a separate file?
 *   When you connect a real FastAPI backend later, you replace the functions
 *   in src/services/api.js (which will call your endpoints) and these demo
 *   objects become irrelevant.  Keeping data out of components makes that
 *   swap much easier.
 *
 * NOTE: All data here is demonstration data only.
 *       No real browser tests have been executed.
 */

// ─── Metric card stats shown on the Overview page ────────────────────────────
export const demoStats = {
  totalRuns: 128,
  passRate: 94.2,
  failedTests: 7,
  avgDuration: '1m 24s',
  totalRunsDelta: '+12% from last week',
  passRateDelta: '+2.3% from last week',
  failedTestsDelta: '+1 from last week',
  avgDurationDelta: '-18% from last week',
};

// ─── Possible statuses a test run can have ────────────────────────────────────
export const STATUS = {
  PASSED: 'Passed',
  FAILED: 'Failed',
  RUNNING: 'Running',
  PENDING: 'Pending',
};

// ─── Sample test run records ──────────────────────────────────────────────────
let _nextId = 10; // used when the demo simulation adds a new run
export function nextId() { return _nextId++; }

export const demoTestRuns = [
  {
    id: 1,
    scenario: 'Login rejects invalid password',
    target: 'demo-shop.test',
    status: STATUS.FAILED,
    duration: '27s',
    date: '19 Oct 2026, 3:11 PM',
    mode: 'AI-assisted',
  },
  {
    id: 2,
    scenario: 'Add product to cart',
    target: 'demo-shop.test',
    status: STATUS.PASSED,
    duration: '32s',
    date: '19 Oct 2026, 4:18 PM',
    mode: 'AI-assisted',
  },
  {
    id: 3,
    scenario: 'Login rejects invalid password',
    target: 'demo-shop.test',
    status: STATUS.PASSED,
    duration: '18s',
    date: '19 Oct 2026, 5:42 PM',
    mode: 'Manual',
  },
  {
    id: 4,
    scenario: 'Search for a product',
    target: 'demo-shop.test',
    status: STATUS.PASSED,
    duration: '14s',
    date: '19 Oct 2026, 2:05 PM',
    mode: 'AI-assisted',
  },
  {
    id: 5,
    scenario: 'Checkout without a delivery address',
    target: 'demo-shop.test',
    status: STATUS.FAILED,
    duration: '41s',
    date: '18 Oct 2026, 11:30 AM',
    mode: 'AI-assisted',
  },
  {
    id: 6,
    scenario: 'Password reset flow',
    target: 'demo-shop.test',
    status: STATUS.PASSED,
    duration: '55s',
    date: '18 Oct 2026, 10:15 AM',
    mode: 'AI-assisted',
  },
  {
    id: 7,
    scenario: 'Filter products by category',
    target: 'demo-shop.test',
    status: STATUS.PENDING,
    duration: '—',
    date: '21 Oct 2026, 9:00 AM',
    mode: 'Manual',
  },
  {
    id: 8,
    scenario: 'User profile update',
    target: 'demo-shop.test',
    status: STATUS.RUNNING,
    duration: '—',
    date: '21 Oct 2026, 8:50 AM',
    mode: 'AI-assisted',
  },
];

// ─── Sample failure evidence record (linked to run id 1) ─────────────────────
export const demoFailureEvidence = {
  runId: 1,
  errorSummary: 'Expected validation message was not visible.',
  failingStep: 'Verify error message',
  expected: "Text containing 'Invalid credentials'",
  actual: 'No visible error message found',
  targetUrl: 'https://demo-shop.test/login',
  timestamp: '19 Oct 2026, 3:11 PM',
  screenshotFile: 'failure-step-3.png',
  logFile: 'run-1-agent.log',
};

// ─── Saved scenario library shown on the Scenarios page ──────────────────────
export const demoScenarios = [
  {
    id: 'sc-1',
    name: 'Login rejects invalid password',
    description: 'Verify that submitting wrong credentials shows a validation message.',
    instruction: 'Verify that the login form rejects invalid credentials and displays an appropriate validation message.',
    tags: ['auth', 'validation'],
    lastRun: '19 Oct 2026',
    status: STATUS.FAILED,
  },
  {
    id: 'sc-2',
    name: 'Add product to cart',
    description: 'Open a product page and add the item to the shopping cart.',
    instruction: 'Navigate to a product page and click "Add to cart". Verify the cart badge increments by 1.',
    tags: ['cart', 'e-commerce'],
    lastRun: '19 Oct 2026',
    status: STATUS.PASSED,
  },
  {
    id: 'sc-3',
    name: 'Search for a product',
    description: 'Use the search bar to find a specific product and verify results appear.',
    instruction: 'Type "running shoes" in the search bar and verify at least one result appears with a relevant title.',
    tags: ['search', 'e-commerce'],
    lastRun: '19 Oct 2026',
    status: STATUS.PASSED,
  },
  {
    id: 'sc-4',
    name: 'Checkout without a delivery address',
    description: 'Attempt checkout and confirm an address validation error is shown.',
    instruction: 'Proceed to checkout without filling in a delivery address. Verify an error message prompts for address.',
    tags: ['checkout', 'validation'],
    lastRun: '18 Oct 2026',
    status: STATUS.FAILED,
  },
  {
    id: 'sc-5',
    name: 'Password reset flow',
    description: 'Submit the forgot-password form and verify the confirmation screen.',
    instruction: 'Click "Forgot password", enter a registered email, and verify the "Check your inbox" confirmation is shown.',
    tags: ['auth', 'email'],
    lastRun: '18 Oct 2026',
    status: STATUS.PASSED,
  },
  {
    id: 'sc-6',
    name: 'Filter products by category',
    description: 'Apply a category filter and confirm only matching products are shown.',
    instruction: 'On the products listing page, select "Electronics" from the category filter. Verify all visible products belong to that category.',
    tags: ['filter', 'e-commerce'],
    lastRun: '—',
    status: STATUS.PENDING,
  },
];

// ─── Report summary entries shown on the Reports page ────────────────────────
export const demoReports = [
  {
    id: 'rep-1',
    title: 'Daily Run — 19 Oct 2026',
    total: 4,
    passed: 3,
    failed: 1,
    duration: '1m 31s',
    createdAt: '19 Oct 2026, 6:00 PM',
  },
  {
    id: 'rep-2',
    title: 'Daily Run — 18 Oct 2026',
    total: 3,
    passed: 2,
    failed: 1,
    duration: '2m 16s',
    createdAt: '18 Oct 2026, 12:00 PM',
  },
  {
    id: 'rep-3',
    title: 'Sprint Check — 17 Oct 2026',
    total: 6,
    passed: 6,
    failed: 0,
    duration: '4m 02s',
    createdAt: '17 Oct 2026, 5:00 PM',
  },
];
