import React from 'react';

export interface ProgressBarProps {
  progress: number; // 0 to 100
  label?: string;
  showPercent?: boolean;
  className?: string;
}

export const ProgressBar: React.FC<ProgressBarProps> = ({
  progress,
  label,
  showPercent = true,
  className = '',
}) => {
  const clampedProgress = Math.max(0, Math.min(100, Math.round(progress)));

  return (
    <div className={`w-full ${className}`}>
      {(label || showPercent) && (
        <div className="flex justify-between items-center mb-1.5 text-xs font-medium text-slate-300">
          <span>{label}</span>
          {showPercent && <span className="tabular-nums">{clampedProgress}%</span>}
        </div>
      )}
      <div className="w-full h-2 bg-slate-800 rounded-full overflow-hidden p-0.5 border border-slate-700/50">
        <div
          className="h-full bg-gradient-to-r from-indigo-500 via-indigo-400 to-emerald-400 rounded-full transition-all duration-300 ease-out"
          style={{ width: `${clampedProgress}%` }}
        />
      </div>
    </div>
  );
};
