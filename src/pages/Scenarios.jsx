/**
 * Scenarios.jsx  — Saved scenario library
 *
 * Shows all saved test scenario templates.
 * Clicking "Use scenario" pre-fills the New Test form via onSelectScenario.
 *
 * Props:
 *   searchQuery       — global search string
 *   onSelectScenario  — called with a scenario object (navigates to New Test form)
 */

import { useState } from 'react';
import { BookOpen, Play, Tag } from 'lucide-react';
import StatusBadge from '../components/StatusBadge';
import { demoScenarios } from '../data/demoData';

export default function Scenarios({ searchQuery, onSelectScenario }) {
  const [localSearch, setLocalSearch] = useState('');

  const q = (searchQuery || localSearch).toLowerCase();
  const visible = demoScenarios.filter(sc =>
    !q ||
    sc.name.toLowerCase().includes(q) ||
    sc.description.toLowerCase().includes(q) ||
    sc.tags.some(t => t.includes(q))
  );

  return (
    <div className="space-y-5">
      {/* ── Header ──────────────────────────────────────────── */}
      <div>
        <h1 className="text-xl font-bold text-gray-900">Scenarios</h1>
        <p className="text-sm text-gray-500 mt-0.5">
          Saved test scenario templates. Select one to pre-fill the test form.{' '}
          <span className="text-amber-600 font-medium">[Demo Data]</span>
        </p>
      </div>

      {/* ── Cards grid ──────────────────────────────────────── */}
      {visible.length === 0 ? (
        <div className="bg-white rounded-2xl border border-gray-100 shadow-sm flex flex-col items-center justify-center py-16 text-center">
          <BookOpen size={24} className="text-gray-300 mb-2" />
          <p className="text-sm text-gray-500 font-medium">No scenarios match your search.</p>
        </div>
      ) : (
        <div className="grid grid-cols-1 md:grid-cols-2 xl:grid-cols-3 gap-4">
          {visible.map(sc => (
            <div
              key={sc.id}
              className="bg-white rounded-2xl border border-gray-100 shadow-sm p-5 flex flex-col gap-3 hover:border-indigo-100 hover:shadow-md transition-all"
            >
              {/* Name + status */}
              <div className="flex items-start justify-between gap-2">
                <p className="text-sm font-semibold text-gray-900 leading-snug">{sc.name}</p>
                <StatusBadge status={sc.status} />
              </div>

              {/* Description */}
              <p className="text-xs text-gray-500 leading-relaxed">{sc.description}</p>

              {/* Instruction preview */}
              <div className="bg-gray-50 rounded-lg border border-gray-100 px-3 py-2">
                <p className="text-[11px] text-gray-400 font-semibold mb-1">Instruction</p>
                <p className="text-xs text-gray-700 italic">"{sc.instruction}"</p>
              </div>

              {/* Tags */}
              <div className="flex flex-wrap gap-1.5">
                {sc.tags.map(tag => (
                  <span key={tag} className="inline-flex items-center gap-1 text-[10px] font-medium bg-indigo-50 text-indigo-600 px-2 py-0.5 rounded-full">
                    <Tag size={8} />
                    {tag}
                  </span>
                ))}
              </div>

              {/* Footer */}
              <div className="flex items-center justify-between pt-1 border-t border-gray-100">
                <p className="text-[11px] text-gray-400">Last run: {sc.lastRun}</p>
                <button
                  onClick={() => onSelectScenario?.(sc)}
                  className="flex items-center gap-1 text-xs text-indigo-600 hover:text-indigo-800 font-semibold transition-colors cursor-pointer"
                >
                  <Play size={11} />
                  Use scenario
                </button>
              </div>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}
