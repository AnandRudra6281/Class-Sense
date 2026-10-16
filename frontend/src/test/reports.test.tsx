import { describe, it, expect, vi, beforeEach } from 'vitest';
import { render, screen, fireEvent, waitFor } from '@testing-library/react';
import { ReportsView } from '../views/ReportsView';
import { lectureService } from '../services/lectureService';
import { Lecture, Report } from '../types';

vi.mock('../services/lectureService', () => ({
  lectureService: {
    listLectures: vi.fn(),
    getReports: vi.fn(),
    generateReport: vi.fn(),
    exportReport: vi.fn(),
  },
}));

describe('Phase 8 Reports Generation & Analytics Tests', () => {
  const mockLectures: Lecture[] = [
    {
      id: 'lec-801',
      title: 'Quantum Mechanics: Wavefunctions & Probability Amplitudes',
      source_type: 'upload',
      duration_seconds: 1200.0,
      status: 'analyzed',
      coordinates: { x: 0.0, y: 0.0, z: 0.0 },
      created_at: '2026-10-16T12:00:00Z',
      updated_at: '2026-10-16T12:05:00Z',
    },
  ];

  const mockReports: Report[] = [
    {
      id: 'rep-801',
      lecture_id: 'lec-801',
      title: 'Pedagogy Quality & Cognitive Audit: Quantum Wavefunctions',
      executive_summary: 'The lecture delivered a rigorous introduction to quantum wave mechanics across 4 main topics. A significant cognitive friction spike occurred at the Born rule.',
      confusion_density: 0.25,
      key_recommendations: [
        'Dedicate 4 minutes to visualizing complex multiplication on the Argand plane.',
        'Contrast physical oscillating waves against probability amplitudes on the blackboard.',
        'Use diagnostic checkpoint questions before introducing the Hamiltonian.',
      ],
      metrics: {
        total_duration_seconds: 1200.0,
        total_segments: 4,
        total_topics: 2,
        confusion_spikes: 1,
        confusion_density: 0.25,
        avg_confusion_score: 0.86,
        total_misconceptions: 1,
        critical_misconceptions: 1,
        traced_prerequisites: 1,
        avg_wpm: 136.5,
        hesitation_pause_count: 3,
        pedagogy_quality_score: 82.5,
      },
      export_format: 'markdown',
      coordinates: { x: 50.0, y: 25.0, z: 0.0 },
      created_at: '2026-10-16T12:30:00Z',
    },
  ];

  beforeEach(() => {
    vi.clearAllMocks();
    window.URL.createObjectURL = vi.fn(() => 'blob:mock-url');
    window.URL.revokeObjectURL = vi.fn();
  });

  it('renders pedagogy quality audit report with KPI metrics, narrative, and recommendations', async () => {
    (lectureService.listLectures as any).mockResolvedValue(mockLectures);
    (lectureService.getReports as any).mockResolvedValue(mockReports);

    render(<ReportsView />);

    await waitFor(() => {
      expect(screen.getByRole('heading', { level: 1, name: /Pedagogy Reports & Analytics/i })).toBeInTheDocument();
      expect(screen.getByText('Pedagogy Quality & Cognitive Audit: Quantum Wavefunctions')).toBeInTheDocument();
    });

    // Check KPI metric cards
    expect(screen.getByText('82.5%')).toBeInTheDocument();
    expect(screen.getByText('25%')).toBeInTheDocument(); // Confusion density
    expect(screen.getByText('137')).toBeInTheDocument(); // Speech rate WPM (rounded 136.5 -> 137)
    expect(screen.getByText('Coord: (50, 25, 0)')).toBeInTheDocument();

    // Check Executive Narrative
    expect(screen.getByText(/The lecture delivered a rigorous introduction to quantum wave mechanics/i)).toBeInTheDocument();

    // Check Recommendations
    expect(screen.getByText(/Dedicate 4 minutes to visualizing complex multiplication on the Argand plane/i)).toBeInTheDocument();
    expect(screen.getByText(/Contrast physical oscillating waves against probability amplitudes/i)).toBeInTheDocument();
  });

  it('triggers report generation when button clicked', async () => {
    (lectureService.listLectures as any).mockResolvedValue(mockLectures);
    (lectureService.getReports as any).mockResolvedValue(mockReports);
    (lectureService.generateReport as any).mockResolvedValue({
      job_id: 'job-rep-801',
      lecture_id: 'lec-801',
      status: 'queued',
    });

    render(<ReportsView />);

    const generateBtn = await screen.findByTestId('generate-report-btn');
    fireEvent.click(generateBtn);

    await waitFor(() => {
      expect(lectureService.generateReport).toHaveBeenCalledWith('lec-801');
    });
  });

  it('triggers export downloads for markdown and json formats', async () => {
    (lectureService.listLectures as any).mockResolvedValue(mockLectures);
    (lectureService.getReports as any).mockResolvedValue(mockReports);
    (lectureService.exportReport as any).mockImplementation((_lecId: string, _repId: string, format: string) => {
      return Promise.resolve({
        report_id: 'rep-801',
        lecture_id: 'lec-801',
        format,
        content: format === 'json' ? '{"title": "Quantum Audit"}' : '# Quantum Audit',
        filename: `ClassSense_Audit.${format === 'json' ? 'json' : 'md'}`,
      });
    });

    render(<ReportsView />);

    // Click Export Markdown
    const exportMdBtn = await screen.findByTestId('export-markdown-btn');
    fireEvent.click(exportMdBtn);

    await waitFor(() => {
      expect(lectureService.exportReport).toHaveBeenCalledWith('lec-801', 'rep-801', 'markdown');
    });

    // Click Export JSON
    const exportJsonBtn = await screen.findByTestId('export-json-btn');
    fireEvent.click(exportJsonBtn);

    await waitFor(() => {
      expect(lectureService.exportReport).toHaveBeenCalledWith('lec-801', 'rep-801', 'json');
    });
  });
});
