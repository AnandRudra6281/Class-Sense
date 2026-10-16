import { describe, it, expect, vi, beforeEach } from 'vitest';
import { render, screen, fireEvent, waitFor, within } from '@testing-library/react';
import { DashboardView } from '../views/DashboardView';
import { lectureService } from '../services/lectureService';
import { ConfusionEvent, Intervention, Lecture, Misconception, PrerequisiteNode } from '../types';

vi.mock('../services/lectureService', () => ({
  lectureService: {
    listLectures: vi.fn(),
    getConfusionEvents: vi.fn(),
    getMisconceptions: vi.fn(),
    getPrerequisites: vi.fn(),
    getInterventions: vi.fn(),
    generateInterventions: vi.fn(),
  },
}));

describe('Phase 6 Teacher Interventions & Instructor Cockpit Tests', () => {
  const mockLectures: Lecture[] = [
    {
      id: 'lec-601',
      title: 'Multivariable Calculus & Tangent Planes',
      source_type: 'upload',
      duration_seconds: 520.0,
      status: 'analyzed',
      coordinates: { x: 40.0, y: 85.0, z: 1.0 },
      created_at: '2026-10-16T12:00:00Z',
      updated_at: '2026-10-16T12:05:00Z',
    },
  ];

  const mockConfusionEvents: ConfusionEvent[] = [
    {
      id: 'conf-601',
      lecture_id: 'lec-601',
      timestamp_start: 200.0,
      timestamp_end: 230.0,
      confusion_score: 0.85,
      misconception_text: 'Student struggle with gradient vector orthogonality.',
      evidence_text: 'Wait, does the gradient point tangent to the level curve?',
      signals: { wpm_anomaly_z: 2.1, pause_density: 0.40 },
      coordinates: { x: 40.0, y: 85.0, z: 1.0 },
    },
  ];

  const mockMisconceptions: Misconception[] = [
    {
      id: 'misc-601',
      confusion_id: 'conf-601',
      name: 'Assuming Gradient Aligns Tangent to Level Curves',
      explanation: 'Students believe gradient vector points along contour line.',
      apparent_reason: 'Confusion between tangent vectors and normal vectors.',
      severity: 'critical',
      cognitive_load_score: 0.94,
      coordinates: { x: 40.0, y: 94.0, z: 1.0 },
    },
  ];

  const mockPrerequisites: PrerequisiteNode[] = [
    {
      id: 'prereq-601',
      confusion_id: 'conf-601',
      concept_name: 'Normal Vectors and Orthogonality',
      gap_description: 'Missing intuition that level sets represent constant elevation contours.',
      remediation_hint: 'Review 2D contour maps with hiker elevation paths.',
      depth: 1,
      vector_distance: 0.25,
      coordinates: { x: 40.0, y: 25.0, z: 1.0 },
    },
  ];

  const mockInterventions: Intervention[] = [
    {
      id: 'inv-601',
      lecture_id: 'lec-601',
      target_type: 'teacher',
      title: 'Calibrated Directional Derivative & Gradient Orthogonality Recap',
      content: {
        actionable_recap: [
          'Open with a 3-minute sketch of a circular level curve representing constant elevation.',
          'Contrast tangent walking against perpendicular steepest ascent.',
        ],
        diagnostic_questions: [
          {
            question: 'If you walk along a level curve, what is the directional derivative?',
            options: [
              'Zero, because elevation does not change.',
              'Equal to the gradient magnitude.',
              'Negative infinity.',
              'Undefined.',
            ],
            correct_option_index: 0,
            rationale: 'Elevation remains constant, so derivative is zero.',
            targeted_misconception: 'Assuming Gradient Aligns Tangent to Level Curves',
          },
        ],
        recommended_pacing: 'Pause for 45 seconds after sketching the contour circle.',
        blackboard_analogy: 'Think of a hiker on a mountain trail: the trail follows the contour.',
      },
      coordinates: { x: 40.0, y: 94.0, z: 1.0 },
    },
  ];

  beforeEach(() => {
    vi.clearAllMocks();
  });

  it('renders live instructor cockpit with teacher interventions, actionable recaps, and diagnostic questions', async () => {
    (lectureService.listLectures as any).mockResolvedValue(mockLectures);
    (lectureService.getConfusionEvents as any).mockResolvedValue(mockConfusionEvents);
    (lectureService.getMisconceptions as any).mockResolvedValue(mockMisconceptions);
    (lectureService.getPrerequisites as any).mockResolvedValue(mockPrerequisites);
    (lectureService.getInterventions as any).mockResolvedValue(mockInterventions);

    render(<DashboardView />);

    await waitFor(() => {
      expect(screen.getByRole('heading', { level: 1, name: /Instructor Cockpit/i })).toBeInTheDocument();
      expect(screen.getByRole('heading', { level: 3, name: /Multivariable Calculus & Tangent Planes/i })).toBeInTheDocument();
    });

    const list = await screen.findByTestId('interventions-list');
    expect(list).toBeInTheDocument();

    expect(within(list).getByText('Calibrated Directional Derivative & Gradient Orthogonality Recap')).toBeInTheDocument();
    expect(within(list).getByText(/Next-Class Opening Recap/i)).toBeInTheDocument();
    expect(within(list).getByText(/Open with a 3-minute sketch of a circular level curve/i)).toBeInTheDocument();
    expect(within(list).getByText(/Pause for 45 seconds after sketching the contour circle/i)).toBeInTheDocument();
    expect(within(list).getByText(/Think of a hiker on a mountain trail/i)).toBeInTheDocument();
    expect(within(list).getByText(/If you walk along a level curve, what is the directional derivative\?/i)).toBeInTheDocument();
    expect(within(list).getByText(/Zero, because elevation does not change\./i)).toBeInTheDocument();
    expect(within(list).getByText(/Coord: \(40.0, 94.0, 1.0\)/i)).toBeInTheDocument();
  });

  it('triggers generateInterventions when button is clicked', async () => {
    (lectureService.listLectures as any).mockResolvedValue(mockLectures);
    (lectureService.getConfusionEvents as any).mockResolvedValue(mockConfusionEvents);
    (lectureService.getMisconceptions as any).mockResolvedValue(mockMisconceptions);
    (lectureService.getPrerequisites as any).mockResolvedValue(mockPrerequisites);
    (lectureService.getInterventions as any).mockResolvedValue(mockInterventions);
    (lectureService.generateInterventions as any).mockResolvedValue({
      job_id: 'job-inv-601',
      lecture_id: 'lec-601',
      status: 'queued',
    });

    render(<DashboardView />);

    const generateBtn = await screen.findByTestId('generate-interventions-btn');
    await waitFor(() => {
      expect(generateBtn).not.toBeDisabled();
    });

    fireEvent.click(generateBtn);

    await waitFor(() => {
      expect(lectureService.generateInterventions).toHaveBeenCalledWith('lec-601');
    });
  });
});
