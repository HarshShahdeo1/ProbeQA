/**
 * Topbar.jsx
 *
 * Top navigation bar displayed above the main content area.
 *
 * Contains:
 *  - Search input (filters are applied per-page via the onSearch prop)
 *  - Light/Dark theme toggle (light mode only for now — clean toggle UI)
 *  - Notification bell
 *  - Profile avatar
 *  - "+ New Test" primary action button
 *
 * Props:
 *   searchQuery    — controlled search string
 *   onSearchChange — called when the search input changes
 *   onNewTest      — called when "+ New Test" is clicked
 *   onNavigate     — called to navigate to a page
 *   theme          — 'light' | 'dark'
 *   onToggleTheme  — called when theme toggle is clicked
 */

import { Search, Sun, Moon, Bell, Plus } from 'lucide-react';

export default function Topbar({
  searchQuery,
  onSearchChange,
  onNewTest,
  theme = 'light',
  onToggleTheme,
}) {
  return (
    <header className="h-14 bg-white border-b border-gray-100 flex items-center gap-3 px-6 sticky top-0 z-30 shadow-sm">

      {/* ── Search ──────────────────────────────────────────────── */}
      <div className="relative flex-1 max-w-sm">
        <Search
          size={15}
          className="absolute left-3 top-1/2 -translate-y-1/2 text-gray-400 pointer-events-none"
        />
        <input
          type="text"
          value={searchQuery}
          onChange={(e) => onSearchChange(e.target.value)}
          placeholder="Search test runs, scenarios, or reports…"
          className="w-full pl-9 pr-3 py-1.5 text-sm bg-gray-50 border border-gray-200 rounded-lg focus:outline-none focus:ring-2 focus:ring-indigo-400 focus:border-transparent placeholder:text-gray-400 transition-all"
        />
      </div>

      {/* ── Right controls ──────────────────────────────────────── */}
      <div className="flex items-center gap-2 ml-auto">

        {/* Theme toggle */}
        <button
          onClick={onToggleTheme}
          title={theme === 'light' ? 'Switch to dark mode' : 'Switch to light mode'}
          className="w-8 h-8 rounded-lg flex items-center justify-center text-gray-400 hover:bg-gray-100 hover:text-gray-700 transition-colors cursor-pointer"
        >
          {theme === 'light' ? <Moon size={16} /> : <Sun size={16} />}
        </button>

        {/* Notifications */}
        <button
          title="Notifications"
          className="relative w-8 h-8 rounded-lg flex items-center justify-center text-gray-400 hover:bg-gray-100 hover:text-gray-700 transition-colors cursor-pointer"
        >
          <Bell size={16} />
          {/* Unread dot */}
          <span className="absolute top-1.5 right-1.5 w-1.5 h-1.5 bg-indigo-500 rounded-full" />
        </button>

        {/* Avatar */}
        <button
          title="Profile"
          className="w-8 h-8 rounded-full bg-indigo-600 flex items-center justify-center text-white text-xs font-bold hover:opacity-90 transition-opacity cursor-pointer"
        >
          HS
        </button>

        {/* New Test CTA */}
        <button
          onClick={onNewTest}
          className="flex items-center gap-1.5 px-4 py-1.5 bg-indigo-600 hover:bg-indigo-700 text-white text-sm font-semibold rounded-lg transition-colors shadow-sm cursor-pointer"
        >
          <Plus size={15} />
          New Test
        </button>
      </div>
    </header>
  );
}
