import React from 'react';
import { SeverityLevel } from '../../types';

export interface BadgeProps extends React.HTMLAttributes<HTMLSpanElement> {
  variant?: 'default' | 'indigo' | 'success' | 'warning' | 'error' | SeverityLevel;
  size?: 'sm' | 'md';
}

export const Badge: React.FC<BadgeProps> = ({
  children,
  variant = 'default',
  size = 'md',
  className = '',
  ...props
}) => {
  const sizeStyles = {
    sm: 'text-xs px-2 py-0.5',
    md: 'text-xs px-2.5 py-1',
  }[size];

  const variantStyles = {
    default: 'bg-slate-800 text-slate-300 border border-slate-700',
    indigo: 'bg-indigo-950/60 text-indigo-300 border border-indigo-800/60',
    // Severity Palette
    low: 'bg-emerald-950/60 text-emerald-400 border border-emerald-800/60',
    medium: 'bg-cyan-950/60 text-cyan-400 border border-cyan-800/60',
    high: 'bg-amber-950/60 text-amber-400 border border-amber-800/60',
    critical: 'bg-rose-950/60 text-rose-400 border border-rose-800/60',
    // Aliases
    success: 'bg-emerald-950/60 text-emerald-400 border border-emerald-800/60',
    warning: 'bg-amber-950/60 text-amber-400 border border-amber-800/60',
    error: 'bg-rose-950/60 text-rose-400 border border-rose-800/60',
  }[variant];

  return (
    <span
      className={`inline-flex items-center font-medium rounded-full ${sizeStyles} ${variantStyles} ${className}`}
      {...props}
    >
      {children}
    </span>
  );
};
