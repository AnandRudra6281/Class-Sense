import { Coordinates3D } from './common';

export interface ConfusionSignals {
  wpm: number;
  wpm_anomaly_z: number;
  pause_density: number;
  disfluency_ratio: number;
  type_token_ratio: number;
  llm_friction_score: number;
  composite_score: number;
}

export interface PrerequisiteGap {
  id: string;
  confusion_id: string;
  concept_name: string;
  gap_description: string;
  depth: number;
  vector_distance: number;
  coordinates: Coordinates3D;
}

export interface ConfusionPoint {
  id: string;
  lecture_id: string;
  segment_id?: string | null;
  timestamp_start: number;
  timestamp_end: number;
  confusion_score: number; // 0.0 - 1.0
  misconception: string;
  evidence_text: string;
  signals: ConfusionSignals;
  coordinates: Coordinates3D;
  prerequisite_gaps?: PrerequisiteGap[];
}
