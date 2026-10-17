import { describe, it, expect, vi, beforeEach } from 'vitest';
import { render, screen, fireEvent, waitFor } from '@testing-library/react';
import { UploadView } from '../views/UploadView';
import { lectureService } from '../services/lectureService';
import * as jobPollingHook from '../hooks/useJobPolling';
import { PipelineStageInfo } from '../types';

vi.mock('../services/lectureService', () => ({
  lectureService: {
    uploadLectureMedia: vi.fn(),
    ingestYouTubeLecture: vi.fn(),
    analyzeLecture: vi.fn(),
  },
}));

describe('UploadView Stage Stepper & Pipeline Tests', () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  const allSuccessStages: Record<string, PipelineStageInfo> = {
    transcribe: { name: 'Speech-to-Text', status: 'done', progress_pct: 100, error: null },
    segment_topics: { name: 'Topic Segmentation', status: 'done', progress_pct: 100, error: null },
    confusion: { name: 'Confusion Signals', status: 'done', progress_pct: 100, error: null },
    misconceptions: { name: 'Misconceptions', status: 'done', progress_pct: 100, error: null },
    prerequisites: { name: 'Prerequisites', status: 'done', progress_pct: 100, error: null },
    interventions: { name: 'Interventions', status: 'done', progress_pct: 100, error: null },
    student_catchup: { name: 'Student Catch-Up', status: 'done', progress_pct: 100, error: null },
    report: { name: 'Pedagogy Report', status: 'done', progress_pct: 100, error: null },
  };

  it('renders all 8 stages with success badges and links to analysis view when all stages succeed', async () => {
    const onNavigate = vi.fn();

    // Mock successful ingest with pipeline job
    (lectureService.ingestYouTubeLecture as any).mockResolvedValueOnce({
      lecture_id: 'lec-success-1',
      job_id: 'job-ingest-1',
      analyze_job_id: 'job-pipe-1',
      status: 'queued',
      title: 'Multivariable Calculus',
    });

    // Mock useJobPolling hook behavior
    vi.spyOn(jobPollingHook, 'useJobPolling').mockImplementation((id: string | null) => {
      if (id === 'job-pipe-1') {
        return {
          job: {
            id: 'job-pipe-1',
            job_type: 'lecture_pipeline',
            status: 'done',
            progress_pct: 100,
            error_message: null,
            payload: {
              lecture_id: 'lec-success-1',
              stages: allSuccessStages,
              failed_stage: null,
            },
            created_at: '2026-10-16T12:00:00Z',
            updated_at: '2026-10-16T12:05:00Z',
            coordinates: { x: 0, y: 0, z: 0 },
          },
          status: 'done',
          progress: 100,
          error: null,
          isPolling: false,
          retry: vi.fn(),
        };
      }
      return {
        job: null,
        status: null,
        progress: 0,
        error: null,
        isPolling: false,
        retry: vi.fn(),
      };
    });

    render(<UploadView onNavigate={onNavigate} />);

    // Switch to YouTube and submit
    fireEvent.click(screen.getByRole('button', { name: /youtube url/i }));
    fireEvent.change(screen.getByPlaceholderText(/e\.g\., Deep Learning 101/i), {
      target: { value: 'Multivariable Calculus' },
    });
    fireEvent.change(screen.getByPlaceholderText(/https:\/\/www\.youtube\.com\/watch\?v=\.\.\./i), {
      target: { value: 'https://www.youtube.com/watch?v=calc101' },
    });
    fireEvent.click(screen.getByRole('button', { name: /start ingestion pipeline/i }));

    await waitFor(() => {
      expect(screen.getByTestId('upload-job-progress')).toBeInTheDocument();
    });

    // Assert all 8 stage labels are rendered
    expect(screen.getByText('Speech-to-Text')).toBeInTheDocument();
    expect(screen.getByText('Topic Segmentation')).toBeInTheDocument();
    expect(screen.getByText('Confusion Signals')).toBeInTheDocument();
    expect(screen.getByText('Misconceptions')).toBeInTheDocument();
    expect(screen.getByText('Prerequisites')).toBeInTheDocument();
    expect(screen.getByText('Interventions')).toBeInTheDocument();
    expect(screen.getByText('Student Catch-Up')).toBeInTheDocument();
    expect(screen.getByText('Pedagogy Report')).toBeInTheDocument();

    // Assert overall 100% completion alert
    expect(screen.getByText(/All 8 Stages Analyzed Successfully/i)).toBeInTheDocument();

    // Assert View Full Analysis button is rendered and functional
    const viewAnalysisBtn = screen.getByRole('button', { name: /view full analysis/i });
    expect(viewAnalysisBtn).toBeInTheDocument();
    fireEvent.click(viewAnalysisBtn);
    expect(onNavigate).toHaveBeenCalledWith('analysis');
  });

  it('renders visible per-stage error and Retry button when a stage fails', async () => {
    (lectureService.ingestYouTubeLecture as any).mockResolvedValueOnce({
      lecture_id: 'lec-fail-1',
      job_id: 'job-ingest-2',
      analyze_job_id: 'job-pipe-failed',
      status: 'queued',
      title: 'Quantum Mechanics',
    });

    const failedStages: Record<string, PipelineStageInfo> = {
      transcribe: { name: 'Speech-to-Text', status: 'done', progress_pct: 100, error: null },
      segment_topics: { name: 'Topic Segmentation', status: 'done', progress_pct: 100, error: null },
      confusion: { name: 'Confusion Signals', status: 'done', progress_pct: 100, error: null },
      misconceptions: {
        name: 'Misconceptions',
        status: 'failed',
        progress_pct: 40,
        error: 'Provider call timed out after 30.0s during misconception diagnosis',
      },
      prerequisites: { name: 'Prerequisites', status: 'pending', progress_pct: 0, error: null },
      interventions: { name: 'Interventions', status: 'pending', progress_pct: 0, error: null },
      student_catchup: { name: 'Student Catch-Up', status: 'pending', progress_pct: 0, error: null },
      report: { name: 'Pedagogy Report', status: 'pending', progress_pct: 0, error: null },
    };

    vi.spyOn(jobPollingHook, 'useJobPolling').mockImplementation((id: string | null) => {
      if (id === 'job-pipe-failed') {
        return {
          job: {
            id: 'job-pipe-failed',
            job_type: 'lecture_pipeline',
            status: 'failed',
            progress_pct: 35,
            error_message: "Stage 'misconceptions' failed: Provider call timed out after 30.0s during misconception diagnosis",
            payload: {
              lecture_id: 'lec-fail-1',
              stages: failedStages,
              failed_stage: 'misconceptions',
            },
            created_at: '2026-10-16T12:00:00Z',
            updated_at: '2026-10-16T12:05:00Z',
            coordinates: { x: 0, y: 0, z: 0 },
          },
          status: 'failed',
          progress: 35,
          error: "Stage 'misconceptions' failed: Provider call timed out after 30.0s during misconception diagnosis",
          isPolling: false,
          retry: vi.fn(),
        };
      }
      return {
        job: null,
        status: null,
        progress: 0,
        error: null,
        isPolling: false,
        retry: vi.fn(),
      };
    });

    render(<UploadView />);

    // Switch to YouTube and submit
    fireEvent.click(screen.getByRole('button', { name: /youtube url/i }));
    fireEvent.change(screen.getByPlaceholderText(/e\.g\., Deep Learning 101/i), {
      target: { value: 'Quantum Mechanics' },
    });
    fireEvent.change(screen.getByPlaceholderText(/https:\/\/www\.youtube\.com\/watch\?v=\.\.\./i), {
      target: { value: 'https://www.youtube.com/watch?v=quantum101' },
    });
    fireEvent.click(screen.getByRole('button', { name: /start ingestion pipeline/i }));

    await waitFor(() => {
      expect(screen.getByTestId('upload-job-progress')).toBeInTheDocument();
    });

    // Visible per-stage error banner
    expect(
      screen.getByText(/Pipeline Error: Stage 'Misconceptions' Failed/i)
    ).toBeInTheDocument();
    expect(
      screen.getByText(/Provider call timed out after 30\.0s during misconception diagnosis/i)
    ).toBeInTheDocument();

    // Retry / Resume Analysis button
    const retryBtn = screen.getByRole('button', { name: /retry \/ resume analysis/i });
    expect(retryBtn).toBeInTheDocument();

    // Clicking retry triggers analyzeLecture with resume: true
    (lectureService.analyzeLecture as any).mockResolvedValueOnce({
      id: 'job-pipe-resumed',
      status: 'queued',
      progress_pct: 35,
    });

    fireEvent.click(retryBtn);

    await waitFor(() => {
      expect(lectureService.analyzeLecture).toHaveBeenCalledWith('lec-fail-1', { resume: true });
    });
  });
});
