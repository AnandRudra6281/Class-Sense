import { describe, it, expect, vi, beforeEach } from 'vitest';
import { request, ApiClientError } from '../api/client';

describe('API Client', () => {
  beforeEach(() => {
    vi.restoreAllMocks();
  });

  it('unpacks successful response envelope', async () => {
    const mockData = { id: 'job-123', status: 'running' };
    vi.spyOn(globalThis, 'fetch').mockResolvedValueOnce({
      ok: true,
      status: 200,
      json: async () => ({
        success: true,
        data: mockData,
        error: null,
        meta: { timestamp: '2026-10-16T12:00:00Z', request_id: 'req-1' },
      }),
    } as Response);

    const result = await request<typeof mockData>('/jobs/job-123');
    expect(result).toEqual(mockData);
  });

  it('throws ApiClientError when response envelope has success: false', async () => {
    vi.spyOn(globalThis, 'fetch').mockResolvedValueOnce({
      ok: false,
      status: 404,
      statusText: 'Not Found',
      json: async () => ({
        success: false,
        data: null,
        error: {
          code: 'JOB_NOT_FOUND',
          message: "Job with ID 'missing' was not found.",
        },
        meta: { timestamp: '2026-10-16T12:00:00Z', request_id: 'req-2' },
      }),
    } as Response);

    await expect(request('/jobs/missing')).rejects.toThrowError(ApiClientError);
  });
});
