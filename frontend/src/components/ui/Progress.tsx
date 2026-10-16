import React from 'react';
import { SeverityLevel } from '../../types';

export interface ProgressProps {
  value: number; // 0 to 100
  max?: number;
  label?: string;
  showPercent?: boolean;
  severity?: SeverityLevel;
  className?: string;
}

export const Progress: React.FC<ProgressProps> = ({
  value,
  max = 100,
  label,
  showPercent = true,
  severity,
  className = '',
}) => {
  const percentage = Math.max(0, Math.min(100, Math.round((value / max) * 100)));

  const severityBarStyles = {
    low: 'bg-emerald-500',
    medium: 'bg-cyan-500',
    high: 'bg-amber-500',
    critical: 'bg-rose-500',
  };

  const barColor = severity
    ? severityBarStyles[severity]
    : 'bg-gradient-to-r from-indigo-500 via-indigo-400 to-emerald-400';

  return (
    <div className={`w-full ${className}`}>
      {(label || showPercent) && (
        <div className="flex justify-between items-center mb-1.5 text-xs font-medium text-slate-300">
          <span>{label}</span>
          {showPercent && <span className="tabular-nums">{percentage}%</span>}
        </div>
      )}
      <div className="w-full h-2 bg-slate-800 rounded-full overflow-hidden p-0.5 border border-slate-700/50">
        <div
          className={`h-full rounded-full transition-all duration-300 ease-out ${barColor}`}
          style={{ width: `${percentage}%` }}
        />
      </div>
    </div>
  );
};
