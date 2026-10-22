/**
 * Sidebar.jsx
 *
 * Fixed left navigation sidebar for ProbeQA.
 *
 * Responsibilities:
 *  - Show the app logo + name.
 *  - Render navigation links (Overview, Test Runs, Scenarios, Reports, Settings).
 *  - Highlight the currently active page.
 *  - Show a "Free Plan" section and a user avatar at the bottom.
 *
 * Props:
 *   activePage  — string: the currently active page key
 *   onNavigate  — function(page): called when a nav item is clicked
 */

import {
  LayoutDashboard,
  PlayCircle,
  BookOpen,
  BarChart2,
  Settings,
  Bot,
  Crown,
  ChevronRight,
} from 'lucide-react';

const NAV_ITEMS = [
  { key: 'overview',   label: 'Overview',   icon: LayoutDashboard },
  { key: 'testruns',   label: 'Test Runs',  icon: PlayCircle },
  { key: 'scenarios',  label: 'Scenarios',  icon: BookOpen },
  { key: 'reports',    label: 'Reports',    icon: BarChart2 },
  { key: 'settings',   label: 'Settings',   icon: Settings },
];

export default function Sidebar({ activePage, onNavigate }) {
  return (
    <aside className="fixed top-0 left-0 h-screen w-56 bg-white border-r border-gray-100 flex flex-col z-40 shadow-sm">

      {/* ── Logo ─────────────────────────────────────────────── */}
      <div className="px-5 py-5 border-b border-gray-100">
        <div className="flex items-center gap-2.5">
          {/* Robot-style logo mark */}
          <div className="w-8 h-8 bg-indigo-600 rounded-lg flex items-center justify-center flex-shrink-0">
            <Bot size={18} className="text-white" />
          </div>
          <div>
            <p className="text-sm font-bold text-gray-900 leading-tight">ProbeQA</p>
            <p className="text-[10px] text-gray-400 leading-tight">AI Web Testing Agent</p>
          </div>
        </div>
      </div>

      {/* ── Navigation ───────────────────────────────────────── */}
      <nav className="flex-1 px-3 py-4 space-y-0.5 overflow-y-auto scrollbar-thin">
        {NAV_ITEMS.map(({ key, label, icon: Icon }) => {
          const isActive = activePage === key;
          return (
            <button
              key={key}
              onClick={() => onNavigate(key)}
              className={`w-full flex items-center gap-3 px-3 py-2.5 rounded-xl text-sm font-medium transition-all duration-150 cursor-pointer
                ${isActive
                  ? 'bg-indigo-50 text-indigo-700'
                  : 'text-gray-500 hover:bg-gray-50 hover:text-gray-800'
                }`}
            >
              <Icon
                size={17}
                className={isActive ? 'text-indigo-600' : 'text-gray-400'}
              />
              {label}
              {/* Active indicator bar */}
              {isActive && (
                <span className="ml-auto w-1.5 h-1.5 rounded-full bg-indigo-600" />
              )}
            </button>
          );
        })}
      </nav>

      {/* ── Promo card ───────────────────────────────────────── */}
      <div className="mx-3 mb-3 p-4 bg-indigo-50 rounded-xl border border-indigo-100">
        <div className="flex items-center gap-1.5 mb-1.5">
          <Crown size={13} className="text-indigo-500" />
          <span className="text-xs font-semibold text-indigo-700">Free Plan</span>
        </div>
        <p className="text-[11px] text-indigo-600 leading-snug">
          Build reliable web experiences with AI. Create, run and debug tests using natural language.
        </p>
      </div>

      {/* ── User row ─────────────────────────────────────────── */}
      <div className="px-3 pb-4 border-t border-gray-100 pt-3">
        <button className="w-full flex items-center gap-2.5 px-2 py-2 rounded-xl hover:bg-gray-50 transition-colors group cursor-pointer">
          <div className="w-8 h-8 rounded-full bg-indigo-600 flex items-center justify-center text-white text-xs font-bold flex-shrink-0">
            HS
          </div>
          <div className="text-left min-w-0">
            <p className="text-xs font-semibold text-gray-800 truncate">Harsh Shahdeo</p>
            <p className="text-[10px] text-gray-400">Free Plan</p>
          </div>
          <ChevronRight size={13} className="ml-auto text-gray-300 group-hover:text-gray-500 transition-colors" />
        </button>
      </div>
    </aside>
  );
}
