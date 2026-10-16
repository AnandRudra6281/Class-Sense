import React from 'react';
import { BrainCircuit, Menu, Sparkles, Terminal } from 'lucide-react';
import { ViewId } from '../../types';
import { Badge } from '../ui/Badge';

interface HeaderProps {
  currentView: ViewId;
  demoMode: boolean;
  onToggleDemoMode: () => void;
  onToggleMobileDrawer: () => void;
}

export const Header: React.FC<HeaderProps> = ({
  currentView,
  demoMode,
  onToggleDemoMode,
  onToggleMobileDrawer,
}) => {
  return (
    <header className="sticky top-0 z-30 w-full border-b border-slate-800/80 bg-navy-950/80 backdrop-blur-md">
      <div className="px-4 sm:px-6 lg:px-8 h-16 flex items-center justify-between">
        <div className="flex items-center gap-3">
          <button
            onClick={onToggleMobileDrawer}
            className="md:hidden p-2 rounded-lg text-slate-400 hover:text-slate-200 hover:bg-slate-800/60"
            aria-label="Open mobile navigation"
          >
            <Menu className="w-5 h-5" />
          </button>

          <div className="flex items-center gap-2.5">
            <div className="w-9 h-9 rounded-xl bg-gradient-to-tr from-indigo-600 to-indigo-400 flex items-center justify-center shadow-lg shadow-indigo-500/20">
              <BrainCircuit className="w-5 h-5 text-white" />
            </div>
            <div>
              <div className="flex items-center gap-2">
                <span className="text-base font-bold tracking-tight text-white">ClassSense</span>
                <Badge variant="indigo" size="sm">Phase 0</Badge>
              </div>
            </div>
          </div>
        </div>

        <div className="flex items-center gap-3">
          <div className="hidden sm:flex items-center gap-2 px-2.5 py-1 rounded-md bg-slate-900 border border-slate-800 text-xs">
            <span className="text-slate-400">Route:</span>
            <span className="font-mono text-indigo-400 font-medium">/{currentView}</span>
          </div>

          <button
            onClick={onToggleDemoMode}
            className={`flex items-center gap-1.5 px-3 py-1.5 rounded-lg text-xs font-medium border transition-colors ${
              demoMode
                ? 'bg-amber-950/40 border-amber-600/50 text-amber-300'
                : 'bg-slate-900 border-slate-800 text-slate-400 hover:text-slate-200'
            }`}
          >
            <Sparkles className="w-3.5 h-3.5" />
            <span>Demo: {demoMode ? 'ON' : 'OFF'}</span>
          </button>

          <div className="hidden lg:flex items-center gap-1.5 text-xs text-slate-400 border-l border-slate-800 pl-3">
            <Terminal className="w-3.5 h-3.5 text-indigo-400" />
            <span>API v1</span>
          </div>
        </div>
      </div>
    </header>
  );
};
