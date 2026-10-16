import { Coordinates3D } from './common';

export interface DiagnosticQuestion {
  question: string;
  options: string[];
  correct_option_index: number;
  rationale: string;
}

export interface TeacherInterventionContent {
  actionable_recap: string[];
  diagnostic_questions: DiagnosticQuestion[];
  recommended_pacing: string;
}

export interface PracticeHint {
  step: number;
  hint: string;
}

export interface PracticeQuestion {
  question: string;
  hints: PracticeHint[];
  solution_explanation: string;
}

export interface StudentCatchUpContent {
  summary: string;
  concrete_analogy: string;
  practice_problems: PracticeQuestion[];
}

export interface Intervention {
  id: string;
  lecture_id: string;
  target_type: 'teacher' | 'student';
  title: string;
  content: TeacherInterventionContent | StudentCatchUpContent | Record<string, unknown>;
  coordinates: Coordinates3D;
}
