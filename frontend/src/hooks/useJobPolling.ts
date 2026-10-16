import { useEffect, useState, useCallback, useRef } from 'react';
import { JobResponse, JobStatus } from '../types';
import { jobService } from '../services/jobService';

interface UseJobPollingOptions {
  onSuccess?: (job: JobResponse) => void;
  onError?: (error: Error) => void;
  intervalMs?: number;
}

export function useJobPolling(jobId: string | null, options: UseJobPollingOptions = {}) {
  const [job, setJob] = useState<JobResponse | null>(null);
  const [status, setStatus] = useState<JobStatus | null>(null);
  const [progress, setProgress] = useState<number>(0);
  const [error, setError] = useState<string | null>(null);
  const [isPolling, setIsPolling] = useState<boolean>(false);

  const { onSuccess, onError, intervalMs = 1500 } = options;
  const isMountedRef = useRef<boolean>(true);

  useEffect(() => {
    isMountedRef.current = true;
    return () => {
      isMountedRef.current = false;
    };
  }, []);

  const poll = useCallback(async (id: string) => {
    setIsPolling(true);
    setError(null);

    try {
      const result = await jobService.pollUntilComplete(
        id,
        (currentJob) => {
          if (!isMountedRef.current) return;
          setJob(currentJob);
          setStatus(currentJob.status);
          setProgress(currentJob.progress_pct);
        },
        intervalMs
      );

      if (isMountedRef.current) {
        setJob(result);
        setStatus(result.status);
        setProgress(result.progress_pct);
        setIsPolling(false);
        if (onSuccess) onSuccess(result);
      }
    } catch (err: unknown) {
      if (isMountedRef.current) {
        const errorMsg = err instanceof Error ? err.message : 'Job polling failed';
        setError(errorMsg);
        setIsPolling(false);
        if (onError && err instanceof Error) onError(err);
      }
    }
  }, [intervalMs, onError, onSuccess]);

  useEffect(() => {
    if (jobId) {
      poll(jobId);
    }
  }, [jobId, poll]);

  return { job, status, progress, error, isPolling, retry: () => jobId && poll(jobId) };
}
