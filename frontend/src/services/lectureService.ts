import { request } from '../api/client';
import {
  ConfusionEvent,
  Evidence,
  Intervention,
  Lecture,
  LectureDetail,
  Misconception,
  PrerequisiteNode,
  StudentCatchUp,
  Topic,
  TranscriptSegment,
  TutorChatMessage,
  TutorChatResponse,
} from '../types';

export interface IngestJobResponse {
  lecture_id: string;
  job_id: string;
  status: string;
  title: string;
}

export interface YouTubeIngestPayload {
  url: string;
  title?: string;
}

export interface CreateLecturePayload {
  title: string;
  source_type: 'upload' | 'youtube';
  source_url?: string;
}

export interface JobTriggerResponse {
  job_id: string;
  lecture_id: string;
  status: string;
}

export const lectureService = {
  async listLectures(): Promise<Lecture[]> {
    return request<Lecture[]>('/lectures');
  },

  async getLectureDetail(lectureId: string): Promise<LectureDetail> {
    return request<LectureDetail>(`/lectures/${lectureId}`);
  },

  async uploadLectureMedia(file: File, title?: string): Promise<IngestJobResponse> {
    const formData = new FormData();
    formData.append('file', file);
    if (title && title.trim()) {
      formData.append('title', title.trim());
    }

    return request<IngestJobResponse>('/lectures/upload', {
      method: 'POST',
      body: formData,
    });
  },

  async ingestYouTubeLecture(payload: YouTubeIngestPayload): Promise<IngestJobResponse> {
    return request<IngestJobResponse>('/lectures/youtube', {
      method: 'POST',
      body: JSON.stringify(payload),
    });
  },

  async deleteLecture(lectureId: string): Promise<{ deleted: boolean; lecture_id: string }> {
    return request<{ deleted: boolean; lecture_id: string }>(`/lectures/${lectureId}`, {
      method: 'DELETE',
    });
  },

  async createLecture(payload: CreateLecturePayload): Promise<Lecture> {
    return request<Lecture>('/lectures', {
      method: 'POST',
      body: JSON.stringify(payload),
    });
  },

  async transcribeLecture(
    lectureId: string,
    provider: string = 'auto',
    language?: string
  ): Promise<JobTriggerResponse> {
    return request<JobTriggerResponse>(
      `/lectures/${lectureId}/transcribe`,
      {
        method: 'POST',
        body: JSON.stringify({ provider, language }),
      }
    );
  },

  async getTranscript(lectureId: string): Promise<TranscriptSegment[]> {
    return request<TranscriptSegment[]>(`/lectures/${lectureId}/transcript`);
  },

  async segmentTopics(lectureId: string): Promise<JobTriggerResponse> {
    return request<JobTriggerResponse>(`/lectures/${lectureId}/segment-topics`, {
      method: 'POST',
    });
  },

  async getTopics(lectureId: string): Promise<Topic[]> {
    return request<Topic[]>(`/lectures/${lectureId}/topics`);
  },

  async analyzeSignals(lectureId: string): Promise<JobTriggerResponse> {
    return request<JobTriggerResponse>(`/lectures/${lectureId}/analyze-signals`, {
      method: 'POST',
    });
  },

  async getConfusionEvents(lectureId: string): Promise<ConfusionEvent[]> {
    return request<ConfusionEvent[]>(`/lectures/${lectureId}/confusion-events`);
  },

  async getEvidence(lectureId: string): Promise<Evidence[]> {
    return request<Evidence[]>(`/lectures/${lectureId}/evidence`);
  },

  async extractMisconceptions(lectureId: string): Promise<JobTriggerResponse> {
    return request<JobTriggerResponse>(`/lectures/${lectureId}/extract-misconceptions`, {
      method: 'POST',
    });
  },

  async getMisconceptions(lectureId: string): Promise<Misconception[]> {
    return request<Misconception[]>(`/lectures/${lectureId}/misconceptions`);
  },

  async tracePrerequisites(lectureId: string): Promise<JobTriggerResponse> {
    return request<JobTriggerResponse>(`/lectures/${lectureId}/trace-prerequisites`, {
      method: 'POST',
    });
  },

  async getPrerequisites(lectureId: string): Promise<PrerequisiteNode[]> {
    return request<PrerequisiteNode[]>(`/lectures/${lectureId}/prerequisites`);
  },

  async generateInterventions(lectureId: string): Promise<JobTriggerResponse> {
    return request<JobTriggerResponse>(`/lectures/${lectureId}/generate-interventions`, {
      method: 'POST',
    });
  },

  async getInterventions(lectureId: string, targetType?: string): Promise<Intervention[]> {
    const query = targetType ? `?target_type=${encodeURIComponent(targetType)}` : '';
    return request<Intervention[]>(`/lectures/${lectureId}/interventions${query}`);
  },

  async generateStudentCatchUp(lectureId: string): Promise<JobTriggerResponse> {
    return request<JobTriggerResponse>(`/lectures/${lectureId}/generate-catchup`, {
      method: 'POST',
    });
  },

  async getStudentCatchUp(lectureId: string): Promise<StudentCatchUp[]> {
    return request<StudentCatchUp[]>(`/lectures/${lectureId}/catchup`);
  },

  async sendTutorChatMessage(
    lectureId: string,
    message: string,
    history: TutorChatMessage[] = [],
    catchupId?: string
  ): Promise<TutorChatResponse> {
    return request<TutorChatResponse>(`/lectures/${lectureId}/tutor/chat`, {
      method: 'POST',
      body: JSON.stringify({
        message,
        history,
        catchup_id: catchupId || null,
      }),
    });
  },
};
