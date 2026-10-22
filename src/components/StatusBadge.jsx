/**
 * StatusBadge.jsx
 *
 * A small colored pill that shows the status of a test run.
 * It maps a status string to a color scheme.
 *
 * Props:
 *   status — one of 'Passed' | 'Failed' | 'Running' | 'Pending'
 */

const STATUS_STYLES = {
  Passed:  'bg-emerald-50 text-emerald-700 ring-1 ring-emerald-200',
  Failed:  'bg-red-50 text-red-700 ring-1 ring-red-200',
  Running: 'bg-blue-50 text-blue-700 ring-1 ring-blue-200',
  Pending: 'bg-amber-50 text-amber-700 ring-1 ring-amber-200',
};

const STATUS_DOTS = {
  Passed:  'bg-emerald-500',
  Failed:  'bg-red-500',
  Running: 'bg-blue-500 animate-pulse',
  Pending: 'bg-amber-400',
};

export default function StatusBadge({ status }) {
  const pill = STATUS_STYLES[status] ?? 'bg-gray-100 text-gray-600';
  const dot  = STATUS_DOTS[status]  ?? 'bg-gray-400';

  return (
    <span className={`inline-flex items-center gap-1.5 px-2.5 py-0.5 rounded-full text-xs font-medium ${pill}`}>
      <span className={`w-1.5 h-1.5 rounded-full ${dot}`} />
      {status}
    </span>
  );
}
