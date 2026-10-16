import { JobStatus } from './common';

export interface JobCreate {
  job_type: string;
  payload?: Record<string, unknown>;
}

export interface JobResponse {
  id: string;
  job_type: string;
  status: JobStatus;
  progress_pct: number;
  error_message?: string | null;
  payload?: Record<string, unknown> | null;
  result?: Record<string, unknown> | null;
  created_at: string;
  updated_at: string;
}
