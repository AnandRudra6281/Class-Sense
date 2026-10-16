import React, { useEffect, useState } from 'react';
import {
  BarChart3,
  Mic,
  Play,
  RefreshCw,
  ChevronDown,
  Layers,
  Activity,
} from 'lucide-react';
import { Card, Badge, Button, Progress, Alert } from '../components/ui';
import { lectureService } from '../services/lectureService';
import { useJobPolling } from '../hooks/useJobPolling';
import { Lecture, Topic, TranscriptSegment, ViewId } from '../types';

interface AnalysisViewProps {
  onNavigate?: (view: ViewId) => void;
}

export const AnalysisView: React.FC<AnalysisViewProps> = ({ onNavigate }) => {
  const [lectures, setLectures] = useState<Lecture[]>([]);
  const [selectedLectureId, setSelectedLectureId] = useState<string | null>(null);
  const [segments, setSegments] = useState<TranscriptSegment[]>([]);
  const [topics, setTopics] = useState<Topic[]>([]);
  const [isLoadingLectures, setIsLoadingLectures] = useState(true);
  const [isLoadingTranscript, setIsLoadingTranscript] = useState(false);
  const [isLoadingTopics, setIsLoadingTopics] = useState(false);
  const [asrProvider, setAsrProvider] = useState<string>('auto');
  const [activeJobId, setActiveJobId] = useState<string | null>(null);
  const [activeJobType, setActiveJobType] = useState<string | null>(null);
  const [actionError, setActionError] = useState<string | null>(null);
  const [expandedSegmentId, setExpandedSegmentId] = useState<string | null>(null);

  // Background Job Polling
  const { job, status: jobStatus, progress: jobProgress, error: jobError } = useJobPolling(activeJobId);

  // Fetch lectures on mount
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

  // Fetch transcript and topics when selected lecture changes or job finishes
  useEffect(() => {
    if (!selectedLectureId) return;

    async function loadData() {
      try {
        setIsLoadingTranscript(true);
        setIsLoadingTopics(true);
        setActionError(null);

        const [tSegments, tTopics] = await Promise.allSettled([
          lectureService.getTranscript(selectedLectureId!),
          lectureService.getTopics(selectedLectureId!),
        ]);

        if (tSegments.status === 'fulfilled') {
          setSegments(tSegments.value);
        } else {
          setSegments([]);
        }

        if (tTopics.status === 'fulfilled') {
          setTopics(tTopics.value);
        } else {
          setTopics([]);
        }
      } finally {
        setIsLoadingTranscript(false);
        setIsLoadingTopics(false);
      }
    }
    loadData();
  }, [selectedLectureId, jobStatus]);

  const selectedLecture = lectures.find((l) => l.id === selectedLectureId);

  const handleStartTranscription = async () => {
    if (!selectedLectureId) return;
    try {
      setActionError(null);
      setActiveJobType('transcription');
      const res = await lectureService.transcribeLecture(selectedLectureId, asrProvider);
      setActiveJobId(res.job_id);
    } catch (err: unknown) {
      setActionError(err instanceof Error ? err.message : 'Failed to launch transcription.');
      setActiveJobType(null);
    }
  };

  const handleStartTopicSegmentation = async () => {
    if (!selectedLectureId) return;
    try {
      setActionError(null);
      setActiveJobType('topic_segmentation');
      const res = await lectureService.segmentTopics(selectedLectureId);
      setActiveJobId(res.job_id);
    } catch (err: unknown) {
      setActionError(err instanceof Error ? err.message : 'Failed to launch topic segmentation.');
      setActiveJobType(null);
    }
  };

  const handleStartSignalAnalysis = async () => {
    if (!selectedLectureId) return;
    try {
      setActionError(null);
      setActiveJobType('confusion_analysis');
      const res = await lectureService.analyzeSignals(selectedLectureId);
      setActiveJobId(res.job_id);
    } catch (err: unknown) {
      setActionError(err instanceof Error ? err.message : 'Failed to launch signal analysis.');
      setActiveJobType(null);
    }
  };

  const formatTimestamp = (seconds: number) => {
    const mins = Math.floor(seconds / 60);
    const secs = Math.floor(seconds % 60);
    const ms = Math.floor((seconds % 1) * 10);
    return `${mins.toString().padStart(2, '0')}:${secs.toString().padStart(2, '0')}.${ms}`;
  };

  const totalWords = segments.reduce((acc, s) => acc + (s.words ? s.words.length : s.text.split(' ').length), 0);

  return (
    <div className="space-y-6" data-testid="view-analysis">
      {/* Header */}
      <div className="flex flex-col md:flex-row md:items-center justify-between gap-4 pb-4 border-b border-slate-800">
        <div>
          <div className="flex items-center gap-2 mb-1">
            <span className="text-xs font-semibold tracking-wider text-indigo-400 uppercase">Phase 3 Cognitive Engine</span>
            <Badge variant="indigo" size="sm">Topics & Signals</Badge>
          </div>
          <h1 className="text-2xl font-bold tracking-tight text-white flex items-center gap-2">
            <BarChart3 className="w-6 h-6 text-indigo-400" />
            Lecture Timeline & Transcript Segments
          </h1>
          <p className="text-slate-400 text-sm mt-1">
            Hierarchical topic clustering, empirical hesitation signals, and deterministic 3D pedagogical coordinates $(x, y, z)$.
          </p>
        </div>

        {lectures.length > 0 && (
          <div className="flex items-center gap-2.5">
            <select
              value={selectedLectureId || ''}
              onChange={(e) => setSelectedLectureId(e.target.value)}
              className="bg-slate-900 border border-slate-800 rounded-xl px-3 py-2 text-xs font-medium text-slate-200 focus:outline-none focus:border-indigo-500 max-w-xs truncate"
              data-testid="lecture-select"
            >
              {lectures.map((lec) => (
                <option key={lec.id} value={lec.id}>
                  {lec.title} ({Math.round(lec.duration_seconds)}s)
                </option>
              ))}
            </select>
          </div>
        )}
      </div>

      {actionError && (
        <Alert severity="critical" title="Pipeline Error">
          {actionError}
        </Alert>
      )}

      {isLoadingLectures ? (
        <div className="py-12 text-center text-sm text-slate-400">
          <RefreshCw className="w-6 h-6 animate-spin mx-auto text-indigo-400 mb-2" />
          Loading ingested lectures...
        </div>
      ) : lectures.length === 0 ? (
        <Card className="text-center py-12 space-y-4">
          <Mic className="w-12 h-12 text-slate-600 mx-auto" />
          <div>
            <h3 className="text-base font-semibold text-white">No Lectures Available for Analysis</h3>
            <p className="text-xs text-slate-400 mt-1">Ingest a lecture video or audio file first to generate transcripts.</p>
          </div>
          {onNavigate && (
            <Button variant="primary" size="md" onClick={() => onNavigate('upload')}>
              Go to Ingestion View
            </Button>
          )}
        </Card>
      ) : (
        <div className="space-y-6">
          {/* Lecture Status & Pipeline Controls Card */}
          <Card className="space-y-4">
            <div className="flex flex-col lg:flex-row lg:items-center justify-between gap-4">
              <div>
                <h3 className="text-lg font-bold text-white">{selectedLecture?.title}</h3>
                <div className="flex flex-wrap items-center gap-3 text-xs text-slate-400 mt-1">
                  <span>Source: <strong className="text-slate-200">{selectedLecture?.source_type}</strong></span>
                  <span>&bull;</span>
                  <span>Duration: <strong className="text-slate-200">{Math.round(selectedLecture?.duration_seconds || 0)}s</strong></span>
                  <span>&bull;</span>
                  <span>Topics: <strong className="text-indigo-400">{topics.length}</strong></span>
                  <span>&bull;</span>
                  <span>Segments: <strong className="text-indigo-400">{segments.length}</strong></span>
                </div>
              </div>

              {/* Action Buttons */}
              <div className="flex flex-wrap items-center gap-2">
                {/* ASR Dropdown and Button */}
                <select
                  value={asrProvider}
                  onChange={(e) => setAsrProvider(e.target.value)}
                  disabled={Boolean(activeJobId && jobStatus === 'running')}
                  className="bg-slate-950 border border-slate-800 rounded-lg px-2.5 py-1.5 text-xs text-slate-200 focus:outline-none"
                >
                  <option value="auto">Auto (Gemini / Mistral / Whisper)</option>
                  <option value="gemini_audio">Gemini Audio</option>
                  <option value="mistral_voxtral">Mistral Voxtral</option>
                  <option value="faster_whisper">Faster Whisper (Local)</option>
                </select>

                <Button
                  variant="primary"
                  size="sm"
                  onClick={handleStartTranscription}
                  isLoading={Boolean(activeJobId && activeJobType === 'transcription' && jobStatus === 'running')}
                  disabled={Boolean(activeJobId && jobStatus === 'running')}
                >
                  <Play className="w-3.5 h-3.5 mr-1 inline" /> Transcribe
                </Button>

                <Button
                  variant="secondary"
                  size="sm"
                  onClick={handleStartTopicSegmentation}
                  isLoading={Boolean(activeJobId && activeJobType === 'topic_segmentation' && jobStatus === 'running')}
                  disabled={Boolean(activeJobId && jobStatus === 'running') || segments.length === 0}
                  title={segments.length === 0 ? 'Transcribe lecture first' : 'Segment topics via LLM'}
                >
                  <Layers className="w-3.5 h-3.5 mr-1 inline text-indigo-400" /> Segment Topics
                </Button>

                <Button
                  variant="secondary"
                  size="sm"
                  onClick={handleStartSignalAnalysis}
                  isLoading={Boolean(activeJobId && activeJobType === 'confusion_analysis' && jobStatus === 'running')}
                  disabled={Boolean(activeJobId && jobStatus === 'running') || segments.length === 0}
                  title={segments.length === 0 ? 'Transcribe lecture first' : 'Analyze cognitive signals'}
                >
                  <Activity className="w-3.5 h-3.5 mr-1 inline text-amber-400" /> Analyze Signals
                </Button>
              </div>
            </div>

            {/* Active Polling Progress Bar */}
            {activeJobId && (
              <div className="pt-2 border-t border-slate-800/80 space-y-2" data-testid="transcription-progress">
                <div className="flex justify-between text-xs text-slate-300">
                  <span className="flex items-center gap-1.5">
                    <RefreshCw className={`w-3.5 h-3.5 ${jobStatus === 'running' ? 'animate-spin text-indigo-400' : ''}`} />
                    Job: <strong className="uppercase">{activeJobType?.replace('_', ' ')}</strong> &bull; Status: <strong className="uppercase">{jobStatus || 'Running'}</strong>
                  </span>
                  <span>{jobProgress}%</span>
                </div>
                <Progress
                  value={jobProgress}
                  severity={jobStatus === 'done' ? 'low' : jobStatus === 'failed' ? 'critical' : 'medium'}
                />
                {jobStatus === 'done' && (
                  <Alert severity="low" title="Pipeline Task Completed">
                    {activeJobType === 'topic_segmentation'
                      ? `Generated hierarchical topic outline and computed 3D coordinates.`
                      : activeJobType === 'confusion_analysis'
                      ? `Extracted empirical cognitive hesitation spikes and linked evidence.`
                      : `Generated word timestamps and updated 3D coordinates.`}
                  </Alert>
                )}
                {jobStatus === 'failed' && (
                  <Alert severity="critical" title="Pipeline Job Failed">
                    {jobError || job?.error_message || 'Job execution failed.'}
                  </Alert>
                )}
              </div>
            )}
          </Card>

          {/* Transcript Summary Metrics */}
          {segments.length > 0 && (
            <div className="grid grid-cols-2 sm:grid-cols-4 gap-3">
              <div className="p-3 bg-slate-900 border border-slate-800 rounded-xl">
                <span className="text-[11px] text-slate-400 uppercase">Topics</span>
                <div className="text-xl font-bold text-indigo-400 mt-1">{topics.length}</div>
              </div>
              <div className="p-3 bg-slate-900 border border-slate-800 rounded-xl">
                <span className="text-[11px] text-slate-400 uppercase">Segments</span>
                <div className="text-xl font-bold text-white mt-1">{segments.length}</div>
              </div>
              <div className="p-3 bg-slate-900 border border-slate-800 rounded-xl">
                <span className="text-[11px] text-slate-400 uppercase">Speech Rate</span>
                <div className="text-xl font-bold text-emerald-400 mt-1">
                  {selectedLecture?.duration_seconds ? Math.round((totalWords / selectedLecture.duration_seconds) * 60) : 0} WPM
                </div>
              </div>
              <div className="p-3 bg-slate-900 border border-slate-800 rounded-xl">
                <span className="text-[11px] text-slate-400 uppercase">Coordinate Baseline</span>
                <div className="text-xs font-mono text-amber-400 mt-2">
                  y = 0.0, z = 0.0
                </div>
              </div>
            </div>
          )}

          {/* SECTION 1: Topics Hierarchy */}
          <div className="space-y-3">
            <div className="flex items-center justify-between">
              <h2 className="text-base font-bold text-white flex items-center gap-2">
                <Layers className="w-5 h-5 text-indigo-400" />
                Hierarchical Topics ({topics.length})
              </h2>
            </div>

            {isLoadingTopics ? (
              <div className="py-4 text-center text-xs text-slate-400">
                <RefreshCw className="w-4 h-4 animate-spin mx-auto text-indigo-400 mb-1" />
                Loading topics...
              </div>
            ) : topics.length === 0 ? (
              <Card className="text-center py-6 text-xs text-slate-400">
                No topic outline generated yet. Click &quot;Segment Topics&quot; to outline topics with LLM.
              </Card>
            ) : (
              <div className="space-y-3" data-testid="topics-tree-list">
                {topics.map((t, idx) => {
                  const isSubtopic = t.depth > 0;
                  const confusionIntensity = t.coordinates?.y ?? 0;
                  return (
                    <Card
                      key={t.id || idx}
                      variant="default"
                      className={`space-y-2 p-3 transition-all ${
                        isSubtopic ? 'ml-6 border-l-4 border-l-indigo-500 bg-slate-900/60' : 'bg-slate-900'
                      }`}
                    >
                      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-2">
                        <div className="flex items-center gap-2">
                          <Badge variant={isSubtopic ? 'default' : 'indigo'} size="sm">
                            {isSubtopic ? `Subtopic (Depth ${t.depth})` : 'Main Topic'}
                          </Badge>
                          <span className="text-xs font-mono text-slate-300 bg-slate-950 px-2 py-0.5 rounded border border-slate-800">
                            {formatTimestamp(t.start_time)} &rarr; {formatTimestamp(t.end_time)}
                          </span>
                        </div>

                        <div className="flex items-center gap-2">
                          <Badge variant="default" size="sm">
                            Coord: ({t.coordinates?.x?.toFixed(1) ?? 0}, {t.coordinates?.y?.toFixed(1) ?? 0}, {t.coordinates?.z?.toFixed(1) ?? 0})
                          </Badge>
                        </div>
                      </div>

                      <div>
                        <h4 className="text-sm font-semibold text-white">{t.title}</h4>
                        <p className="text-slate-300 text-xs mt-1 leading-relaxed">{t.summary}</p>
                      </div>

                      {/* Confusion Density Indicator */}
                      <div className="pt-1.5 border-t border-slate-800/60 flex items-center justify-between gap-2 text-xs">
                        <div className="flex items-center gap-2 flex-1 max-w-xs">
                          <span className="text-slate-400 text-[11px]">Confusion:</span>
                          <div className="flex-1">
                            <Progress
                              value={confusionIntensity}
                              severity={confusionIntensity > 50 ? 'critical' : confusionIntensity > 20 ? 'medium' : 'low'}
                            />
                          </div>
                          <span className={`font-mono text-[11px] font-semibold ${confusionIntensity > 50 ? 'text-red-400' : 'text-slate-300'}`}>
                            {confusionIntensity.toFixed(0)}%
                          </span>
                        </div>

                        {onNavigate && confusionIntensity > 0 && (
                          <button
                            onClick={() => onNavigate('evidence')}
                            className="text-xs text-indigo-400 hover:text-indigo-300 font-medium"
                          >
                            Inspect Evidence &rarr;
                          </button>
                        )}
                      </div>
                    </Card>
                  );
                })}
              </div>
            )}
          </div>

          {/* SECTION 2: Transcript Segment Timeline */}
          <div className="space-y-3 pt-2">
            <div className="flex items-center justify-between">
              <h2 className="text-base font-bold text-white flex items-center gap-2">
                <BarChart3 className="w-5 h-5 text-indigo-400" />
                Transcript Segments ({segments.length})
              </h2>
            </div>

            {isLoadingTranscript ? (
              <div className="py-8 text-center text-sm text-slate-400">
                <RefreshCw className="w-5 h-5 animate-spin mx-auto text-indigo-400 mb-1.5" />
                Loading transcript segments...
              </div>
            ) : segments.length === 0 ? (
              <Card className="text-center py-8 text-sm text-slate-400">
                No transcript segments found for this lecture. Click &quot;Transcribe&quot; above to run speech-to-text.
              </Card>
            ) : (
              <div className="space-y-3" data-testid="transcript-segments-list">
                {segments.map((seg, idx) => {
                  const isExpanded = expandedSegmentId === seg.id;
                  return (
                    <Card key={seg.id || idx} variant="default" className="space-y-2 p-4">
                      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-2">
                        <div className="flex items-center gap-2">
                          <span className="w-6 h-6 rounded-md bg-indigo-950 border border-indigo-800 text-indigo-300 text-xs font-mono flex items-center justify-center font-bold">
                            {idx + 1}
                          </span>
                          <span className="text-xs font-mono text-slate-300 bg-slate-950 px-2 py-0.5 rounded border border-slate-800">
                            {formatTimestamp(seg.start_time)} &rarr; {formatTimestamp(seg.end_time)}
                          </span>
                          {seg.speaker && (
                            <Badge variant="default" size="sm">{seg.speaker}</Badge>
                          )}
                        </div>

                        <div className="flex items-center gap-2">
                          <Badge variant="default" size="sm">
                            Coord: ({seg.coordinates?.x?.toFixed(1) ?? 0}, {seg.coordinates?.y?.toFixed(1) ?? 0}, {seg.coordinates?.z?.toFixed(1) ?? 0})
                          </Badge>
                          {seg.words && seg.words.length > 0 && (
                            <button
                              onClick={() => setExpandedSegmentId(isExpanded ? null : (seg.id || `seg-${idx}`))}
                              className="text-xs text-indigo-400 hover:text-indigo-300 flex items-center gap-0.5"
                            >
                              <span>{seg.words.length} words</span>
                              <ChevronDown className={`w-3.5 h-3.5 transition-transform ${isExpanded ? 'rotate-180' : ''}`} />
                            </button>
                          )}
                        </div>
                      </div>

                      <p className="text-slate-100 text-sm leading-relaxed">{seg.text}</p>

                      {/* Word-Level Timestamps Drawer */}
                      {isExpanded && seg.words && seg.words.length > 0 && (
                        <div className="pt-2 border-t border-slate-800/80">
                          <div className="text-[11px] text-slate-400 font-semibold mb-1.5 uppercase tracking-wider">
                            Word-Level Timestamps:
                          </div>
                          <div className="flex flex-wrap gap-1.5">
                            {seg.words.map((w, wIdx) => (
                              <span
                                key={wIdx}
                                className="inline-flex items-center gap-1 px-2 py-0.5 rounded bg-slate-950 border border-slate-800 text-xs text-slate-300"
                                title={`Start: ${w.start}s, End: ${w.end}s${w.probability ? `, Prob: ${(w.probability * 100).toFixed(0)}%` : ''}`}
                              >
                                <span className="font-medium text-white">{w.word}</span>
                                <span className="text-[10px] font-mono text-slate-500">{w.start.toFixed(2)}s</span>
                              </span>
                            ))}
                          </div>
                        </div>
                      )}
                    </Card>
                  );
                })}
              </div>
            )}
          </div>
        </div>
      )}
    </div>
  );
};
