import React, { useEffect, useState } from 'react';
import {
  FileSearch,
  Activity,
  AlertTriangle,
  RefreshCw,
  Sparkles,
} from 'lucide-react';
import { Card, Badge, Alert, Button, Progress } from '../components/ui';
import { lectureService } from '../services/lectureService';
import { useJobPolling } from '../hooks/useJobPolling';
import { ConfusionEvent, Evidence, Lecture, ViewId } from '../types';

interface EvidenceViewProps {
  onNavigate?: (view: ViewId) => void;
}

export const EvidenceView: React.FC<EvidenceViewProps> = ({ onNavigate }) => {
  const [lectures, setLectures] = useState<Lecture[]>([]);
  const [selectedLectureId, setSelectedLectureId] = useState<string | null>(null);
  const [evidenceList, setEvidenceList] = useState<Evidence[]>([]);
  const [confusionEvents, setConfusionEvents] = useState<ConfusionEvent[]>([]);
  const [isLoadingLectures, setIsLoadingLectures] = useState(true);
  const [isLoadingEvidence, setIsLoadingEvidence] = useState(false);
  const [activeJobId, setActiveJobId] = useState<string | null>(null);
  const [actionError, setActionError] = useState<string | null>(null);

  // Background Job Polling
  const { status: jobStatus, progress: jobProgress } = useJobPolling(activeJobId);

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

  // Load evidence and confusion events when lecture changes or analysis job finishes
  useEffect(() => {
    if (!selectedLectureId) return;

    async function loadEvidence() {
      try {
        setIsLoadingEvidence(true);
        setActionError(null);
        const [eviRes, confRes] = await Promise.allSettled([
          lectureService.getEvidence(selectedLectureId!),
          lectureService.getConfusionEvents(selectedLectureId!),
        ]);

        if (eviRes.status === 'fulfilled') {
          setEvidenceList(eviRes.value);
        } else {
          setEvidenceList([]);
        }

        if (confRes.status === 'fulfilled') {
          setConfusionEvents(confRes.value);
        } else {
          setConfusionEvents([]);
        }
      } finally {
        setIsLoadingEvidence(false);
      }
    }
    loadEvidence();
  }, [selectedLectureId, jobStatus]);

  const selectedLecture = lectures.find((l) => l.id === selectedLectureId);

  const handleStartSignalAnalysis = async () => {
    if (!selectedLectureId) return;
    try {
      setActionError(null);
      const res = await lectureService.analyzeSignals(selectedLectureId);
      setActiveJobId(res.job_id);
    } catch (err: unknown) {
      setActionError(err instanceof Error ? err.message : 'Failed to run confusion signal analysis.');
    }
  };

  const getSignalBadgeVariant = (signalType: string): 'critical' | 'high' | 'medium' | 'low' => {
    switch (signalType.toLowerCase()) {
      case 'disfluency':
        return 'critical';
      case 'pause_density':
        return 'high';
      case 'acoustic_wpm':
        return 'medium';
      default:
        return 'low';
    }
  };

  const confusionMap = new Map<string, ConfusionEvent>(
    confusionEvents.map((e) => [e.id, e])
  );

  return (
    <div className="space-y-6" data-testid="view-evidence">
      {/* Header */}
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
            Empirical multi-modal proof (speech rate deceleration, cognitive pauses, disfluency markers) grounded in <span className="font-mono text-indigo-300">docs/CONFUSION_METHOD.md</span>.
          </p>
        </div>

        {lectures.length > 0 && (
          <div className="flex items-center gap-2.5">
            <select
              value={selectedLectureId || ''}
              onChange={(e) => setSelectedLectureId(e.target.value)}
              className="bg-slate-900 border border-slate-800 rounded-xl px-3 py-2 text-xs font-medium text-slate-200 focus:outline-none focus:border-indigo-500 max-w-xs truncate"
              data-testid="evidence-lecture-select"
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
        <Alert severity="critical" title="Analysis Error">
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
          <Activity className="w-12 h-12 text-slate-600 mx-auto" />
          <div>
            <h3 className="text-base font-semibold text-white">No Lectures Available</h3>
            <p className="text-xs text-slate-400 mt-1">Ingest and transcribe a lecture video to extract empirical evidence.</p>
          </div>
          {onNavigate && (
            <Button variant="primary" size="md" onClick={() => onNavigate('upload')}>
              Go to Ingestion View
            </Button>
          )}
        </Card>
      ) : (
        <div className="space-y-6">
          {/* Signal Controls & Metrics Card */}
          <Card className="space-y-4">
            <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4">
              <div>
                <h3 className="text-lg font-bold text-white">{selectedLecture?.title}</h3>
                <p className="text-xs text-slate-400 mt-0.5">
                  {evidenceList.length} evidence items &bull; {confusionEvents.length} friction clusters detected
                </p>
              </div>

              <Button
                variant="primary"
                size="sm"
                onClick={handleStartSignalAnalysis}
                isLoading={Boolean(activeJobId && jobStatus === 'running')}
                disabled={Boolean(activeJobId && jobStatus === 'running')}
              >
                <Activity className="w-3.5 h-3.5 mr-1 inline" /> Re-Analyze Signals
              </Button>
            </div>

            {/* Active Analysis Progress Bar */}
            {activeJobId && (
              <div className="pt-2 border-t border-slate-800/80 space-y-2" data-testid="evidence-progress">
                <div className="flex justify-between text-xs text-slate-300">
                  <span className="flex items-center gap-1.5">
                    <RefreshCw className={`w-3.5 h-3.5 ${jobStatus === 'running' ? 'animate-spin text-indigo-400' : ''}`} />
                    Analyzing Signals: <strong className="uppercase">{jobStatus || 'Running'}</strong>
                  </span>
                  <span>{jobProgress}%</span>
                </div>
                <Progress
                  value={jobProgress}
                  severity={jobStatus === 'done' ? 'low' : jobStatus === 'failed' ? 'critical' : 'medium'}
                />
              </div>
            )}
          </Card>

          {/* Evidence List */}
          {isLoadingEvidence ? (
            <div className="py-8 text-center text-sm text-slate-400">
              <RefreshCw className="w-5 h-5 animate-spin mx-auto text-indigo-400 mb-1.5" />
              Loading empirical evidence items...
            </div>
          ) : evidenceList.length === 0 ? (
            <Card className="text-center py-8 text-sm text-slate-400 space-y-3">
              <p>No confusion evidence generated yet for this lecture.</p>
              <Button
                variant="secondary"
                size="sm"
                onClick={handleStartSignalAnalysis}
              >
                <Sparkles className="w-3.5 h-3.5 mr-1 inline text-indigo-400" /> Run Signal Engine Now
              </Button>
            </Card>
          ) : (
            <div className="space-y-4" data-testid="evidence-items-list">
              {evidenceList.map((evi) => {
                const linkedEvent = confusionMap.get(evi.confusion_id);
                const signals = (linkedEvent?.signals || {}) as Record<string, unknown>;

                return (
                  <Card key={evi.id} className="space-y-3 p-4">
                    <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-2">
                      <div className="flex items-center gap-2">
                        <Badge variant={getSignalBadgeVariant(evi.signal_type)} size="sm">
                          {evi.signal_type.replace('_', ' ').toUpperCase()}
                        </Badge>
                        <span className="text-xs text-slate-300">
                          Confidence: <strong className="text-white">{Math.round(evi.confidence * 100)}%</strong>
                        </span>
                      </div>
                      <Badge variant="default" size="sm">
                        Coord: ({evi.coordinates?.x?.toFixed(1) ?? 0}, {evi.coordinates?.y?.toFixed(1) ?? 0}, {evi.coordinates?.z?.toFixed(1) ?? 0})
                      </Badge>
                    </div>

                    {/* Linked Confusion Context */}
                    {linkedEvent && (
                      <div className="text-xs text-slate-300 font-medium bg-slate-950/40 p-2 rounded-lg border border-slate-800/60 flex items-start gap-1.5">
                        <AlertTriangle className="w-3.5 h-3.5 text-amber-400 shrink-0 mt-0.5" />
                        <span>{linkedEvent.misconception_text}</span>
                      </div>
                    )}

                    {/* Grounding Transcript Quote */}
                    <blockquote className="border-l-2 border-indigo-500 pl-3 py-1.5 italic text-slate-100 text-sm bg-slate-950/30 rounded-r-lg leading-relaxed">
                      &ldquo;{evi.quote}&rdquo;
                    </blockquote>

                    {/* Empirical Signal Markers */}
                    {signals && Object.keys(signals).length > 0 && (
                      <div className="flex flex-wrap gap-2 text-[11px] pt-1">
                        {signals.wpm_anomaly_z !== undefined && (
                          <span className="px-2 py-0.5 rounded bg-slate-950 border border-slate-800 text-slate-300">
                            WPM Anomaly: <strong className="text-indigo-300">{String(signals.wpm_anomaly_z)}&sigma;</strong>
                          </span>
                        )}
                        {signals.pause_density !== undefined && (
                          <span className="px-2 py-0.5 rounded bg-slate-950 border border-slate-800 text-slate-300">
                            Pause Density: <strong className="text-amber-300">{(Number(signals.pause_density) * 100).toFixed(0)}%</strong>
                          </span>
                        )}
                        {signals.disfluency_ratio !== undefined && (
                          <span className="px-2 py-0.5 rounded bg-slate-950 border border-slate-800 text-slate-300">
                            Disfluency Ratio: <strong className="text-rose-300">{(Number(signals.disfluency_ratio) * 100).toFixed(0)}%</strong>
                          </span>
                        )}
                        {signals.acoustic_friction_score !== undefined && (
                          <span className="px-2 py-0.5 rounded bg-slate-950 border border-slate-800 text-slate-300">
                            Friction Score: <strong className="text-emerald-300">{String(signals.acoustic_friction_score)}</strong>
                          </span>
                        )}
                      </div>
                    )}

                    <div className="flex items-center justify-between text-xs text-slate-400 pt-1 border-t border-slate-800/50">
                      <span>Time: {evi.timestamp_start.toFixed(1)}s &rarr; {evi.timestamp_end.toFixed(1)}s</span>
                      <span className="font-mono text-[11px] text-slate-500">ID: {evi.id.slice(0, 8)}</span>
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
