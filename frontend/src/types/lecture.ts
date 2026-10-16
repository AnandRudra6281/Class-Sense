import { Coordinates3D } from './common';
import { TranscriptSegment } from './transcript';
import { Topic } from './topic';
import { ConfusionPoint } from './confusion';
import { Intervention } from './intervention';

export interface Lecture {
  id: string;
  title: string;
  source_type: 'upload' | 'youtube';
  source_url?: string | null;
  media_path?: string | null;
  audio_path?: string | null;
  duration_seconds: number;
  status: string;
  coordinates: Coordinates3D;
  created_at: string;
  updated_at: string;
}

export interface LectureDetail extends Lecture {
  segments: TranscriptSegment[];
  topics: Topic[];
  confusion_points: ConfusionPoint[];
  interventions: Intervention[];
}
