/**
 * TestRunsTable.jsx
 *
 * Renders a table of test run records.
 *
 * Props:
 *   runs          — array of run objects (from demoData or state)
 *   onViewEvidence— called with a run object when "View evidence" is clicked
 *   compact       — if true, shows only the first 4 rows (for Overview page)
 */

import { ExternalLink, Eye, MoreHorizontal } from 'lucide-react';
import { useState } from 'react';
import StatusBadge from './StatusBadge';

export default function TestRunsTable({ runs = [], onViewEvidence, compact = false }) {
  const [openMenu, setOpenMenu] = useState(null);

  // On the Overview page we cap at 4 rows
  const visible = compact ? runs.slice(0, 4) : runs;

  if (visible.length === 0) {
    return (
      <div className="flex flex-col items-center justify-center py-16 text-center">
        <div className="w-12 h-12 rounded-full bg-gray-100 flex items-center justify-center mb-3">
          <Eye size={20} className="text-gray-400" />
        </div>
        <p className="text-sm font-medium text-gray-600">No test runs yet</p>
        <p className="text-xs text-gray-400 mt-1">Run your first test to see results here.</p>
      </div>
    );
  }

  return (
    <div className="overflow-x-auto">
      <table className="w-full text-sm">
        <thead>
          <tr className="border-b border-gray-100">
            <th className="text-left py-3 px-4 text-xs font-semibold text-gray-400 uppercase tracking-wide w-8">#</th>
            <th className="text-left py-3 px-4 text-xs font-semibold text-gray-400 uppercase tracking-wide">Test Scenario</th>
            <th className="text-left py-3 px-4 text-xs font-semibold text-gray-400 uppercase tracking-wide">Target Website</th>
            <th className="text-left py-3 px-4 text-xs font-semibold text-gray-400 uppercase tracking-wide">Status</th>
            <th className="text-left py-3 px-4 text-xs font-semibold text-gray-400 uppercase tracking-wide">Duration</th>
            <th className="text-left py-3 px-4 text-xs font-semibold text-gray-400 uppercase tracking-wide">Date</th>
            <th className="py-3 px-4 w-10" />
          </tr>
        </thead>
        <tbody>
          {visible.map((run, idx) => (
            <tr
              key={run.id}
              className="border-b border-gray-50 hover:bg-gray-50 transition-colors group"
            >
              {/* Row number */}
              <td className="py-3 px-4 text-gray-400 text-xs">{idx + 1}</td>

              {/* Scenario */}
              <td className="py-3 px-4">
                <span className="font-medium text-gray-800">{run.scenario}</span>
                {run.isRealTest ? (
                  <span className="ml-2 text-[10px] text-emerald-700 font-semibold bg-emerald-50 border border-emerald-200 px-1.5 py-0.5 rounded">
                    Live Real
                  </span>
                ) : (
                  <span className="ml-2 text-[10px] text-gray-400 font-medium bg-gray-100 px-1.5 py-0.5 rounded">
                    Demo
                  </span>
                )}
                {run.mode && (
                  <span className="ml-1 text-[10px] text-indigo-600 font-medium bg-indigo-50 px-1.5 py-0.5 rounded">
                    {run.mode}
                  </span>
                )}
              </td>

              {/* Target */}
              <td className="py-3 px-4">
                <span className="flex items-center gap-1 text-gray-500">
                  <ExternalLink size={11} className="text-gray-300" />
                  {run.target}
                </span>
              </td>

              {/* Status */}
              <td className="py-3 px-4">
                <StatusBadge status={run.status} />
              </td>

              {/* Duration */}
              <td className="py-3 px-4 text-gray-500 tabular-nums">{run.duration}</td>

              {/* Date */}
              <td className="py-3 px-4 text-gray-400 text-xs whitespace-nowrap">{run.date}</td>

              {/* Actions */}
              <td className="py-3 px-4 relative">
                <div className="flex items-center gap-1">
                  {/* Show evidence button for failed runs or any run with real screenshot */}
                  {(run.status === 'Failed' || run.details?.screenshotUrl) && onViewEvidence && (
                    <button
                      onClick={() => onViewEvidence(run)}
                      className={`hidden group-hover:flex items-center gap-1 text-xs px-2 py-1 rounded-md transition-colors cursor-pointer ${
                        run.status === 'Failed'
                          ? 'text-red-600 hover:text-red-700 bg-red-50 hover:bg-red-100'
                          : 'text-indigo-600 hover:text-indigo-700 bg-indigo-50 hover:bg-indigo-100'
                      }`}
                    >
                      <Eye size={11} />
                      Evidence
                    </button>
                  )}
                  {/* Kebab menu */}
                  <button
                    onClick={() => setOpenMenu(openMenu === run.id ? null : run.id)}
                    className="w-7 h-7 rounded-lg flex items-center justify-center text-gray-300 hover:text-gray-600 hover:bg-gray-100 transition-colors cursor-pointer"
                  >
                    <MoreHorizontal size={15} />
                  </button>
                  {/* Dropdown */}
                  {openMenu === run.id && (
                    <div
                      className="absolute right-0 top-full mt-1 w-36 bg-white rounded-xl shadow-lg border border-gray-100 z-50 py-1"
                      onMouseLeave={() => setOpenMenu(null)}
                    >
                      <button
                        onClick={() => { onViewEvidence?.(run); setOpenMenu(null); }}
                        className="w-full text-left px-3 py-2 text-xs text-gray-700 hover:bg-gray-50 transition-colors cursor-pointer"
                      >
                        View details
                      </button>
                      <button className="w-full text-left px-3 py-2 text-xs text-gray-700 hover:bg-gray-50 transition-colors cursor-pointer">
                        Download log
                      </button>
                      <button className="w-full text-left px-3 py-2 text-xs text-red-500 hover:bg-red-50 transition-colors cursor-pointer">
                        Delete
                      </button>
                    </div>
                  )}
                </div>
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}
