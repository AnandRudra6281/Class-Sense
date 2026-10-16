// 3D Cartesian coordinates for pedagogical spatial visualization
export interface Coordinates3D {
  x: number; // time position [0.0 - 100.0]
  y: number; // confusion score [0.0 - 100.0]
  z: number; // topic depth [0.0 - 10.0]
}

export type SeverityLevel = 'low' | 'medium' | 'high' | 'critical';

export type ViewId =
  | 'landing'
  | 'dashboard'
  | 'library'
  | 'upload'
  | 'analysis'
  | 'evidence'
  | 'misconceptions'
  | 'student'
  | 'reports'
  | 'settings';

export type JobStatus = 'queued' | 'running' | 'failed' | 'done';

// 1. Lecture
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

// 2. Job
export interface Job {
  id: string;
  job_type: string;
  status: JobStatus;
  progress_pct: number;
  error_message?: string | null;
  payload?: Record<string, unknown> | null;
  result?: Record<string, unknown> | null;
  coordinates: Coordinates3D;
  created_at: string;
  updated_at: string;
}

// 3. TranscriptSegment
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

// 4. Topic
export interface Topic {
  id: string;
  lecture_id: string;
  parent_id?: string | null;
  title: string;
  summary: string;
  start_time: number;
  end_time: number;
  depth: number;
  coordinates: Coordinates3D;
  subtopics?: Topic[];
}

// 5. ConfusionEvent
export interface ConfusionEvent {
  id: string;
  lecture_id: string;
  segment_id?: string | null;
  timestamp_start: number;
  timestamp_end: number;
  confusion_score: number; // 0.0 - 1.0
  misconception_text: string;
  evidence_text: string;
  signals: Record<string, unknown>;
  coordinates: Coordinates3D;
}

// 6. Evidence
export interface Evidence {
  id: string;
  confusion_id: string;
  quote: string;
  signal_type: 'acoustic_wpm' | 'pause_density' | 'disfluency' | 'semantic' | string;
  confidence: number;
  timestamp_start: number;
  timestamp_end: number;
  coordinates: Coordinates3D;
}

// 7. Misconception
export interface Misconception {
  id: string;
  confusion_id: string;
  name: string;
  explanation: string;
  apparent_reason: string;
  severity: SeverityLevel;
  cognitive_load_score: number;
  coordinates: Coordinates3D;
}

// 8. PrerequisiteNode
export interface PrerequisiteNode {
  id: string;
  confusion_id: string;
  concept_name: string;
  gap_description: string;
  remediation_hint: string;
  depth: number;
  vector_distance: number;
  coordinates: Coordinates3D;
}

// 9. Intervention
export interface DiagnosticQuestion {
  question: string;
  options: string[];
  correct_option_index: number;
  rationale: string;
}

export interface Intervention {
  id: string;
  lecture_id: string;
  target_type: 'teacher' | 'student';
  title: string;
  content: Record<string, unknown>;
  coordinates: Coordinates3D;
}

// 10. StudentCatchUp
export interface StudentCatchUp {
  id: string;
  lecture_id: string;
  topic_id?: string | null;
  title: string;
  summary: string;
  concrete_analogy: string;
  key_takeaways: string[];
  quiz_questions?: QuizQuestion[];
  coordinates: Coordinates3D;
}

// 11. QuizQuestion
export interface PracticeHint {
  step: number;
  hint: string;
}

export interface QuizQuestion {
  id: string;
  catchup_id: string;
  question: string;
  options: string[];
  correct_option_index: number;
  hints: PracticeHint[];
  explanation: string;
  coordinates: Coordinates3D;
}

// Socratic Tutor & CatchUp DTOs
export interface TutorChatMessage {
  role: 'user' | 'assistant';
  content: string;
}

export interface TutorChatRequest {
  message: string;
  history?: TutorChatMessage[];
  catchup_id?: string;
}

export interface TutorChatResponse {
  reply: string;
  suggested_followups: string[];
  grounded_timestamp?: number | null;
  coordinates: Coordinates3D;
}

export interface StudentCatchUpJobResponse {
  job_id: string;
  lecture_id: string;
  status: string;
  progress_pct?: number;
}

// 12. Report
export interface Report {
  id: string;
  lecture_id: string;
  title: string;
  executive_summary: string;
  confusion_density: number;
  key_recommendations: string[];
  metrics: Record<string, unknown>;
  export_format: string;
  coordinates: Coordinates3D;
  created_at?: string;
  updated_at?: string;
}

export interface ReportExportResponse {
  report_id: string;
  lecture_id: string;
  format: string;
  content: string;
  filename: string;
}

// Job DTOs
export interface JobCreate {
  job_type: string;
  payload?: Record<string, unknown>;
}

export type JobResponse = Job;

// Composite / Aggregate views
export interface ConfusionPoint {
  id: string;
  lecture_id: string;
  segment_id?: string | null;
  timestamp_start: number;
  timestamp_end: number;
  confusion_score: number;
  misconception: string;
  evidence_text: string;
  signals: Record<string, unknown>;
  coordinates: Coordinates3D;
  prerequisite_gaps?: PrerequisiteNode[];
}

export interface LectureDetail extends Lecture {
  segments: TranscriptSegment[];
  topics: Topic[];
  confusion_points: ConfusionPoint[];
  interventions: Intervention[];
}

