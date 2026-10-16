import React from 'react';
import { AlertOctagon, GitBranch } from 'lucide-react';
import { Card, Badge } from '../components/ui';
import { Misconception, Coordinates3D } from '../types';

export const MisconceptionsView: React.FC = () => {
  const dummyMisconceptions: Misconception[] = [
    {
      id: 'misc-1',
      confusion_id: 'conf-1',
      name: 'Confusing Local Derivative with Total Gradient',
      explanation: 'Students assume scalar partial derivative handles multi-dimensional tensor backpropagation automatically.',
      apparent_reason: 'Missing prerequisite in vector/matrix multivariable calculus.',
      severity: 'critical',
      cognitive_load_score: 8.8,
      coordinates: { x: 35.0, y: 88.0, z: 1.0 } as Coordinates3D,
    },
    {
      id: 'misc-2',
      confusion_id: 'conf-2',
      name: 'Conflating Learning Rate with Step Size',
      explanation: 'Students believe larger learning rates always guarantee faster monotonic loss decrease.',
      apparent_reason: 'Intuition from 1D linear systems wrongly applied to non-convex loss surfaces.',
      severity: 'high',
      cognitive_load_score: 7.2,
      coordinates: { x: 70.0, y: 65.0, z: 2.0 } as Coordinates3D,
    },
  ];

  return (
    <div className="space-y-6" data-testid="view-misconceptions">
      <div className="flex flex-col md:flex-row md:items-center justify-between gap-4 pb-4 border-b border-slate-800">
        <div>
          <div className="flex items-center gap-2 mb-1">
            <span className="text-xs font-semibold tracking-wider text-indigo-400 uppercase">Cognitive Diagnostics</span>
            <Badge variant="indigo" size="sm">Vector Root Traced</Badge>
          </div>
          <h1 className="text-2xl font-bold tracking-tight text-white flex items-center gap-2">
            <AlertOctagon className="w-6 h-6 text-rose-400" />
            Extracted Misconceptions & Root Causes
          </h1>
          <p className="text-slate-400 text-sm mt-1">
            Synthesized cognitive obstacles linked to ChromaDB prerequisite embeddings.
          </p>
        </div>
      </div>

      <div className="space-y-4">
        {dummyMisconceptions.map((m) => (
          <Card key={m.id} className="space-y-3">
            <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-2">
              <div className="flex items-center gap-2">
                <Badge variant={m.severity} size="sm">
                  {m.severity.toUpperCase()} SEVERITY
                </Badge>
                <h3 className="text-base font-semibold text-white">{m.name}</h3>
              </div>
              <Badge variant="default" size="sm">
                Coord: ({m.coordinates.x}, {m.coordinates.y}, {m.coordinates.z})
              </Badge>
            </div>

            <p className="text-slate-300 text-sm leading-relaxed">{m.explanation}</p>

            <div className="p-3 bg-slate-950/50 border border-slate-800/80 rounded-xl space-y-1">
              <span className="text-xs font-semibold text-amber-400 flex items-center gap-1">
                <GitBranch className="w-3.5 h-3.5" /> Root Prerequisite Gap:
              </span>
              <p className="text-xs text-slate-300">{m.apparent_reason}</p>
            </div>

            <div className="flex items-center justify-between text-xs text-slate-400 pt-1">
              <span>Cognitive Load Score: <strong className="text-white">{m.cognitive_load_score} / 10</strong></span>
              <span>Confusion Node ID: {m.confusion_id}</span>
            </div>
          </Card>
        ))}
      </div>
    </div>
  );
};
