import React from 'react';
import { LayoutDashboard, AlertTriangle, CheckCircle2, Clock, BookOpen } from 'lucide-react';
import { Card, Badge, Progress, Alert } from '../components/ui';
import { Coordinates3D } from '../types';

export const DashboardView: React.FC = () => {
  const coordinates: Coordinates3D = { x: 50.0, y: 35.0, z: 2.0 };

  return (
    <div className="space-y-6" data-testid="view-dashboard">
      <div className="flex flex-col md:flex-row md:items-center justify-between gap-4 pb-4 border-b border-slate-800">
        <div>
          <div className="flex items-center gap-2 mb-1">
            <span className="text-xs font-semibold tracking-wider text-indigo-400 uppercase">Executive Overview</span>
            <Badge variant="indigo" size="sm">Active Session</Badge>
          </div>
          <h1 className="text-2xl font-bold tracking-tight text-white flex items-center gap-2">
            <LayoutDashboard className="w-6 h-6 text-indigo-400" />
            Instructor Cockpit
          </h1>
          <p className="text-slate-400 text-sm mt-1">
            Real-time analytics across lecture confusion spikes, topic comprehension, and student remediation.
          </p>
        </div>
        <div>
          <Badge variant="default">
            Center Coord: ({coordinates.x.toFixed(1)}, {coordinates.y.toFixed(1)}, {coordinates.z.toFixed(1)})
          </Badge>
        </div>
      </div>

      <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4">
        <Card className="space-y-2">
          <div className="flex items-center justify-between text-xs text-slate-400">
            <span>Processed Lectures</span>
            <BookOpen className="w-4 h-4 text-indigo-400" />
          </div>
          <div className="text-2xl font-bold text-white">12</div>
          <div className="flex items-center gap-1.5 text-xs text-emerald-400">
            <CheckCircle2 className="w-3.5 h-3.5" />
            <span>100% ingested</span>
          </div>
        </Card>

        <Card className="space-y-2">
          <div className="flex items-center justify-between text-xs text-slate-400">
            <span>Critical Confusion Points</span>
            <AlertTriangle className="w-4 h-4 text-rose-400" />
          </div>
          <div className="text-2xl font-bold text-rose-400">7</div>
          <Badge variant="critical" size="sm">Requires Action</Badge>
        </Card>

        <Card className="space-y-2">
          <div className="flex items-center justify-between text-xs text-slate-400">
            <span>Mean Confusion Density</span>
            <Clock className="w-4 h-4 text-amber-400" />
          </div>
          <div className="text-2xl font-bold text-amber-400">32.4%</div>
          <Badge variant="medium" size="sm">Moderate</Badge>
        </Card>

        <Card className="space-y-2">
          <div className="flex items-center justify-between text-xs text-slate-400">
            <span>Prerequisite Resolution</span>
            <CheckCircle2 className="w-4 h-4 text-emerald-400" />
          </div>
          <div className="text-2xl font-bold text-emerald-400">89%</div>
          <Badge variant="low" size="sm">Healthy</Badge>
        </Card>
      </div>

      <Card className="space-y-4">
        <h3 className="text-base font-semibold text-white">Pipeline Execution Status</h3>
        <div className="space-y-3">
          <Progress value={100} label="Acoustic & Semantic Signal Ingestion" severity="low" />
          <Progress value={65} label="Vector Knowledge Graph Traversal" severity="medium" />
          <Progress value={40} label="Socratic Practice Synthesis" severity="high" />
        </div>
      </Card>

      <Alert severity="high" title="Attention Recommended: Backpropagation Lecture">
        Detected 3 high-severity confusion clusters between timestamps 18:20 and 24:10 due to prerequisite gaps in Matrix Calculus.
      </Alert>
    </div>
  );
};
