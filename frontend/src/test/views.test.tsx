import { describe, it, expect } from 'vitest';
import { render, screen } from '@testing-library/react';
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
} from '../views';

describe('All 10 Platform Views Smoke Test', () => {
  it('1. renders LandingView', () => {
    render(<LandingView />);
    expect(screen.getByTestId('view-landing')).toBeInTheDocument();
    expect(screen.getByText(/ClassSense AI Teaching Assistant/i)).toBeInTheDocument();
  });

  it('2. renders DashboardView', () => {
    render(<DashboardView />);
    expect(screen.getByTestId('view-dashboard')).toBeInTheDocument();
    expect(screen.getByText(/Instructor Cockpit/i)).toBeInTheDocument();
  });

  it('3. renders LibraryView', () => {
    render(<LibraryView />);
    expect(screen.getByTestId('view-library')).toBeInTheDocument();
    expect(screen.getByText(/Lecture Library/i)).toBeInTheDocument();
  });

  it('4. renders UploadView', () => {
    render(<UploadView />);
    expect(screen.getByTestId('view-upload')).toBeInTheDocument();
    expect(screen.getByText(/Ingest Lecture Video \/ Audio/i)).toBeInTheDocument();
  });

  it('5. renders AnalysisView', () => {
    render(<AnalysisView />);
    expect(screen.getByTestId('view-analysis')).toBeInTheDocument();
    expect(screen.getByText(/Lecture Timeline & Topic Hierarchy/i)).toBeInTheDocument();
  });

  it('6. renders EvidenceView', () => {
    render(<EvidenceView />);
    expect(screen.getByTestId('view-evidence')).toBeInTheDocument();
    expect(screen.getByText(/Confusion Signal Evidence/i)).toBeInTheDocument();
  });

  it('7. renders MisconceptionsView', () => {
    render(<MisconceptionsView />);
    expect(screen.getByTestId('view-misconceptions')).toBeInTheDocument();
    expect(screen.getByText(/Extracted Misconceptions & Root Causes/i)).toBeInTheDocument();
  });

  it('8. renders StudentView', () => {
    render(<StudentView />);
    expect(screen.getByTestId('view-student')).toBeInTheDocument();
    expect(screen.getByText(/Student Catch-Up & Practice/i)).toBeInTheDocument();
  });

  it('9. renders ReportsView', () => {
    render(<ReportsView />);
    expect(screen.getByTestId('view-reports')).toBeInTheDocument();
    expect(screen.getByText(/Pedagogy Reports & Interventions/i)).toBeInTheDocument();
  });

  it('10. renders SettingsView', () => {
    render(<SettingsView />);
    expect(screen.getByTestId('view-settings')).toBeInTheDocument();
    expect(screen.getByText(/System & Provider Settings/i)).toBeInTheDocument();
  });
});
