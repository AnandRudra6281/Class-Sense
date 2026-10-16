export interface Coordinates3D {
  x: number; // time position [0.0 - 100.0]
  y: number; // confusion score [0.0 - 100.0]
  z: number; // topic depth [0.0 - 10.0]
}

export interface ApiError {
  code: string;
  message: string;
  details?: unknown;
}

export interface ApiMeta {
  timestamp: string;
  request_id: string;
  duration_ms?: number;
}

export interface ApiResponse<T> {
  success: boolean;
  data: T | null;
  error: ApiError | null;
  meta: ApiMeta;
}

export type JobStatus = 'queued' | 'running' | 'failed' | 'done';
