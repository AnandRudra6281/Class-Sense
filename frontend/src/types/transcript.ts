import { Coordinates3D } from './common';

export interface WordTimestamp {
  word: string;
  start: number;
  end: number;
  probability?: number | null;
}

export interface TranscriptSegment {
  id: string;
  lecture_id: string;
  start_time: number;
  end_time: number;
  text: string;
  speaker?: string | null;
  words: WordTimestamp[];
  coordinates: Coordinates3D;
}

export interface TranscriptionResult {
  text: string;
  duration_seconds: number;
  language: string;
  segments: TranscriptSegment[];
  words: WordTimestamp[];
}
