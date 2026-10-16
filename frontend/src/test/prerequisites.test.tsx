import { describe, it, expect, vi, beforeEach } from 'vitest';
import { render, screen, fireEvent, waitFor, within } from '@testing-library/react';
import { MisconceptionsView } from '../views/MisconceptionsView';
import { lectureService } from '../services/lectureService';
import { ConfusionEvent, Lecture, Misconception, PrerequisiteNode } from '../types';

vi.mock('../services/lectureService', () => ({
  lectureService: {
    listLectures: vi.fn(),
    getMisconceptions: vi.fn(),
    getConfusionEvents: vi.fn(),
    getPrerequisites: vi.fn(),
    extractMisconceptions: vi.fn(),
    tracePrerequisites: vi.fn(),
  },
}));

describe('Phase 5 Prerequisite Tracing & Vector Retrieval Tests', () => {
  const mockLectures: Lecture[] = [
    {
      id: 'lec-501',
      title: 'Multivariable Calculus & Gradient Fields',
      source_type: 'upload',
      duration_seconds: 400.0,
      status: 'analyzed',
      coordinates: { x: 0.0, y: 0.0, z: 0.0 },
      created_at: '2026-10-16T12:00:00Z',
      updated_at: '2026-10-16T12:05:00Z',
    },
  ];

  const mockConfusionEvents: ConfusionEvent[] = [
    {
      id: 'conf-501',
      lecture_id: 'lec-501',
      timestamp_start: 120.0,
      timestamp_end: 140.0,
      confusion_score: 0.85,
      misconception_text: 'Student struggle with directional derivatives.',
      evidence_text: 'Wait, why is directional derivative a dot product with the gradient vector?',
      signals: { wpm_anomaly_z: 2.3, pause_density: 0.40 },
      coordinates: { x: 25.0, y: 85.0, z: 1.0 },
    },
  ];

  const mockMisconceptions: Misconception[] = [
    {
      id: 'misc-501',
      confusion_id: 'conf-501',
      name: 'Confusing Directional Derivative with Gradient Magnitude',
      explanation: 'Students assume the directional derivative is scalar length rather than directional projection.',
      apparent_reason: 'Missing foundational understanding of vector dot product projection geometry.',
      severity: 'critical',
      cognitive_load_score: 0.92,
      coordinates: { x: 25.0, y: 92.0, z: 1.0 },
    },
  ];

  const mockPrerequisites: PrerequisiteNode[] = [
    {
      id: 'prereq-1',
      confusion_id: 'conf-501',
      concept_name: 'Vector Dot Product and Orthogonal Projection',
      gap_description: 'Inability to compute or visualize orthogonal shadows on unit vectors.',
      remediation_hint: 'Practice 2D projection formulas and dot product cosine theorems.',
      depth: 1,
      vector_distance: 0.284,
      coordinates: { x: 25.0, y: 28.4, z: 1.0 },
    },
    {
      id: 'prereq-2',
      confusion_id: 'conf-501',
      concept_name: 'Single-Variable Linear Approximation',
      gap_description: 'Viewing derivatives as static rates rather than local linear tangent transformations.',
      remediation_hint: 'Review tangent line approximations before multivariable generalizations.',
      depth: 2,
      vector_distance: 0.612,
      coordinates: { x: 25.0, y: 61.2, z: 2.0 },
    },
  ];

  beforeEach(() => {
    vi.clearAllMocks();
  });

  it('renders traced prerequisite knowledge nodes with depth badges, vector distance, and coordinates', async () => {
    (lectureService.listLectures as any).mockResolvedValue(mockLectures);
    (lectureService.getConfusionEvents as any).mockResolvedValue(mockConfusionEvents);
    (lectureService.getMisconceptions as any).mockResolvedValue(mockMisconceptions);
    (lectureService.getPrerequisites as any).mockResolvedValue(mockPrerequisites);

    render(<MisconceptionsView />);

    await waitFor(() => {
      expect(screen.getByRole('heading', { level: 3, name: /Multivariable Calculus & Gradient Fields/i })).toBeInTheDocument();
    });

    const list = await screen.findByTestId('misconceptions-list');
    expect(list).toBeInTheDocument();

    const prereqSection = await screen.findByTestId('prerequisite-nodes-list');
    expect(prereqSection).toBeInTheDocument();

    expect(within(prereqSection).getByText('Vector Dot Product and Orthogonal Projection')).toBeInTheDocument();
    expect(within(prereqSection).getByText(/Depth 1: Direct Gap/i)).toBeInTheDocument();
    expect(within(prereqSection).getByText(/Vector Dist: 0.284/i)).toBeInTheDocument();
    expect(within(prereqSection).getByText(/Practice 2D projection formulas/i)).toBeInTheDocument();
    expect(within(prereqSection).getByText(/Coord: \(25.0, 28.4, 1.0\)/i)).toBeInTheDocument();

    expect(within(prereqSection).getByText('Single-Variable Linear Approximation')).toBeInTheDocument();
    expect(within(prereqSection).getByText(/Depth 2: Foundational/i)).toBeInTheDocument();
    expect(within(prereqSection).getByText(/Vector Dist: 0.612/i)).toBeInTheDocument();
  });

  it('triggers tracePrerequisites action when Trace Prerequisites button is clicked', async () => {
    (lectureService.listLectures as any).mockResolvedValue(mockLectures);
    (lectureService.getConfusionEvents as any).mockResolvedValue(mockConfusionEvents);
    (lectureService.getMisconceptions as any).mockResolvedValue(mockMisconceptions);
    (lectureService.getPrerequisites as any).mockResolvedValue(mockPrerequisites);
    (lectureService.tracePrerequisites as any).mockResolvedValue({
      job_id: 'job-trace-501',
      lecture_id: 'lec-501',
      status: 'queued',
    });

    render(<MisconceptionsView />);

    const traceBtn = await screen.findByTestId('trace-prerequisites-btn');
    await waitFor(() => {
      expect(traceBtn).not.toBeDisabled();
    });

    fireEvent.click(traceBtn);

    await waitFor(() => {
      expect(lectureService.tracePrerequisites).toHaveBeenCalledWith('lec-501');
    });
  });
});
