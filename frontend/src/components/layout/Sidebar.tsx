import React from 'react';
import {
  AlertOctagon,
  BarChart3,
  BookOpen,
  Compass,
  FileSearch,
  FileSpreadsheet,
  GraduationCap,
  LayoutDashboard,
  Settings,
  UploadCloud,
} from 'lucide-react';
import { ViewId } from '../../types';

interface NavItem {
  id: ViewId;
  label: string;
  icon: React.ReactNode;
}

export const NAV_ITEMS: NavItem[] = [
  { id: 'landing', label: 'Overview', icon: <Compass className="w-4 h-4" /> },
  { id: 'dashboard', label: 'Dashboard', icon: <LayoutDashboard className="w-4 h-4" /> },
  { id: 'library', label: 'Lecture Library', icon: <BookOpen className="w-4 h-4" /> },
  { id: 'upload', label: 'Ingest Lecture', icon: <UploadCloud className="w-4 h-4" /> },
  { id: 'analysis', label: 'Timeline & Topics', icon: <BarChart3 className="w-4 h-4" /> },
  { id: 'evidence', label: 'Signal Evidence', icon: <FileSearch className="w-4 h-4" /> },
  { id: 'misconceptions', label: 'Misconceptions', icon: <AlertOctagon className="w-4 h-4" /> },
  { id: 'student', label: 'Student Catch-Up', icon: <GraduationCap className="w-4 h-4" /> },
  { id: 'reports', label: 'Pedagogy Reports', icon: <FileSpreadsheet className="w-4 h-4" /> },
  { id: 'settings', label: 'System Settings', icon: <Settings className="w-4 h-4" /> },
];

interface SidebarProps {
  currentView: ViewId;
  onNavigate: (view: ViewId) => void;
}

export const Sidebar: React.FC<SidebarProps> = ({ currentView, onNavigate }) => {
  return (
    <aside className="hidden md:flex flex-col w-64 border-r border-slate-800/80 bg-navy-950/60 p-4 shrink-0">
      <div className="text-[11px] font-semibold text-slate-400 uppercase tracking-wider px-3 mb-2">
        Platform Views (10 Routes)
      </div>

      <nav className="space-y-1">
        {NAV_ITEMS.map((item) => {
          const isActive = currentView === item.id;
          return (
            <button
              key={item.id}
              onClick={() => onNavigate(item.id)}
              className={`w-full flex items-center gap-3 px-3 py-2 rounded-xl text-sm font-medium transition-all ${
                isActive
                  ? 'bg-indigo-600/20 text-indigo-300 border border-indigo-500/30 shadow-sm'
                  : 'text-slate-400 hover:text-slate-200 hover:bg-slate-900/60'
              }`}
            >
              <span className={isActive ? 'text-indigo-400' : 'text-slate-500'}>{item.icon}</span>
              <span>{item.label}</span>
            </button>
          );
        })}
      </nav>

      <div className="mt-auto pt-4 border-t border-slate-800/80 text-[11px] text-slate-400 px-3">
        ClassSense v0.1.0 &bull; Monorepo Scaffold
      </div>
    </aside>
  );
};
