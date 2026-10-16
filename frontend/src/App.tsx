import React, { useState } from 'react';
import { useNavigation } from './hooks/useNavigation';
import { AppLayout } from './components/layout';
import {
  LandingView,
  DashboardView,
  LibraryView,
  UploadView,
  AnalysisView,
  EvidenceView,
  MisconceptionsView,
  StudentView,
  ReportsView,
  SettingsView,
} from './views';
import { ViewId } from './types';

export const App: React.FC = () => {
  const { currentView, navigateTo } = useNavigation('dashboard');
  const [demoMode, setDemoMode] = useState<boolean>(false);

  const renderActiveView = () => {
    switch (currentView) {
      case 'landing':
        return <LandingView onNavigate={(view) => navigateTo(view as ViewId)} />;
      case 'dashboard':
        return <DashboardView />;
      case 'library':
        return <LibraryView onNavigate={navigateTo} />;
      case 'upload':
        return <UploadView onNavigate={navigateTo} />;
      case 'analysis':
        return <AnalysisView onNavigate={navigateTo} />;
      case 'evidence':
        return <EvidenceView />;
      case 'misconceptions':
        return <MisconceptionsView />;
      case 'student':
        return <StudentView />;
      case 'reports':
        return <ReportsView />;
      case 'settings':
        return <SettingsView />;
      default:
        return <DashboardView />;
    }
  };

  return (
    <AppLayout
      currentView={currentView}
      onNavigate={navigateTo}
      demoMode={demoMode}
      onToggleDemoMode={() => setDemoMode(!demoMode)}
    >
      {renderActiveView()}
    </AppLayout>
  );
};

export default App;
