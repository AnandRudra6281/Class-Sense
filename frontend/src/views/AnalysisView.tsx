import React, { useEffect, useState } from 'react';
import {
  BarChart3,
  Mic,
  Play,
  RefreshCw,
  ChevronDown,
} from 'lucide-react';
import { Card, Badge, Button, Progress, Alert } from '../components/ui';
import { lectureService } from '../services/lectureService';
import { useJobPolling } from '../hooks/useJobPolling';
import { Lecture, TranscriptSegment, ViewId } from '../types';

interface AnalysisViewProps {
  onNavigate?: (view: ViewId) => void;
}

export const AnalysisView: React.FC<AnalysisViewProps> = ({ onNavigate }) => {
  const [lectures, setLectures] = useState<Lecture[]>([]);
  const [selectedLectureId, setSelectedLectureId] = useState<string | null>(null);
  const [segments, setSegments] = useState<TranscriptSegment[]>([]);
  const [isLoadingLectures, setIsLoadingLectures] = useState(true);
  const [isLoadingTranscript, setIsLoadingTranscript] = useState(false);
  const [asrProvider, setAsrProvider] = useState<string>('auto');
  const [activeJobId, setActiveJobId] = useState<string | null>(null);
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

  // Fetch transcript when selected lecture changes
  useEffect(() => {
    if (!selectedLectureId) return;

    async function loadTranscript() {
      try {
        setIsLoadingTranscript(true);
        setActionError(null);
        const data = await lectureService.getTranscript(selectedLectureId!);
        setSegments(data);
      } catch (err: unknown) {
        // If 404 or empty, not transcribed yet
        setSegments([]);
      } finally {
        setIsLoadingTranscript(false);
      }
    }
    loadTranscript();
  }, [selectedLectureId, jobStatus]);

  const selectedLecture = lectures.find((l) => l.id === selectedLectureId);

  const handleStartTranscription = async () => {
    if (!selectedLectureId) return;
    try {
      setActionError(null);
      const res = await lectureService.transcribeLecture(selectedLectureId, asrProvider);
      setActiveJobId(res.job_id);
    } catch (err: unknown) {
      setActionError(err instanceof Error ? err.message : 'Failed to launch transcription.');
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
            <span className="text-xs font-semibold tracking-wider text-indigo-400 uppercase">Phase 2 Timeline</span>
            <Badge variant="indigo" size="sm">ASR & Word Timestamps</Badge>
          </div>
          <h1 className="text-2xl font-bold tracking-tight text-white flex items-center gap-2">
            <BarChart3 className="w-6 h-6 text-indigo-400" />
            Lecture Timeline & Transcript Segments
          </h1>
          <p className="text-slate-400 text-sm mt-1">
            Word-aligned transcript segments carrying deterministic 3D pedagogical coordinates $(x, y, z)$.
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
        <Alert severity="critical" title="Transcription Error">
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
          {/* Lecture Status & ASR Controls Card */}
          <Card className="space-y-4">
            <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-3">
              <div>
                <h3 className="text-lg font-bold text-white">{selectedLecture?.title}</h3>
                <div className="flex items-center gap-3 text-xs text-slate-400 mt-1">
                  <span>Source: {selectedLecture?.source_type}</span>
                  <span>&bull;</span>
                  <span>Duration: {Math.round(selectedLecture?.duration_seconds || 0)}s</span>
                  <span>&bull;</span>
                  <span>Status: <strong className="text-indigo-400 uppercase">{selectedLecture?.status}</strong></span>
                </div>
              </div>

              <div className="flex items-center gap-2">
                <select
                  value={asrProvider}
                  onChange={(e) => setAsrProvider(e.target.value)}
                  disabled={Boolean(activeJobId && jobStatus === 'running')}
                  className="bg-slate-950 border border-slate-800 rounded-lg px-2.5 py-1.5 text-xs text-slate-200 focus:outline-none"
                >
                  <option value="auto">Auto (Gemini / Mistral / Whisper)</option>
                  <option value="gemini_audio">Gemini Multimodal Audio</option>
                  <option value="mistral_voxtral">Mistral Voxtral</option>
                  <option value="faster_whisper">Faster Whisper (Local)</option>
                  <option value="openai_whisper">OpenAI Whisper (If key set)</option>
                  <option value="sarvam_ai">Sarvam AI (If key set)</option>
                </select>

                <Button
                  variant="primary"
                  size="sm"
                  onClick={handleStartTranscription}
                  isLoading={Boolean(activeJobId && jobStatus === 'running')}
                  disabled={Boolean(activeJobId && jobStatus === 'running')}
                >
                  <Play className="w-3.5 h-3.5 mr-1 inline" /> Transcribe
                </Button>
              </div>
            </div>

            {/* Active Polling Progress Bar */}
            {activeJobId && (
              <div className="pt-2 border-t border-slate-800/80 space-y-2" data-testid="transcription-progress">
                <div className="flex justify-between text-xs text-slate-300">
                  <span className="flex items-center gap-1.5">
                    <RefreshCw className={`w-3.5 h-3.5 ${jobStatus === 'running' ? 'animate-spin text-indigo-400' : ''}`} />
                    ASR Status: <strong className="uppercase">{jobStatus || 'Running'}</strong>
                  </span>
                  <span>{jobProgress}%</span>
                </div>
                <Progress
                  value={jobProgress}
                  severity={jobStatus === 'done' ? 'low' : jobStatus === 'failed' ? 'critical' : 'medium'}
                />
                {jobStatus === 'done' && (
                  <Alert severity="low" title="Transcription Completed">
                    Generated word timestamps and updated 3D coordinates.
                  </Alert>
                )}
                {jobStatus === 'failed' && (
                  <Alert severity="critical" title="Transcription Job Failed">
                    {jobError || job?.error_message || 'ASR execution failed.'}
                  </Alert>
                )}
              </div>
            )}
          </Card>

          {/* Transcript Summary Metrics */}
          {segments.length > 0 && (
            <div className="grid grid-cols-2 sm:grid-cols-4 gap-3">
              <div className="p-3 bg-slate-900 border border-slate-800 rounded-xl">
                <span className="text-[11px] text-slate-400 uppercase">Segments</span>
                <div className="text-xl font-bold text-white mt-1">{segments.length}</div>
              </div>
              <div className="p-3 bg-slate-900 border border-slate-800 rounded-xl">
                <span className="text-[11px] text-slate-400 uppercase">Total Words</span>
                <div className="text-xl font-bold text-indigo-400 mt-1">{totalWords}</div>
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

          {/* Transcript Segment Timeline */}
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
      )}
    </div>
  );
};
