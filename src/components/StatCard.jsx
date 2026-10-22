/**
 * StatCard.jsx
 *
 * Displays a single metric on the Overview dashboard (e.g. "Total Tests Run").
 *
 * Props:
 *   title    — label shown above the number
 *   value    — the big number / string
 *   delta    — small change indicator string (e.g. "+12% from last week")
 *   icon     — a Lucide icon component
 *   iconBg   — Tailwind class for the icon background circle
 *   iconColor— Tailwind class for the icon stroke color
 *   deltaPos — true = green, false = red, null/undefined = neutral
 *   sparkColor — hex color for the SVG sparkline
 *   sparkPoints— array of y-values [0-1] for the sparkline path
 */

import { TrendingUp, TrendingDown } from 'lucide-react';

export default function StatCard({
  title,
  value,
  delta,
  icon: Icon,
  iconBg,
  iconColor,
  deltaPos,
  sparkColor = '#6366f1',
  sparkPoints = [0.6, 0.4, 0.7, 0.5, 0.8, 0.6, 0.9],
}) {
  // Build a simple SVG polyline from normalized y-values
  const W = 80, H = 32, pad = 4;
  const pts = sparkPoints
    .map((y, i) => {
      const x = pad + (i / (sparkPoints.length - 1)) * (W - pad * 2);
      const yPx = pad + (1 - y) * (H - pad * 2);
      return `${x},${yPx}`;
    })
    .join(' ');

  return (
    <div className="bg-white rounded-2xl border border-gray-100 shadow-sm p-5 flex flex-col gap-3">
      {/* Header row: icon + sparkline */}
      <div className="flex items-start justify-between">
        <div className={`w-10 h-10 rounded-xl flex items-center justify-center ${iconBg}`}>
          <Icon size={18} className={iconColor} />
        </div>
        {/* Sparkline */}
        <svg width={W} height={H} viewBox={`0 0 ${W} ${H}`} className="overflow-visible">
          <polyline
            points={pts}
            fill="none"
            stroke={sparkColor}
            strokeWidth="1.5"
            strokeLinecap="round"
            strokeLinejoin="round"
          />
        </svg>
      </div>

      {/* Title */}
      <p className="text-sm text-gray-500 font-medium">{title}</p>

      {/* Value */}
      <p className="text-2xl font-bold text-gray-900 leading-none">{value}</p>

      {/* Delta */}
      {delta && (
        <p className={`flex items-center gap-1 text-xs font-medium ${
          deltaPos === true  ? 'text-emerald-600' :
          deltaPos === false ? 'text-red-500'     :
          'text-gray-400'
        }`}>
          {deltaPos === true  && <TrendingUp  size={12} />}
          {deltaPos === false && <TrendingDown size={12} />}
          {delta}
        </p>
      )}
    </div>
  );
}
