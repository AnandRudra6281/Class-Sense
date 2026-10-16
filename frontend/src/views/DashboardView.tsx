import React, { useEffect, useState } from 'react';
import {
  LayoutDashboard,
  AlertTriangle,
  CheckCircle2,
  Clock,
  BookOpen,
  Sparkles,
  RefreshCw,
  GitBranch,
  HelpCircle,
  Lightbulb,
  ArrowRight,
} from 'lucide-react';
import { Card, Badge, Progress, Alert, Button } from '../components/ui';
import { lectureService } from '../services/lectureService';
import { useJobPolling } from '../hooks/useJobPolling';
import {
  ConfusionEvent,
  Coordinates3D,
  DiagnosticQuestion,
  Intervention,
  Lecture,
  Misconception,
  PrerequisiteNode,
  ViewId,
} from '../types';

interface DashboardViewProps {
  onNavigate?: (view: ViewId) => void;
}

export const DashboardView: React.FC<DashboardViewProps> = ({ onNavigate }) => {
  const [lectures, setLectures] = useState<Lecture[]>([]);
  const [selectedLectureId, setSelectedLectureId] = useState<string | null>(null);
  const [confusionEvents, setConfusionEvents] = useState<ConfusionEvent[]>([]);
  const [misconceptions, setMisconceptions] = useState<Misconception[]>([]);
  const [prerequisites, setPrerequisites] = useState<PrerequisiteNode[]>([]);
  const [interventions, setInterventions] = useState<Intervention[]>([]);
  const [isLoadingLectures, setIsLoadingLectures] = useState(true);
  const [isLoadingData, setIsLoadingData] = useState(false);
  const [activeJobId, setActiveJobId] = useState<string | null>(null);
  const [actionError, setActionError] = useState<string | null>(null);
  const [selectedAnswers, setSelectedAnswers] = useState<Record<string, number>>({});

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

  // Load diagnostic and intervention data when lecture changes or job finishes
  useEffect(() => {
    if (!selectedLectureId) return;

    async function loadData() {
      try {
        setIsLoadingData(true);
        setActionError(null);

        const [cRes, mRes, pRes, iRes] = await Promise.allSettled([
          lectureService.getConfusionEvents(selectedLectureId!),
          lectureService.getMisconceptions(selectedLectureId!),
          lectureService.getPrerequisites(selectedLectureId!),
          lectureService.getInterventions(selectedLectureId!, 'teacher'),
        ]);

        if (cRes.status === 'fulfilled') setConfusionEvents(cRes.value);
        else setConfusionEvents([]);

        if (mRes.status === 'fulfilled') setMisconceptions(mRes.value);
        else setMisconceptions([]);

        if (pRes.status === 'fulfilled') setPrerequisites(pRes.value);
        else setPrerequisites([]);

        if (iRes.status === 'fulfilled') setInterventions(iRes.value);
        else setInterventions([]);
      } finally {
        setIsLoadingData(false);
      }
    }
    loadData();
  }, [selectedLectureId, jobStatus]);

  const selectedLecture = lectures.find((l) => l.id === selectedLectureId);

  const handleGenerateInterventions = async () => {
    if (!selectedLectureId) return;
    try {
      setActionError(null);
      const res = await lectureService.generateInterventions(selectedLectureId);
      setActiveJobId(res.job_id);
    } catch (err: unknown) {
      setActionError(err instanceof Error ? err.message : 'Failed to start teacher intervention synthesis.');
    }
  };

  const centerCoords: Coordinates3D = selectedLecture?.coordinates || { x: 50.0, y: 35.0, z: 2.0 };
  const criticalMisconceptions = misconceptions.filter((m) => m.severity === 'critical').length;

  return (
    <div className="space-y-6" data-testid="view-dashboard">
      {/* Header */}
      <div className="flex flex-col md:flex-row md:items-center justify-between gap-4 pb-4 border-b border-slate-800">
        <div>
          <div className="flex items-center gap-2 mb-1">
            <span className="text-xs font-semibold tracking-wider text-indigo-400 uppercase">Executive Overview</span>
            <Badge variant="indigo" size="sm">Pedagogical Interventions</Badge>
          </div>
          <h1 className="text-2xl font-bold tracking-tight text-white flex items-center gap-2">
            <LayoutDashboard className="w-6 h-6 text-indigo-400" />
            Instructor Cockpit
          </h1>
          <p className="text-slate-400 text-sm mt-1">
            Real-time analytics across lecture confusion spikes, topic comprehension, and actionable teacher interventions.
          </p>
        </div>

        {lectures.length > 0 && (
          <div className="flex items-center gap-2.5">
            <select
              value={selectedLectureId || ''}
              onChange={(e) => setSelectedLectureId(e.target.value)}
              className="bg-slate-900 border border-slate-800 rounded-xl px-3 py-2 text-xs font-medium text-slate-200 focus:outline-none focus:border-indigo-500 max-w-xs truncate"
              data-testid="cockpit-lecture-select"
            >
              {lectures.map((lec) => (
                <option key={lec.id} value={lec.id}>
                  {lec.title}
                </option>
              ))}
            </select>
            <Badge variant="default">
              Coord: ({centerCoords.x.toFixed(1)}, {centerCoords.y.toFixed(1)}, {centerCoords.z.toFixed(1)})
            </Badge>
          </div>
        )}
      </div>

      {actionError && (
        <Alert severity="critical" title="Cockpit Error">
          {actionError}
        </Alert>
      )}

      {/* KPI Cards */}
      <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4">
        <Card className="space-y-2">
          <div className="flex items-center justify-between text-xs text-slate-400">
            <span>Lecture Ingestion</span>
            <BookOpen className="w-4 h-4 text-indigo-400" />
          </div>
          <div className="text-2xl font-bold text-white">
            {selectedLecture ? `${Math.round(selectedLecture.duration_seconds)}s` : '0s'}
          </div>
          <div className="flex items-center gap-1.5 text-xs text-emerald-400">
            <CheckCircle2 className="w-3.5 h-3.5" />
            <span>Status: {selectedLecture?.status || 'Active'}</span>
          </div>
        </Card>

        <Card className="space-y-2">
          <div className="flex items-center justify-between text-xs text-slate-400">
            <span>Critical Confusion Points</span>
            <AlertTriangle className="w-4 h-4 text-rose-400" />
          </div>
          <div className="text-2xl font-bold text-rose-400">{confusionEvents.length}</div>
          <Badge variant={confusionEvents.length > 0 ? 'critical' : 'low'} size="sm">
            {confusionEvents.length > 0 ? 'Spikes Detected' : 'Optimal Comprehension'}
          </Badge>
        </Card>

        <Card className="space-y-2">
          <div className="flex items-center justify-between text-xs text-slate-400">
            <span>Diagnosed Misconceptions</span>
            <Clock className="w-4 h-4 text-amber-400" />
          </div>
          <div className="text-2xl font-bold text-amber-400">{misconceptions.length}</div>
          <span className="text-xs text-slate-400">
            Critical Severity: <strong className="text-red-400">{criticalMisconceptions}</strong>
          </span>
        </Card>

        <Card className="space-y-2">
          <div className="flex items-center justify-between text-xs text-slate-400">
            <span>Traced Prerequisites</span>
            <GitBranch className="w-4 h-4 text-emerald-400" />
          </div>
          <div className="text-2xl font-bold text-emerald-400">{prerequisites.length}</div>
          <Badge variant="low" size="sm">
            {prerequisites.length > 0 ? 'Grounded in ChromaDB' : 'Pending Tracing'}
          </Badge>
        </Card>
      </div>

      {isLoadingLectures ? (
        <div className="py-12 text-center text-sm text-slate-400">
          <RefreshCw className="w-6 h-6 animate-spin mx-auto text-indigo-400 mb-2" />
          Loading cockpit lectures...
        </div>
      ) : !selectedLecture ? (
        <Card className="text-center py-12 space-y-4">
          <BookOpen className="w-12 h-12 text-slate-600 mx-auto" />
          <div>
            <h3 className="text-base font-semibold text-white">No Lectures Available</h3>
            <p className="text-xs text-slate-400 mt-1">Upload and transcribe a lecture to view real-time instructor interventions.</p>
          </div>
          {onNavigate && (
            <Button variant="primary" size="md" onClick={() => onNavigate('upload')}>
              Ingest First Lecture
            </Button>
          )}
        </Card>
      ) : (
        <div className="space-y-6">
          {/* Action Trigger Card */}
          <Card className="space-y-4">
            <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4">
              <div>
                <h3 className="text-lg font-bold text-white">{selectedLecture.title}</h3>
                <p className="text-xs text-slate-400 mt-0.5">
                  Automated pedagogical interventions synthesized from acoustic pauses, confusion signals, and prerequisite gaps.
                </p>
              </div>

              <div className="flex items-center gap-2">
                <Button
                  variant="primary"
                  size="sm"
                  onClick={handleGenerateInterventions}
                  isLoading={Boolean(activeJobId && jobStatus === 'running')}
                  disabled={Boolean(activeJobId && jobStatus === 'running') || confusionEvents.length === 0}
                  title={confusionEvents.length === 0 ? 'Analyze signals first' : 'Synthesize targeted teaching interventions with LLM'}
                  data-testid="generate-interventions-btn"
                >
                  <Sparkles className="w-3.5 h-3.5 mr-1 inline" /> Generate Teacher Interventions
                </Button>
              </div>
            </div>

            {/* Background Polling Progress Bar */}
            {activeJobId && (
              <div className="pt-2 border-t border-slate-800/80 space-y-2" data-testid="intervention-progress">
                <div className="flex justify-between text-xs text-slate-300">
                  <span className="flex items-center gap-1.5">
                    <RefreshCw className={`w-3.5 h-3.5 ${jobStatus === 'running' ? 'animate-spin text-indigo-400' : ''}`} />
                    Synthesis Status: <strong className="uppercase">{jobStatus || 'Running'}</strong>
                  </span>
                  <span>{jobProgress}%</span>
                </div>
                <Progress
                  value={jobProgress}
                  severity={jobStatus === 'done' ? 'low' : jobStatus === 'failed' ? 'critical' : 'high'}
                />
                {jobStatus === 'done' && (
                  <Alert severity="low" title="Interventions Synthesized">
                    Teaching interventions and in-class diagnostic check questions generated successfully.
                  </Alert>
                )}
                {jobStatus === 'failed' && (
                  <Alert severity="critical" title="Generation Failed">
                    {jobError || 'Failed to generate teacher interventions.'}
                  </Alert>
                )}
              </div>
            )}
          </Card>

          {/* Teacher Interventions List */}
          {isLoadingData ? (
            <div className="py-8 text-center text-sm text-slate-400">
              <RefreshCw className="w-5 h-5 animate-spin mx-auto text-indigo-400 mb-1.5" />
              Loading synthesized interventions...
            </div>
          ) : interventions.length === 0 ? (
            <Card className="text-center py-8 text-sm text-slate-400 space-y-3">
              <p>No teacher interventions synthesized yet for this lecture.</p>
              <Button
                variant="secondary"
                size="sm"
                onClick={handleGenerateInterventions}
                disabled={confusionEvents.length === 0}
              >
                <Sparkles className="w-3.5 h-3.5 mr-1 inline text-indigo-400" /> Synthesize Interventions Now
              </Button>
            </Card>
          ) : (
            <div className="space-y-6" data-testid="interventions-list">
              {interventions.map((inv) => {
                const content = inv.content as {
                  actionable_recap?: string[];
                  diagnostic_questions?: DiagnosticQuestion[];
                  recommended_pacing?: string;
                  blackboard_analogy?: string;
                };

                return (
                  <Card key={inv.id} variant="glow" className="space-y-5 p-5">
                    {/* Intervention Header */}
                    <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-3 pb-3 border-b border-slate-800">
                      <div>
                        <div className="flex items-center gap-2 mb-1">
                          <Badge variant="indigo" size="sm">Instructional Action Plan</Badge>
                          <Badge variant="default" size="sm">
                            Coord: ({inv.coordinates?.x?.toFixed(1) ?? 0}, {inv.coordinates?.y?.toFixed(1) ?? 0}, {inv.coordinates?.z?.toFixed(1) ?? 0})
                          </Badge>
                        </div>
                        <h3 className="text-lg font-bold text-white">{inv.title}</h3>
                      </div>
                    </div>

                    {/* Section 1: Actionable Opening Recap */}
                    {content.actionable_recap && content.actionable_recap.length > 0 && (
                      <div className="space-y-2">
                        <h4 className="text-xs font-semibold text-emerald-400 uppercase tracking-wider flex items-center gap-1.5">
                          <CheckCircle2 className="w-4 h-4" /> Next-Class Opening Recap (3–5 Minutes)
                        </h4>
                        <div className="grid grid-cols-1 gap-2">
                          {content.actionable_recap.map((point, idx) => (
                            <div
                              key={idx}
                              className="flex items-start gap-2.5 p-3 rounded-xl bg-slate-950/60 border border-slate-800 text-xs text-slate-200"
                            >
                              <span className="font-mono text-emerald-400 font-bold shrink-0">{idx + 1}.</span>
                              <span className="leading-relaxed">{point}</span>
                            </div>
                          ))}
                        </div>
                      </div>
                    )}

                    {/* Section 2: Pacing & Delivery Guidance */}
                    {content.recommended_pacing && (
                      <div className="p-3.5 bg-slate-950/60 border border-amber-900/40 rounded-xl space-y-1">
                        <span className="text-xs font-semibold text-amber-400 flex items-center gap-1.5">
                          <Clock className="w-3.5 h-3.5" /> Pacing & Delivery Adjustment:
                        </span>
                        <p className="text-xs text-slate-300 leading-relaxed">{content.recommended_pacing}</p>
                      </div>
                    )}

                    {/* Section 3: Blackboard Analogy Box */}
                    {content.blackboard_analogy && (
                      <div className="p-3.5 bg-indigo-950/40 border border-indigo-800/60 rounded-xl space-y-1">
                        <span className="text-xs font-semibold text-indigo-300 flex items-center gap-1.5">
                          <Lightbulb className="w-4 h-4 text-amber-400" /> Recommended Blackboard Analogy:
                        </span>
                        <p className="text-xs text-slate-200 leading-relaxed">{content.blackboard_analogy}</p>
                      </div>
                    )}

                    {/* Section 4: In-Class Diagnostic Multiple-Choice Check Questions */}
                    {content.diagnostic_questions && content.diagnostic_questions.length > 0 && (
                      <div className="space-y-3 pt-2 border-t border-slate-800/60">
                        <h4 className="text-xs font-semibold text-slate-300 uppercase tracking-wider flex items-center gap-1.5">
                          <HelpCircle className="w-4 h-4 text-indigo-400" /> In-Class Diagnostic Check Questions
                        </h4>

                        <div className="space-y-4">
                          {content.diagnostic_questions.map((dq, qIdx) => {
                            const qKey = `${inv.id}-q-${qIdx}`;
                            const selectedOption = selectedAnswers[qKey];
                            const isAnswered = selectedOption !== undefined;

                            return (
                              <div
                                key={qIdx}
                                className="p-4 bg-slate-950/80 border border-slate-800 rounded-xl space-y-3"
                                data-testid={`diagnostic-question-${qIdx}`}
                              >
                                <div className="flex items-start justify-between gap-2">
                                  <p className="text-sm font-medium text-white">{dq.question}</p>
                                  <Badge variant="default" size="sm">Question {qIdx + 1}</Badge>
                                </div>

                                <div className="space-y-2">
                                  {dq.options.map((option, optIdx) => {
                                    const isSelected = selectedOption === optIdx;
                                    const isCorrect = optIdx === dq.correct_option_index;

                                    return (
                                      <button
                                        key={optIdx}
                                        type="button"
                                        onClick={() =>
                                          setSelectedAnswers((prev) => ({ ...prev, [qKey]: optIdx }))
                                        }
                                        className={`w-full text-left p-2.5 rounded-lg border text-xs font-medium transition-all ${
                                          isAnswered
                                            ? isCorrect
                                              ? 'bg-emerald-950/40 border-emerald-500/80 text-emerald-200'
                                              : isSelected
                                              ? 'bg-rose-950/40 border-rose-500/80 text-rose-200'
                                              : 'bg-slate-900/60 border-slate-800 text-slate-400'
                                            : 'bg-slate-900 border-slate-800 text-slate-200 hover:border-slate-700'
                                        }`}
                                      >
                                        <div className="flex items-center justify-between">
                                          <span>
                                            <strong className="mr-1.5 font-mono">
                                              {String.fromCharCode(65 + optIdx)}.
                                            </strong>
                                            {option}
                                          </span>
                                          {isAnswered && isCorrect && (
                                            <Badge variant="low" size="sm">Correct Answer</Badge>
                                          )}
                                        </div>
                                      </button>
                                    );
                                  })}
                                </div>

                                {isAnswered && dq.rationale && (
                                  <div className="p-2.5 bg-slate-900/90 rounded-lg border border-slate-800 text-xs text-slate-300">
                                    <strong className="text-indigo-400 mr-1">Rationale:</strong>
                                    {dq.rationale}
                                  </div>
                                )}
                              </div>
                            );
                          })}
                        </div>
                      </div>
                    )}

                    {/* Footer Nav */}
                    <div className="pt-2 border-t border-slate-800/60 flex items-center justify-between text-xs text-slate-400">
                      <span>Package ID: {inv.id.slice(0, 8)}</span>
                      {onNavigate && (
                        <button
                          onClick={() => onNavigate('reports')}
                          className="text-indigo-400 hover:text-indigo-300 font-medium flex items-center gap-1"
                        >
                          View Full Pedagogy Audit Report <ArrowRight className="w-3 h-3" />
                        </button>
                      )}
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
