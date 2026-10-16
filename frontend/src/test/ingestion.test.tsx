import { describe, it, expect, vi, beforeEach } from 'vitest';
import { render, screen, fireEvent, waitFor } from '@testing-library/react';
import { UploadView } from '../views/UploadView';
import { LibraryView } from '../views/LibraryView';
import { lectureService } from '../services/lectureService';
import { Lecture } from '../types';

vi.mock('../services/lectureService', () => ({
  lectureService: {
    listLectures: vi.fn(),
    uploadLectureMedia: vi.fn(),
    ingestYouTubeLecture: vi.fn(),
    deleteLecture: vi.fn(),
  },
}));

describe('Phase 1 Ingestion UI Tests', () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it('switches between direct file upload and YouTube URL mode', () => {
    render(<UploadView />);

    expect(screen.getByText(/Direct File Upload/i)).toBeInTheDocument();
    expect(screen.getByText(/Click or drag lecture video or audio here/i)).toBeInTheDocument();

    // Click YouTube tab
    const youtubeTab = screen.getByRole('button', { name: /youtube url/i });
    fireEvent.click(youtubeTab);

    expect(screen.getByPlaceholderText(/https:\/\/www\.youtube\.com\/watch\?v=\.\.\./i)).toBeInTheDocument();
  });

  it('handles YouTube form submission and triggers background job tracking', async () => {
    const mockIngestResponse = {
      lecture_id: 'lec-999',
      job_id: 'job-999',
      status: 'queued',
      title: 'Neural Networks Overview',
    };
    (lectureService.ingestYouTubeLecture as any).mockResolvedValueOnce(mockIngestResponse);

    render(<UploadView />);

    // Switch to YouTube tab
    fireEvent.click(screen.getByRole('button', { name: /youtube url/i }));

    // Fill inputs
    const titleInput = screen.getByPlaceholderText(/e\.g\., Deep Learning 101/i);
    const urlInput = screen.getByPlaceholderText(/https:\/\/www\.youtube\.com\/watch\?v=\.\.\./i);
    fireEvent.change(titleInput, { target: { value: 'Neural Networks Overview' } });
    fireEvent.change(urlInput, { target: { value: 'https://www.youtube.com/watch?v=dQw4w9WgXcQ' } });

    // Submit
    fireEvent.click(screen.getByRole('button', { name: /start ingestion pipeline/i }));

    await waitFor(() => {
      expect(lectureService.ingestYouTubeLecture).toHaveBeenCalledWith({
        url: 'https://www.youtube.com/watch?v=dQw4w9WgXcQ',
        title: 'Neural Networks Overview',
      });
      expect(screen.getByTestId('upload-job-progress')).toBeInTheDocument();
    });
  });

  it('renders lecture list with duration and 3D coordinates in LibraryView', async () => {
    const mockLectures: Lecture[] = [
      {
        id: 'lec-101',
        title: 'Fourier Transforms & Signal Decomposition',
        source_type: 'upload',
        duration_seconds: 3600,
        status: 'ready',
        coordinates: { x: 0.0, y: 0.0, z: 0.0 },
        created_at: '2026-10-16T12:00:00Z',
        updated_at: '2026-10-16T12:05:00Z',
      },
    ];
    (lectureService.listLectures as any).mockResolvedValueOnce(mockLectures);

    render(<LibraryView />);

    await waitFor(() => {
      expect(screen.getByText('Fourier Transforms & Signal Decomposition')).toBeInTheDocument();
      expect(screen.getByText(/1h 0m/i)).toBeInTheDocument();
      expect(screen.getByText(/3D Coord: \(0.0, 0.0, 0.0\)/i)).toBeInTheDocument();
      expect(screen.getByText('READY')).toBeInTheDocument();
    });
  });
});
