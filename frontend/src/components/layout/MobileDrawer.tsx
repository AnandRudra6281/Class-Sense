import React from 'react';
import { X } from 'lucide-react';
import { ViewId } from '../../types';
import { NAV_ITEMS } from './Sidebar';

interface MobileDrawerProps {
  isOpen: boolean;
  currentView: ViewId;
  onNavigate: (view: ViewId) => void;
  onClose: () => void;
}

export const MobileDrawer: React.FC<MobileDrawerProps> = ({
  isOpen,
  currentView,
  onNavigate,
  onClose,
}) => {
  if (!isOpen) return null;

  return (
    <div
      role="dialog"
      aria-modal="true"
      aria-label="Navigation drawer"
      className="fixed inset-0 z-50 md:hidden flex"
    >
      {/* Backdrop */}
      <div
        className="fixed inset-0 bg-black/70 backdrop-blur-sm transition-opacity"
        onClick={onClose}
        aria-hidden="true"
        data-testid="drawer-backdrop"
      />

      {/* Drawer Panel */}
      <div className="relative w-72 max-w-[80vw] bg-navy-950 border-r border-slate-800 p-5 flex flex-col h-full shadow-2xl z-10">
        <div className="flex items-center justify-between pb-4 border-b border-slate-800">
          <div className="font-bold text-white text-base tracking-tight">Navigation</div>
          <button
            onClick={onClose}
            className="p-1.5 rounded-lg text-slate-400 hover:text-white hover:bg-slate-800"
            aria-label="Close navigation"
          >
            <X className="w-5 h-5" />
          </button>
        </div>

        <div className="text-[11px] font-semibold text-slate-400 uppercase tracking-wider mt-4 mb-2">
          Platform Views (10 Routes)
        </div>

        <nav className="space-y-1 overflow-y-auto flex-1">
          {NAV_ITEMS.map((item) => {
            const isActive = currentView === item.id;
            return (
              <button
                key={item.id}
                onClick={() => {
                  onNavigate(item.id);
                  onClose();
                }}
                className={`w-full flex items-center gap-3 px-3 py-2.5 rounded-xl text-sm font-medium transition-all ${
                  isActive
                    ? 'bg-indigo-600/20 text-indigo-300 border border-indigo-500/30'
                    : 'text-slate-400 hover:text-slate-200 hover:bg-slate-900/60'
                }`}
              >
                <span className={isActive ? 'text-indigo-400' : 'text-slate-500'}>
                  {item.icon}
                </span>
                <span>{item.label}</span>
              </button>
            );
          })}
        </nav>

        <div className="pt-4 border-t border-slate-800 text-[11px] text-slate-400">
          ClassSense &bull; Dark Navy SaaS
        </div>
      </div>
    </div>
  );
};
