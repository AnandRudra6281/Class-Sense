import { request } from '../api/client';
import { Lecture, LectureDetail } from '../types';

export interface CreateLecturePayload {
  title: string;
  source_type: 'upload' | 'youtube';
  source_url?: string;
}

export const lectureService = {
  async listLectures(): Promise<Lecture[]> {
    return request<Lecture[]>('/lectures');
  },

  async getLectureDetail(lectureId: string): Promise<LectureDetail> {
    return request<LectureDetail>(`/lectures/${lectureId}`);
  },

  async createLecture(payload: CreateLecturePayload): Promise<Lecture> {
    return request<Lecture>('/lectures', {
      method: 'POST',
      body: JSON.stringify(payload),
    });
  },
};
