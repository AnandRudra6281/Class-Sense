import { request } from '../api/client';
import { JobCreate, JobResponse } from '../types';

export const jobService = {
  async getJob(jobId: string): Promise<JobResponse> {
    return request<JobResponse>(`/jobs/${jobId}`);
  },

  async createSimulatedJob(jobType: string, payload?: Record<string, unknown>): Promise<JobResponse> {
    return request<JobResponse>('/jobs/test-simulate', {
      method: 'POST',
      body: JSON.stringify({ job_type: jobType, payload } as JobCreate),
    });
  },

  async pollUntilComplete(
    jobId: string,
    onProgress?: (job: JobResponse) => void,
    intervalMs: number = 1000,
    timeoutMs: number = 60000
  ): Promise<JobResponse> {
    const startTime = Date.now();

    while (Date.now() - startTime < timeoutMs) {
      const job = await this.getJob(jobId);
      if (onProgress) {
        onProgress(job);
      }

      if (job.status === 'done') {
        return job;
      }
      if (job.status === 'failed') {
        throw new Error(job.error_message || 'Job execution failed');
      }

      await new Promise((resolve) => setTimeout(resolve, intervalMs));
    }

    throw new Error(`Polling timed out after ${timeoutMs}ms for job ${jobId}`);
  },
};
