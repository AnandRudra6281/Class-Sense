import React, { useState } from 'react';
import { ViewId } from '../../types';
import { Header } from './Header';
import { Sidebar } from './Sidebar';
import { MobileDrawer } from './MobileDrawer';

interface AppLayoutProps {
  currentView: ViewId;
  onNavigate: (view: ViewId) => void;
  demoMode: boolean;
  onToggleDemoMode: () => void;
  children: React.ReactNode;
}

export const AppLayout: React.FC<AppLayoutProps> = ({
  currentView,
  onNavigate,
  demoMode,
  onToggleDemoMode,
  children,
}) => {
  const [mobileDrawerOpen, setMobileDrawerOpen] = useState(false);

  return (
    <div className="min-h-screen bg-navy-950 text-slate-100 flex flex-col font-sans">
      <Header
        currentView={currentView}
        demoMode={demoMode}
        onToggleDemoMode={onToggleDemoMode}
        onToggleMobileDrawer={() => setMobileDrawerOpen(true)}
      />

      <div className="flex-1 flex overflow-hidden">
        <Sidebar currentView={currentView} onNavigate={onNavigate} />

        <MobileDrawer
          isOpen={mobileDrawerOpen}
          currentView={currentView}
          onNavigate={onNavigate}
          onClose={() => setMobileDrawerOpen(false)}
        />

        <main className="flex-1 overflow-y-auto p-4 sm:p-6 lg:p-8 bg-navy-900/30">
          <div className="max-w-7xl mx-auto space-y-6">
            {children}
          </div>
        </main>
      </div>
    </div>
  );
};
