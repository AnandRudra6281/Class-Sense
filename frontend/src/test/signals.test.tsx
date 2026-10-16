import { describe, it, expect, vi, beforeEach } from 'vitest';
import { render, screen, fireEvent, waitFor } from '@testing-library/react';
import { AnalysisView } from '../views/AnalysisView';
import { EvidenceView } from '../views/EvidenceView';
import { lectureService } from '../services/lectureService';
import { ConfusionEvent, Evidence, Lecture, Topic, TranscriptSegment } from '../types';

vi.mock('../services/lectureService', () => ({
  lectureService: {
    listLectures: vi.fn(),
    getTranscript: vi.fn(),
    transcribeLecture: vi.fn(),
    getTopics: vi.fn(),
    segmentTopics: vi.fn(),
    analyzeSignals: vi.fn(),
    getConfusionEvents: vi.fn(),
    getEvidence: vi.fn(),
  },
}));

describe('Phase 3 Topics & Signals Tests', () => {
  const mockLectures: Lecture[] = [
    {
      id: 'lec-301',
      title: 'Eigenvalues & Cognitive Friction',
      source_type: 'upload',
      duration_seconds: 240.0,
      status: 'ready',
      coordinates: { x: 0.0, y: 0.0, z: 0.0 },
      created_at: '2026-10-16T12:00:00Z',
      updated_at: '2026-10-16T12:05:00Z',
    },
  ];

  const mockTopics: Topic[] = [
    {
      id: 'top-1',
      lecture_id: 'lec-301',
      parent_id: null,
      title: 'Matrix Diagonalization',
      summary: 'Introduction to diagonal matrices and basis transformations.',
      start_time: 0.0,
      end_time: 120.0,
      depth: 0,
      coordinates: { x: 0.0, y: 35.0, z: 0.0 },
    },
    {
      id: 'top-2',
      lecture_id: 'lec-301',
      parent_id: 'top-1',
      title: 'Characteristic Polynomial Hesitation',
      summary: 'Struggle point during determinant computation.',
      start_time: 60.0,
      end_time: 120.0,
      depth: 1,
      coordinates: { x: 25.0, y: 72.0, z: 1.0 },
    },
  ];

  const mockSegments: TranscriptSegment[] = [
    {
      id: 'seg-301',
      lecture_id: 'lec-301',
      start_time: 0.0,
      end_time: 10.0,
      text: 'Um if if we consider the determinant...',
      words: [
        { word: 'Um', start: 0.0, end: 0.5 },
        { word: 'if', start: 0.6, end: 0.9 },
        { word: 'if', start: 1.0, end: 1.3 },
      ],
      coordinates: { x: 0.0, y: 0.0, z: 0.0 },
    },
  ];

  const mockConfusionEvents: ConfusionEvent[] = [
    {
      id: 'conf-1',
      lecture_id: 'lec-301',
      segment_id: 'seg-301',
      timestamp_start: 0.0,
      timestamp_end: 10.0,
      confusion_score: 0.72,
      misconception_text: 'Pronounced speech disfluency and hesitation (50% disfluency ratio) during concept presentation.',
      evidence_text: 'Um if if we consider the determinant...',
      signals: {
        wpm_anomaly_z: 2.1,
        pause_density: 0.4,
        disfluency_ratio: 0.5,
        acoustic_friction_score: 0.72,
        primary_signal: 'disfluency',
      },
      coordinates: { x: 0.0, y: 72.0, z: 1.0 },
    },
  ];

  const mockEvidence: Evidence[] = [
    {
      id: 'evi-1',
      confusion_id: 'conf-1',
      quote: 'Um if if we consider the determinant...',
      signal_type: 'disfluency',
      confidence: 0.72,
      timestamp_start: 0.0,
      timestamp_end: 10.0,
      coordinates: { x: 0.0, y: 72.0, z: 1.0 },
    },
  ];

  beforeEach(() => {
    vi.clearAllMocks();
  });

  it('renders topic hierarchy and triggers segment-topics action in AnalysisView', async () => {
    (lectureService.listLectures as any).mockResolvedValue(mockLectures);
    (lectureService.getTranscript as any).mockResolvedValue(mockSegments);
    (lectureService.getTopics as any).mockResolvedValue(mockTopics);
    (lectureService.segmentTopics as any).mockResolvedValue({
      job_id: 'job-topic-1',
      lecture_id: 'lec-301',
      status: 'queued',
    });

    render(<AnalysisView />);

    await waitFor(() => {
      expect(screen.getByText('Eigenvalues & Cognitive Friction')).toBeInTheDocument();
    });

    await waitFor(() => {
      expect(screen.getByText('Matrix Diagonalization')).toBeInTheDocument();
      expect(screen.getByText('Characteristic Polynomial Hesitation')).toBeInTheDocument();
      expect(screen.getByText(/Subtopic \(Depth 1\)/i)).toBeInTheDocument();
      expect(screen.getByText(/Coord: \(25.0, 72.0, 1.0\)/i)).toBeInTheDocument();
    });

    const segmentBtn = screen.getByRole('button', { name: /segment topics/i });
    fireEvent.click(segmentBtn);

    await waitFor(() => {
      expect(lectureService.segmentTopics).toHaveBeenCalledWith('lec-301');
    });
  });

  it('triggers signal analysis action in AnalysisView', async () => {
    (lectureService.listLectures as any).mockResolvedValue(mockLectures);
    (lectureService.getTranscript as any).mockResolvedValue(mockSegments);
    (lectureService.getTopics as any).mockResolvedValue(mockTopics);
    (lectureService.analyzeSignals as any).mockResolvedValue({
      job_id: 'job-signals-1',
      lecture_id: 'lec-301',
      status: 'queued',
    });

    render(<AnalysisView />);

    await waitFor(() => {
      expect(screen.getByRole('button', { name: /analyze signals/i })).toBeInTheDocument();
    });

    const analyzeBtn = screen.getByRole('button', { name: /analyze signals/i });
    fireEvent.click(analyzeBtn);

    await waitFor(() => {
      expect(lectureService.analyzeSignals).toHaveBeenCalledWith('lec-301');
    });
  });

  it('renders live empirical evidence cards and signals in EvidenceView', async () => {
    (lectureService.listLectures as any).mockResolvedValue(mockLectures);
    (lectureService.getEvidence as any).mockResolvedValue(mockEvidence);
    (lectureService.getConfusionEvents as any).mockResolvedValue(mockConfusionEvents);

    render(<EvidenceView />);

    await waitFor(() => {
      expect(screen.getByText(/Confusion Signal Evidence/i)).toBeInTheDocument();
      expect(screen.getByText('DISFLUENCY')).toBeInTheDocument();
      expect(screen.getByText(/72%/i)).toBeInTheDocument();
      expect(screen.getByText(/Um if if we consider the determinant/i)).toBeInTheDocument();
      expect(screen.getByText(/Pronounced speech disfluency and hesitation/i)).toBeInTheDocument();
      expect(screen.getByText(/Coord: \(0.0, 72.0, 1.0\)/i)).toBeInTheDocument();
      expect(screen.getByText(/WPM Anomaly:/i)).toBeInTheDocument();
      expect(screen.getByText(/Pause Density:/i)).toBeInTheDocument();
    });
  });
});
