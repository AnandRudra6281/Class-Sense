import { describe, it, expect, vi, beforeEach } from 'vitest';
import { render, screen, fireEvent, waitFor } from '@testing-library/react';
import { AnalysisView } from '../views/AnalysisView';
import { lectureService } from '../services/lectureService';
import { Lecture, TranscriptSegment } from '../types';

vi.mock('../services/lectureService', () => ({
  lectureService: {
    listLectures: vi.fn(),
    getTranscript: vi.fn(),
    transcribeLecture: vi.fn(),
    getTopics: vi.fn().mockResolvedValue([]),
  },
}));

describe('Phase 2 Transcription & AnalysisView Tests', () => {
  const mockLectures: Lecture[] = [
    {
      id: 'lec-202',
      title: 'Neural Networks & Optimization',
      source_type: 'upload',
      duration_seconds: 120.0,
      status: 'ready',
      coordinates: { x: 0.0, y: 0.0, z: 0.0 },
      created_at: '2026-10-16T12:00:00Z',
      updated_at: '2026-10-16T12:05:00Z',
    },
  ];

  const mockSegments: TranscriptSegment[] = [
    {
      id: 'seg-1',
      lecture_id: 'lec-202',
      start_time: 0.0,
      end_time: 4.5,
      text: 'Welcome to neural networks and optimization.',
      words: [
        { word: 'Welcome', start: 0.0, end: 0.8 },
        { word: 'to', start: 0.9, end: 1.1 },
        { word: 'neural', start: 1.2, end: 1.7 },
        { word: 'networks', start: 1.8, end: 2.5 },
      ],
      coordinates: { x: 0.0, y: 0.0, z: 0.0 },
    },
    {
      id: 'seg-2',
      lecture_id: 'lec-202',
      start_time: 4.5,
      end_time: 9.0,
      text: 'Today we discuss gradient descent.',
      words: [
        { word: 'Today', start: 4.5, end: 5.0 },
        { word: 'we', start: 5.1, end: 5.3 },
        { word: 'discuss', start: 5.4, end: 6.0 },
        { word: 'gradient', start: 6.1, end: 7.0 },
      ],
      coordinates: { x: 3.75, y: 0.0, z: 0.0 },
    },
  ];

  beforeEach(() => {
    vi.clearAllMocks();
  });

  it('renders lecture selector and triggers transcription', async () => {
    (lectureService.listLectures as any).mockResolvedValueOnce(mockLectures);
    (lectureService.getTranscript as any).mockResolvedValueOnce([]);
    (lectureService.transcribeLecture as any).mockResolvedValueOnce({
      job_id: 'job-asr-101',
      lecture_id: 'lec-202',
      status: 'queued',
    });

    render(<AnalysisView />);

    await waitFor(() => {
      expect(screen.getByText('Neural Networks & Optimization')).toBeInTheDocument();
      expect(screen.getByRole('button', { name: /transcribe/i })).toBeInTheDocument();
    });

    // Click transcribe button
    fireEvent.click(screen.getByRole('button', { name: /transcribe/i }));

    await waitFor(() => {
      expect(lectureService.transcribeLecture).toHaveBeenCalledWith('lec-202', 'auto');
      expect(screen.getByTestId('transcription-progress')).toBeInTheDocument();
    });
  });

  it('renders transcript segments with timestamps and 3D coordinates', async () => {
    (lectureService.listLectures as any).mockResolvedValueOnce(mockLectures);
    (lectureService.getTranscript as any).mockResolvedValueOnce(mockSegments);

    render(<AnalysisView />);

    await waitFor(() => {
      expect(screen.getByText('Welcome to neural networks and optimization.')).toBeInTheDocument();
      expect(screen.getByText('Today we discuss gradient descent.')).toBeInTheDocument();
      expect(screen.getByText(/Coord: \(0.0, 0.0, 0.0\)/i)).toBeInTheDocument();
      expect(screen.getByText(/Coord: \(3.8, 0.0, 0.0\)/i)).toBeInTheDocument();
      expect(screen.getAllByText('4 words').length).toBe(2);
    });

    // Expand word-level drawer
    const wordsBtn = screen.getAllByRole('button', { name: /4 words/i })[0];
    fireEvent.click(wordsBtn);

    await waitFor(() => {
      expect(screen.getByText('Word-Level Timestamps:')).toBeInTheDocument();
      expect(screen.getByText('Welcome')).toBeInTheDocument();
      expect(screen.getByText('0.00s')).toBeInTheDocument();
    });
  });
});
