import React, { useEffect, useState } from 'react';
import {
  AlertOctagon,
  GitBranch,
  RefreshCw,
  Sparkles,
  AlertTriangle,
  ArrowRight,
  BrainCircuit,
  CheckCircle2,
} from 'lucide-react';
import { Card, Badge, Alert, Button, Progress } from '../components/ui';
import { lectureService } from '../services/lectureService';
import { useJobPolling } from '../hooks/useJobPolling';
import { ConfusionEvent, Lecture, Misconception, PrerequisiteNode, ViewId } from '../types';

interface MisconceptionsViewProps {
  onNavigate?: (view: ViewId) => void;
}

export const MisconceptionsView: React.FC<MisconceptionsViewProps> = ({ onNavigate }) => {
  const [lectures, setLectures] = useState<Lecture[]>([]);
  const [selectedLectureId, setSelectedLectureId] = useState<string | null>(null);
  const [misconceptions, setMisconceptions] = useState<Misconception[]>([]);
  const [confusionEvents, setConfusionEvents] = useState<ConfusionEvent[]>([]);
  const [prerequisites, setPrerequisites] = useState<PrerequisiteNode[]>([]);
  const [isLoadingLectures, setIsLoadingLectures] = useState(true);
  const [isLoadingMisconceptions, setIsLoadingMisconceptions] = useState(false);
  const [activeJobId, setActiveJobId] = useState<string | null>(null);
  const [actionError, setActionError] = useState<string | null>(null);

  // Background Job Polling
  const { status: jobStatus, progress: jobProgress, error: jobError } = useJobPolling(activeJobId);

  // Load lectures on mount
  useEffect(() => {
    async function loadLectures() {
      try {
        setIsLoadingLectures(true);
        const data = await lectureService.listLectures();
        setLectures(data);
        if (data.length > 0 && !selectedLectureId) {
          setSelectedLectureId(data[0].id);
        }
      } catch (err: unknown) {
        setActionError(err instanceof Error ? err.message : 'Failed to load lectures.');
      } finally {
        setIsLoadingLectures(false);
      }
    }
    loadLectures();
  }, []);

  // Load misconceptions and confusion events when lecture changes or extraction finishes
  useEffect(() => {
    if (!selectedLectureId) return;

    async function loadData() {
      try {
        setIsLoadingMisconceptions(true);
        setActionError(null);

        const [mRes, cRes, pRes] = await Promise.allSettled([
          lectureService.getMisconceptions(selectedLectureId!),
          lectureService.getConfusionEvents(selectedLectureId!),
          lectureService.getPrerequisites(selectedLectureId!),
        ]);

        if (mRes.status === 'fulfilled') {
          setMisconceptions(mRes.value);
        } else {
          setMisconceptions([]);
        }

        if (cRes.status === 'fulfilled') {
          setConfusionEvents(cRes.value);
        } else {
          setConfusionEvents([]);
        }

        if (pRes.status === 'fulfilled') {
          setPrerequisites(pRes.value);
        } else {
          setPrerequisites([]);
        }
      } finally {
        setIsLoadingMisconceptions(false);
      }
    }
    loadData();
  }, [selectedLectureId, jobStatus]);

  const selectedLecture = lectures.find((l) => l.id === selectedLectureId);

  const handleStartExtraction = async () => {
    if (!selectedLectureId) return;
    try {
      setActionError(null);
      const res = await lectureService.extractMisconceptions(selectedLectureId);
      setActiveJobId(res.job_id);
    } catch (err: unknown) {
      setActionError(err instanceof Error ? err.message : 'Failed to start misconception extraction.');
    }
  };

  const handleStartPrerequisiteTracing = async () => {
    if (!selectedLectureId) return;
    try {
      setActionError(null);
      const res = await lectureService.tracePrerequisites(selectedLectureId);
      setActiveJobId(res.job_id);
    } catch (err: unknown) {
      setActionError(err instanceof Error ? err.message : 'Failed to start prerequisite tracing.');
    }
  };

  const confusionMap = new Map<string, ConfusionEvent>(
    confusionEvents.map((e) => [e.id, e])
  );

  const prereqMap = new Map<string, PrerequisiteNode[]>();
  prerequisites.forEach((p) => {
    const list = prereqMap.get(p.confusion_id) || [];
    list.push(p);
    prereqMap.set(p.confusion_id, list);
  });

  const criticalCount = misconceptions.filter((m) => m.severity === 'critical').length;
  const highCount = misconceptions.filter((m) => m.severity === 'high').length;

  return (
    <div className="space-y-6" data-testid="view-misconceptions">
      {/* Header */}
      <div className="flex flex-col md:flex-row md:items-center justify-between gap-4 pb-4 border-b border-slate-800">
        <div>
          <div className="flex items-center gap-2 mb-1">
            <span className="text-xs font-semibold tracking-wider text-indigo-400 uppercase">Phase 4 Cognitive Diagnostics</span>
            <Badge variant="indigo" size="sm">Structured LLM Reasoning</Badge>
          </div>
          <h1 className="text-2xl font-bold tracking-tight text-white flex items-center gap-2">
            <AlertOctagon className="w-6 h-6 text-rose-400" />
            Potential Misconceptions (inferred from lecture speech) & Root Causes
          </h1>
          <p className="text-slate-400 text-sm mt-1">
            Potential student misconceptions inferred from lecture speech hesitation signals, acoustic stalls, and cognitive friction indicators.
          </p>
        </div>

        {lectures.length > 0 && (
          <div className="flex items-center gap-2.5">
            <select
              value={selectedLectureId || ''}
              onChange={(e) => setSelectedLectureId(e.target.value)}
              className="bg-slate-900 border border-slate-800 rounded-xl px-3 py-2 text-xs font-medium text-slate-200 focus:outline-none focus:border-indigo-500 max-w-xs truncate"
              data-testid="misconception-lecture-select"
            >
              {lectures.map((lec) => (
                <option key={lec.id} value={lec.id}>
                  {lec.title}
                </option>
              ))}
            </select>
          </div>
        )}
      </div>

      {actionError && (
        <Alert severity="critical" title="Diagnostic Extraction Error">
          {actionError}
        </Alert>
      )}

      {isLoadingLectures ? (
        <div className="py-12 text-center text-sm text-slate-400">
          <RefreshCw className="w-6 h-6 animate-spin mx-auto text-indigo-400 mb-2" />
          Loading lectures...
        </div>
      ) : lectures.length === 0 ? (
        <Card className="text-center py-12 space-y-4">
          <BrainCircuit className="w-12 h-12 text-slate-600 mx-auto" />
          <div>
            <h3 className="text-base font-semibold text-white">No Lectures Available</h3>
            <p className="text-xs text-slate-400 mt-1">Ingest and analyze a lecture first to extract misconceptions.</p>
          </div>
          {onNavigate && (
            <Button variant="primary" size="md" onClick={() => onNavigate('upload')}>
              Go to Ingestion View
            </Button>
          )}
        </Card>
      ) : (
        <div className="space-y-6">
          {/* Lecture Diagnostic Controls Card */}
          <Card className="space-y-4">
            <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4">
              <div>
                <h3 className="text-lg font-bold text-white">{selectedLecture?.title}</h3>
                <div className="flex flex-wrap items-center gap-3 text-xs text-slate-400 mt-1">
                  <span>Potential Misconceptions: <strong className="text-rose-400">{misconceptions.length}</strong></span>
                  <span>&bull;</span>
                  <span>Prerequisites: <strong className="text-emerald-400">{prerequisites.length}</strong></span>
                  <span>&bull;</span>
                  <span>Critical Severity: <strong className="text-red-400">{criticalCount}</strong></span>
                  <span>&bull;</span>
                  <span>High Severity: <strong className="text-amber-400">{highCount}</strong></span>
                  <span>&bull;</span>
                  <span>Confusion Signals: <strong className="text-indigo-400">{confusionEvents.length}</strong></span>
                </div>
              </div>

              <div className="flex flex-wrap items-center gap-2">
                <Button
                  variant="secondary"
                  size="sm"
                  onClick={handleStartPrerequisiteTracing}
                  isLoading={Boolean(activeJobId && jobStatus === 'running')}
                  disabled={Boolean(activeJobId && jobStatus === 'running') || confusionEvents.length === 0}
                  title={confusionEvents.length === 0 ? 'Analyze signals first' : 'Trace missing prerequisite knowledge graph with ChromaDB'}
                  data-testid="trace-prerequisites-btn"
                >
                  <GitBranch className="w-3.5 h-3.5 mr-1 inline text-emerald-400" /> Trace Prerequisites
                </Button>

                <Button
                  variant="primary"
                  size="sm"
                  onClick={handleStartExtraction}
                  isLoading={Boolean(activeJobId && jobStatus === 'running')}
                  disabled={Boolean(activeJobId && jobStatus === 'running') || confusionEvents.length === 0}
                  title={confusionEvents.length === 0 ? 'Analyze signals first' : 'Infer potential misconceptions (inferred from lecture speech) with LLM'}
                >
                  <Sparkles className="w-3.5 h-3.5 mr-1 inline" /> Extract Potential Misconceptions
                </Button>
              </div>
            </div>

            {/* Active Extraction Progress Bar */}
            {activeJobId && (
              <div className="pt-2 border-t border-slate-800/80 space-y-2" data-testid="misconception-progress">
                <div className="flex justify-between text-xs text-slate-300">
                  <span className="flex items-center gap-1.5">
                    <RefreshCw className={`w-3.5 h-3.5 ${jobStatus === 'running' ? 'animate-spin text-rose-400' : ''}`} />
                    Diagnostic Status: <strong className="uppercase">{jobStatus || 'Running'}</strong>
                  </span>
                  <span>{jobProgress}%</span>
                </div>
                <Progress
                  value={jobProgress}
                  severity={jobStatus === 'done' ? 'low' : jobStatus === 'failed' ? 'critical' : 'high'}
                />
                {jobStatus === 'done' && (
                  <Alert severity="low" title="Diagnostic Extraction Completed">
                    Potential misconceptions (inferred from lecture speech) extracted with root cause prerequisite links and 3D coordinates.
                  </Alert>
                )}
                {jobStatus === 'failed' && (
                  <Alert severity="critical" title="Diagnostic Job Failed">
                    {jobError || 'Failed to extract potential misconceptions.'}
                  </Alert>
                )}
              </div>
            )}
          </Card>

          {/* Misconceptions List */}
          {isLoadingMisconceptions ? (
            <div className="py-8 text-center text-sm text-slate-400">
              <RefreshCw className="w-5 h-5 animate-spin mx-auto text-indigo-400 mb-1.5" />
              Loading potential misconceptions (inferred from lecture speech)...
            </div>
          ) : misconceptions.length === 0 ? (
            <Card className="text-center py-8 text-sm text-slate-400 space-y-3" data-testid="misconceptions-empty-state">
              <CheckCircle2 className="w-8 h-8 text-emerald-400 mx-auto mb-1" />
              <p className="font-semibold text-slate-200">
                {confusionEvents.length === 0
                  ? 'No cognitive confusion detected: lecture delivered with high instructional clarity.'
                  : 'No potential misconceptions (inferred from lecture speech) extracted yet for this lecture.'}
              </p>
              <p className="text-xs text-slate-400 max-w-md mx-auto">
                {confusionEvents.length === 0
                  ? 'Acoustic pacing and articulation metrics remained consistent throughout the presentation. No mental model repairs needed.'
                  : 'Speech friction signals did not elevate to actionable misconception thresholds.'}
              </p>
              {confusionEvents.length > 0 && (
                <Button
                  variant="secondary"
                  size="sm"
                  onClick={handleStartExtraction}
                >
                  <Sparkles className="w-3.5 h-3.5 mr-1 inline text-indigo-400" /> Infer Potential Misconceptions Now
                </Button>
              )}
            </Card>
          ) : (
            <div className="space-y-4" data-testid="misconceptions-list">
              {misconceptions.map((m) => {
                const linkedEvent = confusionMap.get(m.confusion_id);
                const linkedPrereqs = prereqMap.get(m.confusion_id) || [];
                const loadPercent = Math.round(m.cognitive_load_score * 100);
                const rawConfidence = typeof linkedEvent?.signals?.ai_confidence === 'number'
                  ? (linkedEvent.signals.ai_confidence as number)
                  : (linkedEvent?.confusion_score ?? m.cognitive_load_score ?? 0.85);
                const confidencePct = Math.round(rawConfidence * 100);

                return (
                  <Card key={m.id} className="space-y-3 p-4">
                    <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-2">
                      <div className="flex flex-wrap items-center gap-2">
                        <Badge variant={m.severity} size="sm">
                          {m.severity.toUpperCase()} SEVERITY
                        </Badge>
                        <Badge variant="indigo" size="sm" data-testid={`misconception-confidence-${m.id}`}>
                          Model Confidence: {confidencePct}%
                        </Badge>
                        <h3 className="text-base font-semibold text-white">{m.name}</h3>
                      </div>
                      <Badge variant="default" size="sm">
                        Coord: ({m.coordinates?.x?.toFixed(1) ?? 0}, {m.coordinates?.y?.toFixed(1) ?? 0}, {m.coordinates?.z?.toFixed(1) ?? 0})
                      </Badge>
                    </div>

                    <p className="text-slate-200 text-sm leading-relaxed">{m.explanation}</p>

                    {/* Root Prerequisite Gap Callout */}
                    <div className="p-3 bg-slate-950/60 border border-slate-800 rounded-xl space-y-1">
                      <span className="text-xs font-semibold text-amber-400 flex items-center gap-1.5">
                        <GitBranch className="w-3.5 h-3.5" /> Root Prerequisite Gap & Flawed Intuition:
                      </span>
                      <p className="text-xs text-slate-300 leading-relaxed">{m.apparent_reason}</p>
                    </div>

                    {/* Traced Prerequisite Nodes via Vector Retrieval */}
                    {linkedPrereqs.length > 0 && (
                      <div className="space-y-2 pt-2 border-t border-slate-800/60" data-testid="prerequisite-nodes-list">
                        <div className="flex items-center justify-between">
                          <span className="text-xs font-semibold text-emerald-400 flex items-center gap-1.5 uppercase tracking-wider">
                            <GitBranch className="w-3.5 h-3.5" /> Traced Upstream Prerequisites (Vector Retrieval):
                          </span>
                          <span className="text-[11px] text-slate-400 font-mono">
                            {linkedPrereqs.length} foundation{linkedPrereqs.length > 1 ? 's' : ''}
                          </span>
                        </div>

                        <div className="grid grid-cols-1 gap-2">
                          {linkedPrereqs.map((p) => (
                            <div
                              key={p.id}
                              className="bg-slate-950/70 border border-slate-800/80 rounded-lg p-3 space-y-1.5 text-xs"
                              data-testid={`prereq-node-${p.id}`}
                            >
                              <div className="flex flex-wrap items-center justify-between gap-1.5">
                                <div className="flex items-center gap-2">
                                  <Badge
                                    variant={p.depth === 1 ? 'critical' : p.depth === 2 ? 'high' : 'medium'}
                                    size="sm"
                                  >
                                    Depth {p.depth}: {p.depth === 1 ? 'Direct Gap' : p.depth === 2 ? 'Foundational' : 'Primer'}
                                  </Badge>
                                  <strong className="text-slate-100 font-semibold">{p.concept_name}</strong>
                                </div>
                                <div className="flex items-center gap-2">
                                  <Badge variant="default" size="sm">
                                    Vector Dist: {p.vector_distance?.toFixed(3) ?? '0.000'}
                                  </Badge>
                                  <Badge variant="default" size="sm">
                                    Coord: ({p.coordinates?.x?.toFixed(1) ?? 0}, {p.coordinates?.y?.toFixed(1) ?? 0}, {p.coordinates?.z?.toFixed(1) ?? 0})
                                  </Badge>
                                </div>
                              </div>

                              <p className="text-slate-300 leading-relaxed">{p.gap_description}</p>

                              {p.remediation_hint && (
                                <div className="text-[11px] text-indigo-300 bg-indigo-950/30 border border-indigo-900/40 rounded p-1.5 flex items-start gap-1.5">
                                  <Sparkles className="w-3 h-3 text-indigo-400 shrink-0 mt-0.5" />
                                  <span><strong className="text-indigo-200">Remediation:</strong> {p.remediation_hint}</span>
                                </div>
                              )}
                            </div>
                          ))}
                        </div>
                      </div>
                    )}

                    {/* Grounding Confusion Quote Preview */}
                    {linkedEvent && linkedEvent.evidence_text && (
                      <div className="text-xs text-slate-400 bg-slate-950/30 p-2 rounded-lg border border-slate-800/60 flex items-start gap-1.5">
                        <AlertTriangle className="w-3.5 h-3.5 text-indigo-400 shrink-0 mt-0.5" />
                        <span className="italic">&ldquo;{linkedEvent.evidence_text}&rdquo;</span>
                      </div>
                    )}

                    {/* Cognitive Load Bar & Footer */}
                    <div className="pt-2 border-t border-slate-800/60 flex flex-col sm:flex-row sm:items-center justify-between gap-3 text-xs">
                      <div className="flex items-center gap-2 flex-1 max-w-xs">
                        <span className="text-slate-400">Cognitive Load:</span>
                        <div className="flex-1">
                          <Progress
                            value={loadPercent}
                            severity={loadPercent > 80 ? 'critical' : loadPercent > 60 ? 'high' : 'medium'}
                          />
                        </div>
                        <span className={`font-mono font-semibold ${loadPercent > 80 ? 'text-red-400' : 'text-slate-200'}`}>
                          {loadPercent}%
                        </span>
                      </div>

                      <div className="flex items-center gap-3">
                        <span className="font-mono text-[11px] text-slate-500">Node: {m.confusion_id.slice(0, 8)}</span>
                        {onNavigate && (
                          <button
                            onClick={() => onNavigate('student')}
                            className="text-xs text-indigo-400 hover:text-indigo-300 font-medium flex items-center gap-1"
                          >
                            Generate Catch-Up Plan <ArrowRight className="w-3 h-3" />
                          </button>
                        )}
                      </div>
                    </div>
                  </Card>
                );
              })}
            </div>
          )}
        </div>
      )}
    </div>
  );
};
