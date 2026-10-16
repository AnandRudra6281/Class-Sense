import React from 'react';
import { FileSpreadsheet, Download, FileText, CheckCircle2, TrendingUp } from 'lucide-react';
import { Card, Badge, Button } from '../components/ui';
import { Report, Coordinates3D } from '../types';

export const ReportsView: React.FC = () => {
  const dummyReport: Report = {
    id: 'rep-1',
    lecture_id: 'lec-1',
    title: 'Pedagogical Quality Audit: Deep Learning 101',
    executive_summary: 'Overall lecture coherence scored high (84%). However, a significant cognitive bottleneck was identified during the multivariable chain rule segment between minutes 18 and 25.',
    confusion_density: 0.28,
    key_recommendations: [
      'Begin next session with a 5-minute visual review of Jacobians.',
      'Incorporate the factory assembly line analogy prior to mathematical proofs.',
      'Provide interactive slider widgets for visualizing matrix gradients.',
    ],
    metrics: {
      total_segments: 184,
      confusion_spikes: 3,
      avg_wpm: 138,
      hesitation_pause_count: 14,
    },
    export_format: 'pdf',
    coordinates: { x: 50.0, y: 28.0, z: 0.0 } as Coordinates3D,
  };

  return (
    <div className="space-y-6" data-testid="view-reports">
      <div className="flex flex-col md:flex-row md:items-center justify-between gap-4 pb-4 border-b border-slate-800">
        <div>
          <div className="flex items-center gap-2 mb-1">
            <span className="text-xs font-semibold tracking-wider text-indigo-400 uppercase">Export & Insights</span>
            <Badge variant="indigo" size="sm">Audit Complete</Badge>
          </div>
          <h1 className="text-2xl font-bold tracking-tight text-white flex items-center gap-2">
            <FileSpreadsheet className="w-6 h-6 text-indigo-400" />
            Pedagogy Reports & Interventions
          </h1>
          <p className="text-slate-400 text-sm mt-1">
            Executive summaries, quantitative metrics, and recommended teacher interventions.
          </p>
        </div>
        <div className="flex items-center gap-2">
          <Button variant="secondary" size="sm">
            <Download className="w-4 h-4 mr-1.5 inline" /> Export PDF
          </Button>
          <Button variant="secondary" size="sm">
            <FileText className="w-4 h-4 mr-1.5 inline" /> Export JSON
          </Button>
        </div>
      </div>

      <Card variant="glow" className="space-y-4">
        <div className="flex items-center justify-between">
          <h3 className="text-lg font-bold text-white">{dummyReport.title}</h3>
          <Badge variant="low" size="sm">Quality Score: 84/100</Badge>
        </div>

        <p className="text-slate-300 text-sm leading-relaxed">{dummyReport.executive_summary}</p>

        <div className="grid grid-cols-2 sm:grid-cols-4 gap-3 pt-2">
          <div className="p-3 bg-slate-950/60 rounded-xl border border-slate-800">
            <span className="text-[11px] text-slate-400 uppercase">Confusion Density</span>
            <div className="text-xl font-bold text-amber-400 mt-1">
              {Math.round(dummyReport.confusion_density * 100)}%
            </div>
          </div>
          <div className="p-3 bg-slate-950/60 rounded-xl border border-slate-800">
            <span className="text-[11px] text-slate-400 uppercase">Detected Spikes</span>
            <div className="text-xl font-bold text-rose-400 mt-1">3</div>
          </div>
          <div className="p-3 bg-slate-950/60 rounded-xl border border-slate-800">
            <span className="text-[11px] text-slate-400 uppercase">Average Speech Rate</span>
            <div className="text-xl font-bold text-slate-200 mt-1">138 WPM</div>
          </div>
          <div className="p-3 bg-slate-950/60 rounded-xl border border-slate-800">
            <span className="text-[11px] text-slate-400 uppercase">3D Coordinates</span>
            <div className="text-xs font-mono text-indigo-400 mt-2">
              ({dummyReport.coordinates.x}, {dummyReport.coordinates.y}, {dummyReport.coordinates.z})
            </div>
          </div>
        </div>

        <div className="space-y-2 pt-2">
          <h4 className="text-xs font-semibold text-slate-300 uppercase tracking-wider flex items-center gap-1.5">
            <TrendingUp className="w-4 h-4 text-emerald-400" /> Actionable Teacher Interventions
          </h4>
          <div className="space-y-2">
            {dummyReport.key_recommendations.map((rec, i) => (
              <div key={i} className="flex items-start gap-2.5 p-3 rounded-xl bg-slate-900 border border-slate-800 text-xs text-slate-200">
                <CheckCircle2 className="w-4 h-4 text-emerald-400 shrink-0 mt-0.5" />
                <span>{rec}</span>
              </div>
            ))}
          </div>
        </div>
      </Card>
    </div>
  );
};
