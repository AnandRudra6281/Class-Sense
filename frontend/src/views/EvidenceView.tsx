import React from 'react';
import { FileSearch } from 'lucide-react';
import { Card, Badge, Alert } from '../components/ui';
import { Evidence, Coordinates3D } from '../types';

export const EvidenceView: React.FC = () => {
  const dummyEvidence: Evidence[] = [
    {
      id: 'evi-1',
      confusion_id: 'conf-1',
      quote: "...and now we calculate the derivative of the activation with respect to... wait, no, the weights...",
      signal_type: 'disfluency',
      confidence: 0.92,
      timestamp_start: 1120.5,
      timestamp_end: 1128.2,
      coordinates: { x: 34.5, y: 88.0, z: 1.0 } as Coordinates3D,
    },
    {
      id: 'evi-2',
      confusion_id: 'conf-1',
      quote: "Words-per-minute dropped from baseline 142 WPM to 78 WPM accompanied by repeated 3.2s hesitation pause.",
      signal_type: 'acoustic_wpm',
      confidence: 0.85,
      timestamp_start: 1130.0,
      timestamp_end: 1145.0,
      coordinates: { x: 35.0, y: 75.0, z: 1.0 } as Coordinates3D,
    },
    {
      id: 'evi-3',
      confusion_id: 'conf-2',
      quote: "Circular definition detected: 'Loss minimizes error which comes from the loss function'.",
      signal_type: 'semantic',
      confidence: 0.89,
      timestamp_start: 1840.0,
      timestamp_end: 1855.0,
      coordinates: { x: 56.8, y: 64.0, z: 2.0 } as Coordinates3D,
    },
  ];

  return (
    <div className="space-y-6" data-testid="view-evidence">
      <div className="flex flex-col md:flex-row md:items-center justify-between gap-4 pb-4 border-b border-slate-800">
        <div>
          <div className="flex items-center gap-2 mb-1">
            <span className="text-xs font-semibold tracking-wider text-indigo-400 uppercase">Signals & Proof</span>
            <Badge variant="indigo" size="sm">Empirical Grounds</Badge>
          </div>
          <h1 className="text-2xl font-bold tracking-tight text-white flex items-center gap-2">
            <FileSearch className="w-6 h-6 text-indigo-400" />
            Confusion Signal Evidence
          </h1>
          <p className="text-slate-400 text-sm mt-1">
            Multi-modal justification (speech rate, disfluency markers, acoustic pauses, semantic circularity).
          </p>
        </div>
      </div>

      <Alert severity="medium" title="Rigorous Evidence Engine">
        All signals correspond to empirical speech and transcript indicators documented in docs/CONFUSION_METHOD.md.
      </Alert>

      <div className="space-y-4">
        {dummyEvidence.map((evi) => (
          <Card key={evi.id} className="space-y-3">
            <div className="flex items-center justify-between">
              <div className="flex items-center gap-2">
                <Badge variant={evi.signal_type === 'disfluency' ? 'critical' : 'medium'} size="sm">
                  {evi.signal_type.toUpperCase()}
                </Badge>
                <span className="text-xs text-slate-400">
                  Confidence: <span className="font-semibold text-white">{Math.round(evi.confidence * 100)}%</span>
                </span>
              </div>
              <Badge variant="default" size="sm">
                Coord: ({evi.coordinates.x.toFixed(1)}, {evi.coordinates.y.toFixed(1)}, {evi.coordinates.z.toFixed(1)})
              </Badge>
            </div>

            <blockquote className="border-l-2 border-indigo-500 pl-3 py-1 italic text-slate-200 text-sm bg-slate-950/30 rounded-r-lg">
              "{evi.quote}"
            </blockquote>

            <div className="flex items-center justify-between text-xs text-slate-400">
              <span>Time: {evi.timestamp_start.toFixed(1)}s &rarr; {evi.timestamp_end.toFixed(1)}s</span>
              <span>Linked Confusion ID: {evi.confusion_id}</span>
            </div>
          </Card>
        ))}
      </div>
    </div>
  );
};
