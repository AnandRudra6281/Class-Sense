import React from 'react';
import { Brain, Cpu, Compass, ArrowRight } from 'lucide-react';
import { Card, Badge, Button, Alert } from '../components/ui';
import { Coordinates3D } from '../types';

interface LandingViewProps {
  onNavigate?: (view: string) => void;
}

export const LandingView: React.FC<LandingViewProps> = ({ onNavigate }) => {
  const sampleCoordinates: Coordinates3D = { x: 0.0, y: 0.0, z: 1.0 };

  return (
    <div className="space-y-6" data-testid="view-landing">
      <div className="flex flex-col md:flex-row md:items-center justify-between gap-4 pb-4 border-b border-slate-800">
        <div>
          <div className="flex items-center gap-2 mb-1">
            <span className="text-xs font-semibold tracking-wider text-indigo-400 uppercase">Architecture Overview</span>
            <Badge variant="indigo" size="sm">Phase 0</Badge>
          </div>
          <h1 className="text-3xl font-extrabold tracking-tight text-white">ClassSense AI Teaching Assistant</h1>
          <p className="text-slate-400 text-sm mt-1">
            Locate lecture struggle points, trace prerequisite gaps via vector retrieval, and generate actionable teacher interventions.
          </p>
        </div>
        <div className="flex items-center gap-2">
          <Badge variant="default" size="md">
            Coord: ({sampleCoordinates.x.toFixed(1)}, {sampleCoordinates.y.toFixed(1)}, {sampleCoordinates.z.toFixed(1)})
          </Badge>
          {onNavigate && (
            <Button variant="primary" size="md" onClick={() => onNavigate('dashboard')}>
              Go to Dashboard <ArrowRight className="w-4 h-4 ml-1 inline" />
            </Button>
          )}
        </div>
      </div>

      <Alert severity="medium" title="Platform Pipeline Ready">
        ClassSense architecture connects Ingestion &rarr; Audio Extraction &rarr; ASR Word Timestamps &rarr; Topic Segmentation &rarr; Confusion Signal Engine &rarr; Prerequisite Vector Graph &rarr; Socratic Catch-Up.
      </Alert>

      <div className="grid grid-cols-1 md:grid-cols-3 gap-5">
        <Card variant="glow" className="space-y-3">
          <div className="w-10 h-10 rounded-lg bg-indigo-950 border border-indigo-800 flex items-center justify-center text-indigo-400">
            <Brain className="w-5 h-5" />
          </div>
          <h3 className="text-lg font-semibold text-white">Multimodal Pipeline</h3>
          <p className="text-slate-400 text-xs leading-relaxed">
            Ingest lectures via local video/audio or YouTube URL, segmenting transcripts with millisecond-accurate word timestamps.
          </p>
          <div className="pt-2">
            <Badge variant="low">Acoustic & Semantic</Badge>
          </div>
        </Card>

        <Card variant="default" className="space-y-3">
          <div className="w-10 h-10 rounded-lg bg-cyan-950 border border-cyan-800 flex items-center justify-center text-cyan-400">
            <Cpu className="w-5 h-5" />
          </div>
          <h3 className="text-lg font-semibold text-white">Pluggable AI Adapters</h3>
          <p className="text-slate-400 text-xs leading-relaxed">
            Strict provider abstractions for ASR, LLM, and Embeddings supporting Mistral API, Gemini API, and local Whisper fallback.
          </p>
          <div className="pt-2">
            <Badge variant="medium">Provider ABCs</Badge>
          </div>
        </Card>

        <Card variant="default" className="space-y-3">
          <div className="w-10 h-10 rounded-lg bg-emerald-950 border border-emerald-800 flex items-center justify-center text-emerald-400">
            <Compass className="w-5 h-5" />
          </div>
          <h3 className="text-lg font-semibold text-white">3D Pedagogical Space</h3>
          <p className="text-slate-400 text-xs leading-relaxed">
            Deterministic coordinates (x: time %, y: confusion %, z: topic depth) on every domain entity for future Three.js spatial graph.
          </p>
          <div className="pt-2">
            <Badge variant="low">Deterministic (x, y, z)</Badge>
          </div>
        </Card>
      </div>
    </div>
  );
};
