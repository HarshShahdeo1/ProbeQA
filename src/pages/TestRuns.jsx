/**
 * TestRuns.jsx  — Full searchable/filterable test run history page
 *
 * Props:
 *   testRuns        — array of run objects
 *   searchQuery     — current global search string (from Topbar)
 *   onViewEvidence  — called to show evidence for a failed run
 *   selectedEvidence— {evidence, run} or null
 *   onCloseEvidence — clears the selected evidence
 */

import { useState } from 'react';
import { Filter, ChevronDown } from 'lucide-react';
import TestRunsTable  from '../components/TestRunsTable';
import FailureEvidence from '../components/FailureEvidence';
import { STATUS }     from '../data/demoData';

const ALL_STATUSES = ['All', STATUS.PASSED, STATUS.FAILED, STATUS.RUNNING, STATUS.PENDING];

export default function TestRuns({ testRuns, realDbRuns = [], searchQuery, onViewEvidence, selectedEvidence, onCloseEvidence }) {
  const [statusFilter, setStatusFilter] = useState('All');
  const [scopeFilter,  setScopeFilter]  = useState('All'); // 'All', 'Real', 'Demo'

  // Apply search + status + scope filters
  const q = searchQuery.toLowerCase();
  const filtered = testRuns.filter(r => {
    const matchSearch = !q || r.scenario.toLowerCase().includes(q) || r.target.toLowerCase().includes(q);
    const matchStatus = statusFilter === 'All' || r.status === statusFilter;
    const matchScope =
      scopeFilter === 'All' ||
      (scopeFilter === 'Real' && r.isRealTest) ||
      (scopeFilter === 'Demo' && !r.isRealTest);
    return matchSearch && matchStatus && matchScope;
  });

  const realCount = realDbRuns.length;

  return (
    <div className="space-y-5">

      {/* ── Header ──────────────────────────────────────────── */}
      <div className="flex items-start justify-between">
        <div>
          <h1 className="text-xl font-bold text-gray-900">Test Runs</h1>
          <p className="text-sm text-gray-500 mt-0.5">
            Full history of test executions.
            {realCount > 0 ? (
              <span className="ml-1.5 text-emerald-700 font-semibold bg-emerald-50 px-2 py-0.5 rounded text-xs border border-emerald-200">
                {realCount} Real Runs in SQLite
              </span>
            ) : (
              <span className="ml-1.5 text-amber-600 font-medium">[Demo Baseline]</span>
            )}
          </p>
        </div>
      </div>

      {/* ── Filters ─────────────────────────────────────────── */}
      <div className="flex flex-wrap items-center gap-3">
        <div className="flex items-center gap-1.5 text-xs text-gray-500 font-medium">
          <Filter size={13} />
          Filter:
        </div>

        {/* Scope filter (Real vs Demo) */}
        <div className="relative">
          <select
            value={scopeFilter}
            onChange={e => setScopeFilter(e.target.value)}
            className="appearance-none bg-white border border-gray-200 rounded-lg pl-3 pr-7 py-1.5 text-xs font-semibold text-gray-800 focus:outline-none focus:ring-2 focus:ring-indigo-400 cursor-pointer"
          >
            <option value="All">All Records (Real + Demo)</option>
            <option value="Real">Real SQLite Runs Only</option>
            <option value="Demo">Demo Baseline Only</option>
          </select>
          <ChevronDown size={12} className="absolute right-2 top-1/2 -translate-y-1/2 text-gray-400 pointer-events-none" />
        </div>

        {/* Status filter */}
        <div className="relative">
          <select
            value={statusFilter}
            onChange={e => setStatusFilter(e.target.value)}
            className="appearance-none bg-white border border-gray-200 rounded-lg pl-3 pr-7 py-1.5 text-xs font-medium text-gray-700 focus:outline-none focus:ring-2 focus:ring-indigo-400 cursor-pointer"
          >
            {ALL_STATUSES.map(s => <option key={s}>{s}</option>)}
          </select>
          <ChevronDown size={12} className="absolute right-2 top-1/2 -translate-y-1/2 text-gray-400 pointer-events-none" />
        </div>

        <span className="text-xs text-gray-400 ml-auto font-medium">
          {filtered.length} result{filtered.length !== 1 ? 's' : ''}
        </span>
      </div>

      {/* ── Table ───────────────────────────────────────────── */}
      <div className="bg-white rounded-2xl border border-gray-100 shadow-sm overflow-hidden">
        <TestRunsTable
          runs={filtered}
          onViewEvidence={onViewEvidence}
          compact={false}
        />
      </div>

      {/* ── Evidence panel ──────────────────────────────────── */}
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
