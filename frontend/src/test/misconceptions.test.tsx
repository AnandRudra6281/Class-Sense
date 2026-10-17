import { describe, it, expect, vi, beforeEach } from 'vitest';
import { render, screen, fireEvent, waitFor, within } from '@testing-library/react';
import { MisconceptionsView } from '../views/MisconceptionsView';
import { lectureService } from '../services/lectureService';
import { ConfusionEvent, Lecture, Misconception } from '../types';

vi.mock('../services/lectureService', () => ({
  lectureService: {
    listLectures: vi.fn(),
    getMisconceptions: vi.fn(),
    getConfusionEvents: vi.fn(),
    getPrerequisites: vi.fn().mockResolvedValue([]),
    extractMisconceptions: vi.fn(),
    tracePrerequisites: vi.fn(),
  },
}));

describe('Phase 4 MisconceptionsView Tests', () => {
  const mockLectures: Lecture[] = [
    {
      id: 'lec-401',
      title: 'Multivariable Calculus & Gradients',
      source_type: 'upload',
      duration_seconds: 360.0,
      status: 'analyzed',
      coordinates: { x: 0.0, y: 0.0, z: 0.0 },
      created_at: '2026-10-16T12:00:00Z',
      updated_at: '2026-10-16T12:05:00Z',
    },
  ];

  const mockConfusionEvents: ConfusionEvent[] = [
    {
      id: 'conf-401',
      lecture_id: 'lec-401',
      timestamp_start: 120.0,
      timestamp_end: 135.0,
      confusion_score: 0.85,
      misconception_text: 'Cognitive hesitation during partial derivative calculation.',
      evidence_text: '...wait, why does the gradient point in the direction of steepest ascent...',
      signals: { wpm_anomaly_z: 2.5, pause_density: 0.42, primary_signal: 'pause_density' },
      coordinates: { x: 33.3, y: 85.0, z: 1.0 },
    },
  ];

  const mockMisconceptions: Misconception[] = [
    {
      id: 'misc-1',
      confusion_id: 'conf-401',
      name: 'Confusing Directional Derivative with Gradient Magnitude',
      explanation: 'Students assume the gradient is a scalar rate of change rather than a vector specifying direction and max rate.',
      apparent_reason: 'Over-reliance on single-variable derivative intuition without vector field foundations.',
      severity: 'critical',
      cognitive_load_score: 0.92,
      coordinates: { x: 33.3, y: 92.0, z: 1.0 },
    },
    {
      id: 'misc-2',
      confusion_id: 'conf-401',
      name: 'Assuming Level Curves Align with Gradient Vector',
      explanation: 'Students believe the gradient points tangent to the contour lines rather than orthogonal to them.',
      apparent_reason: 'Confusion between tangent vectors to level sets and normal gradient vectors.',
      severity: 'high',
      cognitive_load_score: 0.74,
      coordinates: { x: 33.3, y: 74.0, z: 1.0 },
    },
  ];

  beforeEach(() => {
    vi.clearAllMocks();
  });

  it('renders potential misconceptions (inferred from lecture speech) with severity badges, model confidence, root cause gaps, and coordinates', async () => {
    (lectureService.listLectures as any).mockResolvedValue(mockLectures);
    (lectureService.getMisconceptions as any).mockResolvedValue(mockMisconceptions);
    (lectureService.getConfusionEvents as any).mockResolvedValue(mockConfusionEvents);
    (lectureService.getPrerequisites as any).mockResolvedValue([]);

    render(<MisconceptionsView />);

    await waitFor(() => {
      expect(screen.getByRole('heading', { level: 3, name: /Multivariable Calculus & Gradients/i })).toBeInTheDocument();
    });

    const list = await screen.findByTestId('misconceptions-list');
    expect(list).toBeInTheDocument();

    expect(within(list).getByText('Confusing Directional Derivative with Gradient Magnitude')).toBeInTheDocument();
    expect(within(list).getByText('Assuming Level Curves Align with Gradient Vector')).toBeInTheDocument();
    expect(within(list).getByText(/CRITICAL SEVERITY/i)).toBeInTheDocument();
    expect(within(list).getByText(/HIGH SEVERITY/i)).toBeInTheDocument();
    expect(within(list).getAllByText(/Model Confidence: 85%/i).length).toBe(2);
    expect(within(list).getByText(/Over-reliance on single-variable derivative intuition/i)).toBeInTheDocument();
    expect(within(list).getByText(/Coord: \(33.3, 92.0, 1.0\)/i)).toBeInTheDocument();
    expect(within(list).getAllByText('92%').length).toBeGreaterThan(0);
    expect(within(list).getAllByText('74%').length).toBeGreaterThan(0);
  });

  it('triggers extractMisconceptions action and launches polling', async () => {
    (lectureService.listLectures as any).mockResolvedValue(mockLectures);
    (lectureService.getMisconceptions as any).mockResolvedValue(mockMisconceptions);
    (lectureService.getConfusionEvents as any).mockResolvedValue(mockConfusionEvents);
    (lectureService.getPrerequisites as any).mockResolvedValue([]);
    (lectureService.extractMisconceptions as any).mockResolvedValue({
      job_id: 'job-misc-401',
      lecture_id: 'lec-401',
      status: 'queued',
    });

    render(<MisconceptionsView />);

    const extractBtn = await screen.findByRole('button', { name: /extract potential misconceptions/i });
    await waitFor(() => {
      expect(extractBtn).not.toBeDisabled();
    });

    fireEvent.click(extractBtn);

    await waitFor(() => {
      expect(lectureService.extractMisconceptions).toHaveBeenCalledWith('lec-401');
    });
  });
});
