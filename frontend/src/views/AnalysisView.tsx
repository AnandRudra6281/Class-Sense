import React from 'react';
import { BarChart3, Clock } from 'lucide-react';
import { Card, Badge, Progress } from '../components/ui';
import { Topic, Coordinates3D } from '../types';

export const AnalysisView: React.FC = () => {
  const sampleTopics: Topic[] = [
    {
      id: 'top-1',
      lecture_id: 'lec-1',
      title: 'Introduction to Multivariable Gradients',
      summary: 'Foundation of partial derivatives and Jacobian matrices.',
      start_time: 0,
      end_time: 720,
      depth: 0,
      coordinates: { x: 10.0, y: 15.0, z: 0.0 } as Coordinates3D,
    },
    {
      id: 'top-2',
      lecture_id: 'lec-1',
      title: 'Backpropagation Algorithm Derivation',
      summary: 'Applying recursive chain rule backward through computational graph.',
      start_time: 720,
      end_time: 2100,
      depth: 1,
      coordinates: { x: 45.0, y: 78.0, z: 1.0 } as Coordinates3D,
    },
    {
      id: 'top-3',
      lecture_id: 'lec-1',
      title: 'Stochastic vs Batch Gradient Updates',
      summary: 'Variance and convergence trade-offs in minibatch optimization.',
      start_time: 2100,
      end_time: 3240,
      depth: 1,
      coordinates: { x: 80.0, y: 35.0, z: 1.0 } as Coordinates3D,
    },
  ];

  return (
    <div className="space-y-6" data-testid="view-analysis">
      <div className="flex flex-col md:flex-row md:items-center justify-between gap-4 pb-4 border-b border-slate-800">
        <div>
          <div className="flex items-center gap-2 mb-1">
            <span className="text-xs font-semibold tracking-wider text-indigo-400 uppercase">Analysis</span>
            <Badge variant="indigo" size="sm">Topic Segmentation</Badge>
          </div>
          <h1 className="text-2xl font-bold tracking-tight text-white flex items-center gap-2">
            <BarChart3 className="w-6 h-6 text-indigo-400" />
            Lecture Timeline & Topic Hierarchy
          </h1>
          <p className="text-slate-400 text-sm mt-1">
            Word-aligned segments organized hierarchically with deterministic 3D pedagogical coordinates.
          </p>
        </div>
      </div>

      <div className="space-y-4">
        {sampleTopics.map((topic, idx) => (
          <Card key={topic.id} className="space-y-3">
            <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-2">
              <div className="flex items-center gap-2">
                <span className="w-6 h-6 rounded-md bg-indigo-950 border border-indigo-800 text-indigo-400 text-xs font-bold flex items-center justify-center">
                  {idx + 1}
                </span>
                <h3 className="text-base font-semibold text-white">{topic.title}</h3>
                <Badge variant={topic.coordinates.y > 60 ? 'critical' : 'medium'} size="sm">
                  {topic.coordinates.y > 60 ? 'Spike Detected' : 'Normal Pace'}
                </Badge>
              </div>

              <div className="flex items-center gap-2 text-xs text-slate-400">
                <span className="flex items-center gap-1">
                  <Clock className="w-3.5 h-3.5" />
                  {Math.floor(topic.start_time / 60)}m - {Math.floor(topic.end_time / 60)}m
                </span>
                <Badge variant="default" size="sm">
                  Coord: ({topic.coordinates.x}, {topic.coordinates.y}, {topic.coordinates.z})
                </Badge>
              </div>
            </div>

            <p className="text-slate-300 text-xs">{topic.summary}</p>

            <div className="pt-2">
              <Progress
                value={topic.coordinates.y}
                label={`Topic Confusion Density: ${topic.coordinates.y}%`}
                severity={topic.coordinates.y > 60 ? 'critical' : 'low'}
              />
            </div>
          </Card>
        ))}
      </div>
    </div>
  );
};
