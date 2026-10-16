import { ApiResponse } from '../types';

const BASE_URL = import.meta.env.VITE_API_URL || '/api/v1';

export class ApiClientError extends Error {
  code: string;
  details?: unknown;
  status: number;

  constructor(message: string, code: string = 'API_ERROR', status: number = 500, details?: unknown) {
    super(message);
    this.name = 'ApiClientError';
    this.code = code;
    this.status = status;
    this.details = details;
  }
}

export async function request<T>(
  endpoint: string,
  options: RequestInit = {}
): Promise<T> {
  const url = `${BASE_URL}${endpoint.startsWith('/') ? endpoint : `/${endpoint}`}`;
  
  const headers = new Headers(options.headers || {});
  if (!headers.has('Content-Type') && !(options.body instanceof FormData)) {
    headers.set('Content-Type', 'application/json');
  }

  const response = await fetch(url, {
    ...options,
    headers,
  });

  let payload: ApiResponse<T>;
  try {
    payload = await response.json();
  } catch (err) {
    throw new ApiClientError(
      `Failed to parse response from server (${response.status} ${response.statusText})`,
      'PARSE_ERROR',
      response.status
    );
  }

  if (!response.ok || !payload.success) {
    const errorDetail = payload.error || {
      code: `HTTP_${response.status}`,
      message: response.statusText || 'Unknown server error',
    };
    throw new ApiClientError(
      errorDetail.message,
      errorDetail.code,
      response.status,
      errorDetail.details
    );
  }

  return payload.data as T;
}
