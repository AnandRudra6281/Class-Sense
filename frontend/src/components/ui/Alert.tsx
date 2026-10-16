import React from 'react';
import { AlertCircle, AlertTriangle, CheckCircle, Info } from 'lucide-react';
import { SeverityLevel } from '../../types';

export interface AlertProps extends React.HTMLAttributes<HTMLDivElement> {
  severity?: SeverityLevel;
  title?: string;
}

export const Alert: React.FC<AlertProps> = ({
  children,
  severity = 'medium',
  title,
  className = '',
  ...props
}) => {
  const severityStyles = {
    low: {
      container: 'bg-emerald-950/40 border-emerald-800/60 text-emerald-300',
      icon: <CheckCircle className="w-5 h-5 text-emerald-400 shrink-0 mt-0.5" />,
      titleColor: 'text-emerald-200',
    },
    medium: {
      container: 'bg-cyan-950/40 border-cyan-800/60 text-cyan-300',
      icon: <Info className="w-5 h-5 text-cyan-400 shrink-0 mt-0.5" />,
      titleColor: 'text-cyan-200',
    },
    high: {
      container: 'bg-amber-950/40 border-amber-800/60 text-amber-300',
      icon: <AlertTriangle className="w-5 h-5 text-amber-400 shrink-0 mt-0.5" />,
      titleColor: 'text-amber-200',
    },
    critical: {
      container: 'bg-rose-950/40 border-rose-800/60 text-rose-300',
      icon: <AlertCircle className="w-5 h-5 text-rose-400 shrink-0 mt-0.5" />,
      titleColor: 'text-rose-200',
    },
  }[severity];

  return (
    <div
      role="alert"
      className={`flex items-start gap-3 p-4 rounded-xl border text-sm backdrop-blur-sm ${severityStyles.container} ${className}`}
      {...props}
    >
      {severityStyles.icon}
      <div className="space-y-1 flex-1">
        {title && <h5 className={`font-semibold ${severityStyles.titleColor}`}>{title}</h5>}
        <div className="text-slate-300 leading-relaxed text-xs">{children}</div>
      </div>
    </div>
  );
};
