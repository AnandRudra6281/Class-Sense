import React from 'react';
import { BookOpen, Video, Clock, CheckCircle2, ChevronRight } from 'lucide-react';
import { Card, Badge, Button } from '../components/ui';
import { Lecture, Coordinates3D } from '../types';

export const LibraryView: React.FC = () => {
  const dummyLectures: Partial<Lecture>[] = [
    {
      id: 'lec-1',
      title: 'Deep Learning 101: Backpropagation & Chain Rule',
      source_type: 'upload',
      duration_seconds: 3240,
      status: 'ready',
      coordinates: { x: 25.0, y: 40.0, z: 1.0 } as Coordinates3D,
      created_at: '2026-10-15T10:00:00Z',
    },
    {
      id: 'lec-2',
      title: 'Attention Mechanisms and Transformer Architecture',
      source_type: 'youtube',
      duration_seconds: 4800,
      status: 'ready',
      coordinates: { x: 60.0, y: 72.0, z: 2.5 } as Coordinates3D,
      created_at: '2026-10-14T14:30:00Z',
    },
    {
      id: 'lec-3',
      title: 'Eigenvalues, Eigenvectors and PCA Decomposition',
      source_type: 'upload',
      duration_seconds: 2700,
      status: 'ready',
      coordinates: { x: 10.0, y: 15.0, z: 0.5 } as Coordinates3D,
      created_at: '2026-10-13T09:15:00Z',
    },
  ];

  return (
    <div className="space-y-6" data-testid="view-library">
      <div className="flex flex-col md:flex-row md:items-center justify-between gap-4 pb-4 border-b border-slate-800">
        <div>
          <div className="flex items-center gap-2 mb-1">
            <span className="text-xs font-semibold tracking-wider text-indigo-400 uppercase">Archive</span>
            <Badge variant="indigo" size="sm">3 Ingested</Badge>
          </div>
          <h1 className="text-2xl font-bold tracking-tight text-white flex items-center gap-2">
            <BookOpen className="w-6 h-6 text-indigo-400" />
            Lecture Library
          </h1>
          <p className="text-slate-400 text-sm mt-1">
            Browse ingested lectures, view pedagogical coordinates, and access drill-down analytics.
          </p>
        </div>
      </div>

      <div className="grid grid-cols-1 gap-4">
        {dummyLectures.map((lec) => (
          <Card key={lec.id} variant="interactive" className="flex flex-col sm:flex-row sm:items-center justify-between gap-4">
            <div className="flex items-start gap-3.5">
              <div className="p-2.5 rounded-xl bg-slate-800/80 border border-slate-700/80 text-indigo-400">
                <Video className="w-5 h-5" />
              </div>
              <div className="space-y-1">
                <div className="flex items-center gap-2 flex-wrap">
                  <h4 className="font-semibold text-white text-base">{lec.title}</h4>
                  <Badge variant={lec.source_type === 'youtube' ? 'medium' : 'default'} size="sm">
                    {lec.source_type}
                  </Badge>
                  <Badge variant="low" size="sm" className="flex items-center gap-1">
                    <CheckCircle2 className="w-3 h-3" /> Ready
                  </Badge>
                </div>
                <div className="flex items-center gap-4 text-xs text-slate-400">
                  <span className="flex items-center gap-1">
                    <Clock className="w-3.5 h-3.5" />
                    {Math.round((lec.duration_seconds || 0) / 60)} mins
                  </span>
                  <span>
                    3D Coord: ({lec.coordinates?.x}, {lec.coordinates?.y}, {lec.coordinates?.z})
                  </span>
                </div>
              </div>
            </div>

            <div className="flex items-center gap-2 shrink-0">
              <Button variant="secondary" size="sm">
                Open Analysis <ChevronRight className="w-4 h-4 ml-1 inline" />
              </Button>
            </div>
          </Card>
        ))}
      </div>
    </div>
  );
};
