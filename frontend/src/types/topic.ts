import { Coordinates3D } from './common';

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
