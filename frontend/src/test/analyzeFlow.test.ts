import { describe, it, expect, vi, beforeEach } from 'vitest';
import { lectureService } from '../services/lectureService';
import { ApiClientError } from '../api/client';

describe('lectureService analyze flow tests', () => {
  beforeEach(() => {
    vi.restoreAllMocks();
  });

  it('triggers POST /lectures/:id/analyze with resume=false by default', async () => {
    const mockJob = {
      id: 'job-analyze-101',
      job_type: 'lecture_pipeline',
      status: 'queued',
      progress_pct: 0,
      payload: { lecture_id: 'lec-101', resume: false },
    };

    const fetchSpy = vi.spyOn(globalThis, 'fetch').mockResolvedValueOnce({
      ok: true,
      status: 200,
      json: async () => ({
        success: true,
        data: mockJob,
        error: null,
      }),
    } as Response);

    const result = await lectureService.analyzeLecture('lec-101');

    expect(fetchSpy).toHaveBeenCalledWith(
      '/api/v1/lectures/lec-101/analyze',
      expect.objectContaining({
        method: 'POST',
      })
    );
    expect(result).toEqual(mockJob);
  });

  it('triggers POST /lectures/:id/analyze?resume=true when resume option is true', async () => {
    const mockJob = {
      id: 'job-analyze-102',
      job_type: 'lecture_pipeline',
      status: 'queued',
      progress_pct: 40,
      payload: { lecture_id: 'lec-102', resume: true },
    };

    const fetchSpy = vi.spyOn(globalThis, 'fetch').mockResolvedValueOnce({
      ok: true,
      status: 200,
      json: async () => ({
        success: true,
        data: mockJob,
        error: null,
      }),
    } as Response);

    const result = await lectureService.analyzeLecture('lec-102', { resume: true });

    expect(fetchSpy).toHaveBeenCalledWith(
      '/api/v1/lectures/lec-102/analyze?resume=true',
      expect.objectContaining({
        method: 'POST',
      })
    );

    expect(result).toEqual(mockJob);
  });

  it('propagates ApiClientError when active job conflict (409) occurs', async () => {
    vi.spyOn(globalThis, 'fetch').mockResolvedValueOnce({
      ok: false,
      status: 409,
      statusText: 'Conflict',
      json: async () => ({
        success: false,
        data: null,
        error: {
          code: 'JOB_ALREADY_ACTIVE',
          message: "An analysis job is already active (running) for lecture 'lec-103'.",
        },
      }),
    } as Response);

    await expect(lectureService.analyzeLecture('lec-103')).rejects.toThrowError(
      ApiClientError
    );
  });
});
