import React from 'react';

export interface CardProps extends React.HTMLAttributes<HTMLDivElement> {
  variant?: 'default' | 'glow' | 'interactive';
}

export const Card: React.FC<CardProps> = ({
  children,
  variant = 'default',
  className = '',
  ...props
}) => {
  const baseStyles = 'bg-slate-900/80 backdrop-blur-md border border-slate-800 rounded-xl p-5 text-slate-100 transition-all duration-200';

  const variantStyles = {
    default: 'shadow-lg shadow-black/20',
    glow: 'shadow-xl shadow-indigo-950/30 border-indigo-900/40',
    interactive: 'hover:border-slate-700 hover:shadow-xl cursor-pointer hover:-translate-y-0.5',
  }[variant];

  return (
    <div className={`${baseStyles} ${variantStyles} ${className}`} {...props}>
      {children}
    </div>
  );
};
