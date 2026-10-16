import React, { useState, useEffect, useCallback } from 'react';
import {
  FileSpreadsheet,
  Download,
  FileText,
  CheckCircle2,
  TrendingUp,
  Sparkles,
  RefreshCw,
  AlertCircle,
  Clock,
  AlertTriangle,
  Brain,
  Gauge,
  Calendar,
} from 'lucide-react';
import { Card, Badge, Button, Progress, Alert } from '../components/ui';
import { lectureService } from '../services/lectureService';
import { useJobPolling } from '../hooks/useJobPolling';
import { Lecture, Report } from '../types';

export const ReportsView: React.FC = () => {
  const [lectures, setLectures] = useState<Lecture[]>([]);
  const [selectedLectureId, setSelectedLectureId] = useState<string>('');
  const [loadingLectures, setLoadingLectures] = useState<boolean>(true);
  const [reports, setReports] = useState<Report[]>([]);
  const [loadingReports, setLoadingReports] = useState<boolean>(false);
  const [activeJobId, setActiveJobId] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [exportingFormat, setExportingFormat] = useState<string | null>(null);

  // Background Job Polling
  const { status: jobStatus, progress: jobProgress } = useJobPolling(activeJobId, {
    onSuccess: () => {
      if (selectedLectureId) {
        fetchReports(selectedLectureId);
      }
    },
    onError: (err: Error) => {
      setError(`Report generation failed: ${err.message}`);
    },
  });

  const fetchLectures = async () => {
    try {
      setLoadingLectures(true);
      setError(null);
      const data = await lectureService.listLectures();
      setLectures(data);
      if (data.length > 0 && !selectedLectureId) {
        setSelectedLectureId(data[0].id);
      }
    } catch (err: unknown) {
      setError(err instanceof Error ? err.message : 'Failed to load lectures.');
    } finally {
      setLoadingLectures(false);
    }
  };

  const fetchReports = useCallback(async (lectureId: string) => {
    try {
      setLoadingReports(true);
      setError(null);
      const data = await lectureService.getReports(lectureId);
      setReports(data);
    } catch (err: unknown) {
      setError(err instanceof Error ? err.message : 'Failed to load reports.');
    } finally {
      setLoadingReports(false);
    }
  }, []);

  useEffect(() => {
    fetchLectures();
  }, []);

  useEffect(() => {
    if (selectedLectureId) {
      fetchReports(selectedLectureId);
    }
  }, [selectedLectureId, fetchReports]);

  const handleGenerateReport = async () => {
    if (!selectedLectureId) return;
    try {
      setError(null);
      const res = await lectureService.generateReport(selectedLectureId);
      setActiveJobId(res.job_id);
    } catch (err: unknown) {
      setError(err instanceof Error ? err.message : 'Failed to launch report generation.');
    }
  };

  const handleExport = async (format: 'markdown' | 'json') => {
    if (!selectedLectureId || reports.length === 0) return;
    const currentReport = reports[0];
    try {
      setExportingFormat(format);
      setError(null);
      const res = await lectureService.exportReport(selectedLectureId, currentReport.id, format);

      // Trigger browser download
      const mimeType = format === 'json' ? 'application/json' : 'text/markdown';
      const blob = new Blob([res.content], { type: mimeType });
      const url = URL.createObjectURL(blob);
      const link = document.createElement('a');
      link.href = url;
      link.download = res.filename;
      document.body.appendChild(link);
      link.click();
      document.body.removeChild(link);
      URL.revokeObjectURL(url);
    } catch (err: unknown) {
      setError(err instanceof Error ? err.message : `Failed to export as ${format}.`);
    } finally {
      setExportingFormat(null);
    }
  };

  const isJobRunning = jobStatus === 'running' || jobStatus === 'queued';
  const latestReport = reports.length > 0 ? reports[0] : null;
  const metrics = (latestReport?.metrics || {}) as Record<string, any>;
  const qualityScore = metrics.pedagogy_quality_score ?? Math.round((1 - (latestReport?.confusion_density ?? 0.2)) * 100);

  return (
    <div className="space-y-6" data-testid="view-reports">
      {/* Top Header & Lecture Selector */}
      <div className="flex flex-col md:flex-row md:items-center justify-between gap-4 pb-4 border-b border-slate-800">
        <div>
          <div className="flex items-center gap-2 mb-1">
            <span className="text-xs font-semibold tracking-wider text-indigo-400 uppercase">Executive Audit Engine</span>
            <Badge variant="indigo" size="sm">Pedagogy Analytics</Badge>
          </div>
          <h1 className="text-2xl font-bold tracking-tight text-white flex items-center gap-2">
            <FileSpreadsheet className="w-6 h-6 text-indigo-400" />
            Pedagogy Reports & Analytics
          </h1>
          <p className="text-slate-400 text-sm mt-1">
            Data-driven executive audits, empirical speech pacing signals, cognitive density metrics, and strategic instructional recommendations.
          </p>
        </div>

        <div className="flex flex-wrap items-center gap-3">
          <select
            value={selectedLectureId}
            onChange={(e) => setSelectedLectureId(e.target.value)}
            disabled={loadingLectures || isJobRunning}
            className="bg-slate-900 border border-slate-700 text-slate-200 text-xs rounded-xl px-3 py-2 focus:ring-2 focus:ring-indigo-500 focus:outline-none"
            data-testid="reports-lecture-select"
          >
            {loadingLectures ? (
              <option>Loading lectures...</option>
            ) : lectures.length === 0 ? (
              <option>No lectures available</option>
            ) : (
              lectures.map((lec) => (
                <option key={lec.id} value={lec.id}>
                  {lec.title} ({Math.round(lec.duration_seconds)}s)
                </option>
              ))
            )}
          </select>

          <Button
            variant="primary"
            size="sm"
            onClick={handleGenerateReport}
            disabled={!selectedLectureId || isJobRunning}
            data-testid="generate-report-btn"
          >
            <Sparkles className="w-4 h-4 mr-1.5" />
            Synthesize Audit Report
          </Button>

          <Button
            variant="secondary"
            size="sm"
            onClick={() => selectedLectureId && fetchReports(selectedLectureId)}
            disabled={loadingReports}
            title="Refresh"
          >
            <RefreshCw className={`w-4 h-4 ${loadingReports ? 'animate-spin' : ''}`} />
          </Button>

          {latestReport && (
            <div className="flex items-center gap-2">
              <Button
                variant="secondary"
                size="sm"
                onClick={() => handleExport('markdown')}
                disabled={Boolean(exportingFormat)}
                data-testid="export-markdown-btn"
              >
                <Download className="w-3.5 h-3.5 mr-1" />
                {exportingFormat === 'markdown' ? 'Exporting...' : 'Export Markdown'}
              </Button>
              <Button
                variant="secondary"
                size="sm"
                onClick={() => handleExport('json')}
                disabled={Boolean(exportingFormat)}
                data-testid="export-json-btn"
              >
                <FileText className="w-3.5 h-3.5 mr-1" />
                {exportingFormat === 'json' ? 'Exporting...' : 'Export JSON'}
              </Button>
            </div>
          )}
        </div>
      </div>

      {/* Error alert */}
      {error && (
        <Alert severity="critical" title="Report Error">
          <AlertCircle className="w-4 h-4 mr-2 inline" />
          {error}
        </Alert>
      )}

      {/* Asynchronous Job Progress */}
      {isJobRunning && (
        <Card variant="default" className="border-indigo-500/40 bg-indigo-950/20 space-y-2">
          <div className="flex items-center justify-between text-xs font-semibold text-indigo-300">
            <span className="flex items-center gap-2">
              <Sparkles className="w-4 h-4 text-indigo-400 animate-pulse" />
              Synthesizing Pedagogy Audit Report & Empirical Metrics...
            </span>
            <span>{jobProgress}%</span>
          </div>
          <Progress value={jobProgress} />
          <p className="text-[11px] text-slate-400">
            Aggregating confusion signals, acoustic pacing anomalies, and root-cause prerequisite gaps into an executive quality audit.
          </p>
        </Card>
      )}

      {/* Main Content Area */}
      {loadingReports ? (
        <div className="py-16 text-center text-sm text-slate-400">
          <RefreshCw className="w-6 h-6 animate-spin mx-auto text-indigo-400 mb-2" />
          Loading quality audit report...
        </div>
      ) : !latestReport ? (
        <Card variant="default" className="text-center py-16 space-y-4">
          <FileSpreadsheet className="w-12 h-12 text-slate-600 mx-auto" />
          <div className="max-w-md mx-auto space-y-1">
            <h3 className="text-base font-bold text-white">No Audit Reports Synthesized Yet</h3>
            <p className="text-xs text-slate-400 leading-relaxed">
              Launch report synthesis above to generate an executive-level pedagogical audit, compute confusion density metrics, evaluate speech pacing, and extract actionable curriculum recommendations.
            </p>
          </div>
          <Button
            variant="primary"
            size="sm"
            onClick={handleGenerateReport}
            disabled={!selectedLectureId || isJobRunning}
          >
            <Sparkles className="w-4 h-4 mr-1.5" />
            Synthesize Audit Report Now
          </Button>
        </Card>
      ) : (
        <div className="space-y-6" data-testid="report-content">
          {/* Executive Report Card */}
          <Card variant="glow" className="space-y-6 p-6">
            <div className="flex flex-col md:flex-row md:items-center justify-between gap-3 pb-4 border-b border-slate-800">
              <div>
                <div className="flex items-center gap-2 mb-1.5">
                  <Badge variant="indigo" size="sm">Audited Deliverable</Badge>
                  <span className="text-xs text-slate-400 flex items-center gap-1">
                    <Calendar className="w-3.5 h-3.5" />
                    {latestReport.created_at ? new Date(latestReport.created_at).toLocaleDateString() : 'Active Session'}
                  </span>
                </div>
                <h2 className="text-xl font-bold text-white">{latestReport.title}</h2>
              </div>
              <div className="flex items-center gap-2">
                <Badge
                  variant={qualityScore >= 75 ? 'low' : qualityScore >= 50 ? 'medium' : 'critical'}
                  size="md"
                  className="text-xs font-semibold"
                >
                  Quality Score: {qualityScore}/100
                </Badge>
                <Badge variant="default" size="sm" className="font-mono text-[10px]">
                  Coord: ({latestReport.coordinates.x}, {latestReport.coordinates.y}, {latestReport.coordinates.z})
                </Badge>
              </div>
            </div>

            {/* KPI Metrics Grid */}
            <div className="grid grid-cols-2 sm:grid-cols-3 lg:grid-cols-6 gap-3">
              <div className="p-3.5 bg-slate-950/60 rounded-xl border border-slate-800 space-y-1">
                <div className="flex items-center justify-between text-[11px] text-slate-400 uppercase tracking-wider">
                  <span>Quality Score</span>
                  <Gauge className="w-3.5 h-3.5 text-indigo-400" />
                </div>
                <div className="text-2xl font-bold text-emerald-400">{qualityScore}%</div>
                <p className="text-[10px] text-slate-500">Benchmark: &gt; 75%</p>
              </div>

              <div className="p-3.5 bg-slate-950/60 rounded-xl border border-slate-800 space-y-1">
                <div className="flex items-center justify-between text-[11px] text-slate-400 uppercase tracking-wider">
                  <span>Confusion Density</span>
                  <AlertTriangle className="w-3.5 h-3.5 text-amber-400" />
                </div>
                <div className="text-2xl font-bold text-amber-400">
                  {Math.round(latestReport.confusion_density * 100)}%
                </div>
                <p className="text-[10px] text-slate-500">Friction vs Segments</p>
              </div>

              <div className="p-3.5 bg-slate-950/60 rounded-xl border border-slate-800 space-y-1">
                <div className="flex items-center justify-between text-[11px] text-slate-400 uppercase tracking-wider">
                  <span>Confusion Spikes</span>
                  <AlertCircle className="w-3.5 h-3.5 text-rose-400" />
                </div>
                <div className="text-2xl font-bold text-rose-400">
                  {metrics.confusion_spikes ?? 0}
                </div>
                <p className="text-[10px] text-slate-500">
                  Avg: {metrics.avg_confusion_score ? (metrics.avg_confusion_score * 100).toFixed(0) + '%' : '0%'}
                </p>
              </div>

              <div className="p-3.5 bg-slate-950/60 rounded-xl border border-slate-800 space-y-1">
                <div className="flex items-center justify-between text-[11px] text-slate-400 uppercase tracking-wider">
                  <span>Speech Rate</span>
                  <Clock className="w-3.5 h-3.5 text-cyan-400" />
                </div>
                <div className="text-2xl font-bold text-slate-200">
                  {metrics.avg_wpm ? `${Math.round(metrics.avg_wpm)}` : '135'}
                </div>
                <p className="text-[10px] text-slate-500">Words Per Minute</p>
              </div>

              <div className="p-3.5 bg-slate-950/60 rounded-xl border border-slate-800 space-y-1">
                <div className="flex items-center justify-between text-[11px] text-slate-400 uppercase tracking-wider">
                  <span>Hesitation Pauses</span>
                  <Clock className="w-3.5 h-3.5 text-amber-400" />
                </div>
                <div className="text-2xl font-bold text-amber-300">
                  {metrics.hesitation_pause_count ?? 0}
                </div>
                <p className="text-[10px] text-slate-500">Acoustic Stalls</p>
              </div>

              <div className="p-3.5 bg-slate-950/60 rounded-xl border border-slate-800 space-y-1">
                <div className="flex items-center justify-between text-[11px] text-slate-400 uppercase tracking-wider">
                  <span>Misconceptions</span>
                  <Brain className="w-3.5 h-3.5 text-indigo-400" />
                </div>
                <div className="text-2xl font-bold text-indigo-300">
                  {metrics.total_misconceptions ?? 0}
                </div>
                <p className="text-[10px] text-slate-500">
                  Critical: {metrics.critical_misconceptions ?? 0}
                </p>
              </div>
            </div>

            {/* Executive Summary */}
            <div className="space-y-2 pt-2">
              <h3 className="text-xs font-semibold text-indigo-300 uppercase tracking-wider flex items-center gap-1.5">
                <FileText className="w-4 h-4 text-indigo-400" /> Executive Narrative Assessment
              </h3>
              <div className="p-4 bg-slate-900/60 border border-slate-800 rounded-xl text-xs text-slate-200 leading-relaxed whitespace-pre-line">
                {latestReport.executive_summary}
              </div>
            </div>

            {/* Actionable Recommendations */}
            <div className="space-y-3 pt-2">
              <h3 className="text-xs font-semibold text-emerald-400 uppercase tracking-wider flex items-center gap-1.5">
                <TrendingUp className="w-4 h-4" /> Prioritized Instructional Recommendations
              </h3>
              <div className="grid grid-cols-1 gap-2.5">
                {latestReport.key_recommendations.map((rec, i) => (
                  <div
                    key={i}
                    className="flex items-start gap-3 p-3.5 rounded-xl bg-slate-900/80 border border-slate-800 text-xs text-slate-200"
                  >
                    <div className="w-5 h-5 rounded-full bg-emerald-950/60 border border-emerald-600/40 flex items-center justify-center shrink-0 mt-0.5">
                      <CheckCircle2 className="w-3.5 h-3.5 text-emerald-400" />
                    </div>
                    <div className="space-y-0.5">
                      <span className="font-semibold text-slate-300 mr-1.5">Action #{i + 1}:</span>
                      <span className="leading-relaxed">{rec}</span>
                    </div>
                  </div>
                ))}
              </div>
            </div>
          </Card>
        </div>
      )}
    </div>
  );
};
