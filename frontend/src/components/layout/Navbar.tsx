import React from 'react';
import { BrainCircuit, Sparkles, Terminal } from 'lucide-react';
import { Badge } from '../ui/Badge';

interface NavbarProps {
  demoMode: boolean;
  onToggleDemoMode: () => void;
}

export const Navbar: React.FC<NavbarProps> = ({ demoMode, onToggleDemoMode }) => {
  return (
    <header className="sticky top-0 z-40 w-full border-b border-slate-800/80 bg-navy-950/80 backdrop-blur-md">
      <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 h-16 flex items-center justify-between">
        <div className="flex items-center gap-3">
          <div className="w-10 h-10 rounded-xl bg-gradient-to-tr from-indigo-600 to-indigo-400 flex items-center justify-center shadow-lg shadow-indigo-500/20">
            <BrainCircuit className="w-6 h-6 text-white" />
          </div>
          <div>
            <div className="flex items-center gap-2">
              <span className="text-lg font-bold tracking-tight text-white">ClassSense</span>
              <Badge variant="indigo" size="sm">Phase 1 Architecture</Badge>
            </div>
            <p className="text-xs text-slate-400">AI Lecture Struggle & Misconception Engine</p>
          </div>
        </div>

        <div className="flex items-center gap-4">
          <button
            onClick={onToggleDemoMode}
            className={`flex items-center gap-2 px-3 py-1.5 rounded-lg text-xs font-medium border transition-colors ${
              demoMode
                ? 'bg-amber-950/40 border-amber-600/50 text-amber-300'
                : 'bg-slate-900 border-slate-800 text-slate-400 hover:text-slate-200'
            }`}
          >
            <Sparkles className="w-3.5 h-3.5" />
            <span>Demo Mode: {demoMode ? 'ON (Mocks)' : 'OFF (Live API)'}</span>
          </button>

          <div className="hidden sm:flex items-center gap-2 text-xs text-slate-400 border-l border-slate-800 pl-4">
            <Terminal className="w-3.5 h-3.5 text-indigo-400" />
            <span>API v1 Ready</span>
          </div>
        </div>
      </div>
    </header>
  );
};
