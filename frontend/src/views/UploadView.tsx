import React, { useRef, useState, useEffect } from 'react';
import {
  UploadCloud,
  Youtube,
  FileVideo,
  ArrowRight,
  CheckCircle2,
  RefreshCw,
  AlertCircle,
  Loader2,
  Clock,
  Sparkles,
} from 'lucide-react';
import { Card, Badge, Button, Progress, Alert } from '../components/ui';
import { lectureService, YouTubeIngestPayload } from '../services/lectureService';
import { useJobPolling } from '../hooks/useJobPolling';
import { PipelineStageInfo, ViewId } from '../types';

interface UploadViewProps {
  onNavigate?: (view: ViewId) => void;
}

const PIPELINE_STAGE_CONFIG: Array<{ key: string; label: string; description: string }> = [
  { key: 'transcribe', label: 'Speech-to-Text', description: 'Faster-Whisper / Voxtral word timestamps' },
  { key: 'segment_topics', label: 'Topic Segmentation', description: 'Hierarchical outline and pedagogical depth' },
  { key: 'confusion', label: 'Confusion Signals', description: 'Acoustic and linguistic cognitive friction' },
  { key: 'misconceptions', label: 'Misconceptions', description: 'Flawed intuitions and prerequisite gaps' },
  { key: 'prerequisites', label: 'Prerequisites', description: 'Upstream concept tracing & vector distance' },
  { key: 'interventions', label: 'Interventions', description: 'Targeted recaps, diagnostic checks & pacing' },
  { key: 'student_catchup', label: 'Student Catch-Up', description: 'Concrete analogies and progressive practice' },
  { key: 'report', label: 'Pedagogy Report', description: 'Pedagogy audit, clarity scores & recommendations' },
];

export const UploadView: React.FC<UploadViewProps> = ({ onNavigate }) => {
  const [sourceType, setSourceType] = useState<'upload' | 'youtube'>('upload');
  const [title, setTitle] = useState('');
  const [youtubeUrl, setYoutubeUrl] = useState('');
  const [selectedFile, setSelectedFile] = useState<File | null>(null);
  const [autoAnalyze, setAutoAnalyze] = useState(false);
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [submitError, setSubmitError] = useState<string | null>(null);

  const [lectureId, setLectureId] = useState<string | null>(null);
  const [ingestJobId, setIngestJobId] = useState<string | null>(null);
  const [pipelineJobId, setPipelineJobId] = useState<string | null>(null);
  const [isRetrying, setIsRetrying] = useState(false);

  const fileInputRef = useRef<HTMLInputElement>(null);

  // Poll Ingestion Job
  const {
    job: ingestJob,
    status: ingestStatus,
    progress: ingestProgress,
    error: ingestError,
  } = useJobPolling(ingestJobId);

  // Poll Pipeline Job
  const {
    job: pipelineJob,
    status: pipelineStatus,
    progress: pipelineProgress,
    error: pipelineError,
  } = useJobPolling(pipelineJobId);

  // When ingestion completes and auto_analyze was requested, ensure pipeline job ID is set
  useEffect(() => {
    if (ingestStatus === 'done' && autoAnalyze && lectureId && !pipelineJobId) {
      // Trigger or connect to pipeline job
      lectureService.analyzeLecture(lectureId, { resume: false })
        .then((pJob) => setPipelineJobId(pJob.id))
        .catch((err) => setSubmitError(err instanceof Error ? err.message : 'Failed to launch analysis pipeline.'));
    }
  }, [ingestStatus, autoAnalyze, lectureId, pipelineJobId]);

  const handleFileChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    if (e.target.files && e.target.files[0]) {
      setSelectedFile(e.target.files[0]);
      if (!title) {
        const cleanTitle = e.target.files[0].name.replace(/\.[^/.]+$/, '').replace(/[-_]/g, ' ');
        setTitle(cleanTitle.charAt(0).toUpperCase() + cleanTitle.slice(1));
      }
    }
  };

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setSubmitError(null);

    try {
      setIsSubmitting(true);
      if (sourceType === 'upload') {
        if (!selectedFile) {
          throw new Error('Please select an audio or video file to upload.');
        }
        const res = await lectureService.uploadLectureMedia(selectedFile, title, autoAnalyze);
        setLectureId(res.lecture_id);
        setIngestJobId(res.job_id);
        if (res.analyze_job_id) {
          setPipelineJobId(res.analyze_job_id);
        }
      } else {
        if (!youtubeUrl || !youtubeUrl.trim()) {
          throw new Error('Please enter a valid YouTube video URL.');
        }
        const ytPayload: YouTubeIngestPayload = {
          url: youtubeUrl.trim(),
          title: title.trim() || undefined,
        };
        if (autoAnalyze) {
          ytPayload.auto_analyze = true;
        }
        const res = await lectureService.ingestYouTubeLecture(ytPayload);
        setLectureId(res.lecture_id);
        setIngestJobId(res.job_id);
        if (res.analyze_job_id) {
          setPipelineJobId(res.analyze_job_id);
        }
      }
    } catch (err: unknown) {
      setSubmitError(err instanceof Error ? err.message : 'Ingestion request failed.');
    } finally {
      setIsSubmitting(false);
    }
  };

  const handleRetryPipeline = async () => {
    if (!lectureId) return;
    try {
      setIsRetrying(true);
      setSubmitError(null);
      const resumedJob = await lectureService.analyzeLecture(lectureId, { resume: true });
      setPipelineJobId(resumedJob.id);
    } catch (err: unknown) {
      setSubmitError(err instanceof Error ? err.message : 'Failed to resume pipeline.');
    } finally {
      setIsRetrying(false);
    }
  };

  const handleManualStartAnalysis = async () => {
    if (!lectureId) return;
    try {
      setIsRetrying(true);
      setSubmitError(null);
      const newJob = await lectureService.analyzeLecture(lectureId, { resume: false });
      setPipelineJobId(newJob.id);
    } catch (err: unknown) {
      setSubmitError(err instanceof Error ? err.message : 'Failed to start analysis.');
    } finally {
      setIsRetrying(false);
    }
  };

  const handleReset = () => {
    setIngestJobId(null);
    setPipelineJobId(null);
    setLectureId(null);
    setSelectedFile(null);
    setTitle('');
    setYoutubeUrl('');
    setSubmitError(null);
  };

  // Derive stage dictionary from pipeline job payload
  const stagesRecord: Record<string, PipelineStageInfo> =
    (pipelineJob?.payload as { stages?: Record<string, PipelineStageInfo> })?.stages || {};

  const failedStageKey = (pipelineJob?.payload as { failed_stage?: string })?.failed_stage;
  const failedStageInfo = failedStageKey ? stagesRecord[failedStageKey] : null;

  const isIngesting = ingestJobId && ingestStatus !== 'done' && ingestStatus !== 'failed';
  const showPipelineStepper = Boolean(pipelineJobId || (ingestStatus === 'done' && autoAnalyze));

  return (
    <div className="space-y-6" data-testid="view-upload">
      <div className="flex flex-col md:flex-row md:items-center justify-between gap-4 pb-4 border-b border-slate-800">
        <div>
          <div className="flex items-center gap-2 mb-1">
            <span className="text-xs font-semibold tracking-wider text-indigo-400 uppercase">One-Click Pipeline</span>
            <Badge variant="indigo" size="sm">End-to-End Analysis</Badge>
          </div>
          <h1 className="text-2xl font-bold tracking-tight text-white flex items-center gap-2">
            <UploadCloud className="w-6 h-6 text-indigo-400" />
            Ingest Lecture Video / Audio
          </h1>
          <p className="text-slate-400 text-sm mt-1">
            Upload recordings or supply a YouTube URL. Ingest audio and execute all 8 pedagogical analysis stages in one unified workflow.
          </p>
        </div>
      </div>

      <div className="max-w-2xl mx-auto space-y-6">
        {/* Source Type Selector */}
        {!ingestJobId && (
          <div className="flex p-1 bg-slate-900 border border-slate-800 rounded-xl">
            <button
              type="button"
              onClick={() => { setSourceType('upload'); setSubmitError(null); }}
              className={`flex-1 py-2 text-xs font-semibold rounded-lg flex items-center justify-center gap-2 transition-colors ${
                sourceType === 'upload'
                  ? 'bg-indigo-600 text-white shadow-sm'
                  : 'text-slate-400 hover:text-slate-200'
              }`}
            >
              <FileVideo className="w-4 h-4" />
              Direct File Upload
            </button>
            <button
              type="button"
              onClick={() => { setSourceType('youtube'); setSubmitError(null); }}
              className={`flex-1 py-2 text-xs font-semibold rounded-lg flex items-center justify-center gap-2 transition-colors ${
                sourceType === 'youtube'
                  ? 'bg-indigo-600 text-white shadow-sm'
                  : 'text-slate-400 hover:text-slate-200'
              }`}
            >
              <Youtube className="w-4 h-4" />
              YouTube URL
            </button>
          </div>
        )}

        {/* Upload Form */}
        {!ingestJobId ? (
          <Card className="space-y-5">
            <form onSubmit={handleSubmit} className="space-y-4">
              <div>
                <label className="block text-xs font-medium text-slate-300 mb-1.5">Lecture Title</label>
                <input
                  key="lecture-title-input"
                  type="text"
                  placeholder="e.g., Deep Learning 101: Backpropagation Derivation"
                  value={title}
                  onChange={(e) => setTitle(e.target.value)}
                  className="w-full bg-slate-950 border border-slate-800 rounded-xl px-3.5 py-2.5 text-sm text-slate-100 focus:outline-none focus:border-indigo-500 placeholder:text-slate-600"
                />
              </div>

              {sourceType === 'upload' ? (
                <div key="upload-file-section">
                  <label className="block text-xs font-medium text-slate-300 mb-1.5">Media File (MP4, MKV, MOV, WAV, MP3, M4A)</label>
                  <input
                    type="file"
                    ref={fileInputRef}
                    onChange={handleFileChange}
                    accept="video/mp4,video/mkv,video/quicktime,video/webm,audio/wav,audio/mpeg,audio/mp4,audio/flac,audio/ogg"
                    className="hidden"
                    data-testid="file-input"
                  />
                  <div
                    onClick={() => fileInputRef.current?.click()}
                    className="border-2 border-dashed border-slate-800 hover:border-slate-700 rounded-xl p-8 text-center bg-slate-950/40 cursor-pointer transition-colors"
                  >
                    <UploadCloud className="w-10 h-10 text-indigo-400 mx-auto mb-2" />
                    {selectedFile ? (
                      <div>
                        <p className="text-sm font-semibold text-emerald-400">{selectedFile.name}</p>
                        <p className="text-xs text-slate-500 mt-1">{(selectedFile.size / (1024 * 1024)).toFixed(2)} MB &bull; Ready to ingest</p>
                      </div>
                    ) : (
                      <div>
                        <p className="text-sm font-medium text-slate-200">Click or drag lecture video or audio here</p>
                        <p className="text-xs text-slate-500 mt-1">Direct ffmpeg conversion to 16kHz mono 16-bit WAV</p>
                      </div>
                    )}
                  </div>
                </div>
              ) : (
                <div key="youtube-url-section">
                  <label className="block text-xs font-medium text-slate-300 mb-1.5">YouTube Lecture URL</label>
                  <input
                    key="youtube-url-input"
                    type="url"
                    placeholder="https://www.youtube.com/watch?v=..."
                    value={youtubeUrl}
                    onChange={(e) => setYoutubeUrl(e.target.value)}
                    className="w-full bg-slate-950 border border-slate-800 rounded-xl px-3.5 py-2.5 text-sm text-slate-100 focus:outline-none focus:border-indigo-500 placeholder:text-slate-600"
                  />
                  <p className="text-[11px] text-slate-500 mt-1">Accepts standard YouTube watch URLs, youtu.be, and Shorts.</p>
                </div>
              )}

              {/* Auto-Analyze Checkbox */}
              <div className="flex items-center gap-3 p-3 bg-slate-950/60 border border-slate-800/80 rounded-xl">
                <input
                  type="checkbox"
                  id="autoAnalyzeCheck"
                  checked={autoAnalyze}
                  onChange={(e) => setAutoAnalyze(e.target.checked)}
                  className="w-4 h-4 text-indigo-600 bg-slate-900 border-slate-700 rounded focus:ring-indigo-500"
                />
                <label htmlFor="autoAnalyzeCheck" className="text-xs text-slate-300 cursor-pointer select-none">
                  <span className="font-semibold text-slate-100">Automatically run full analysis pipeline</span> (transcribe, topics, confusion, misconceptions, prerequisites, interventions, catch-up, report)
                </label>
              </div>

              {submitError && (
                <Alert severity="critical" title="Submission Error">
                  {submitError}
                </Alert>
              )}

              <Button type="submit" variant="primary" className="w-full justify-center" disabled={isSubmitting}>
                {isSubmitting ? 'Starting Ingestion...' : 'Start Ingestion Pipeline'}
                <ArrowRight className="w-4 h-4 ml-1 inline" />
              </Button>
            </form>
          </Card>
        ) : (
          /* Live Pipeline & Stepper Card */
          <Card variant="glow" className="space-y-6" data-testid="upload-job-progress">
            {/* Header Status */}
            <div className="flex items-center justify-between border-b border-slate-800 pb-3">
              <div className="flex items-center gap-2">
                <Sparkles className="w-5 h-5 text-indigo-400" />
                <span className="text-base font-bold text-white">
                  {pipelineJobId ? 'Pedagogical Analysis Pipeline' : 'Audio Ingestion Pipeline'}
                </span>
                <Badge
                  variant={
                    pipelineStatus === 'done' || (!pipelineJobId && ingestStatus === 'done')
                      ? 'low'
                      : pipelineStatus === 'failed' || ingestStatus === 'failed'
                      ? 'critical'
                      : 'medium'
                  }
                  size="sm"
                >
                  {(pipelineStatus || ingestStatus || 'running').toUpperCase()}
                </Badge>
              </div>
              <span className="text-xs font-mono text-slate-400 truncate max-w-[160px]">
                {pipelineJobId || ingestJobId}
              </span>
            </div>

            {/* Ingestion Status Bar (if still ingesting) */}
            {isIngesting && (
              <div className="space-y-2 p-3 bg-slate-950/70 border border-slate-800 rounded-xl">
                <div className="flex justify-between text-xs text-slate-300 mb-1">
                  <span>Extracting 16kHz Mono Audio...</span>
                  <span>{ingestProgress}%</span>
                </div>
                <Progress
                  value={ingestProgress}
                  severity="medium"
                />
              </div>
            )}

            {/* Ingestion Failure Alert */}
            {ingestStatus === 'failed' && (
              <Alert severity="critical" title="Audio Ingestion Failed">
                {ingestError || ingestJob?.error_message || 'An error occurred during audio extraction.'}
              </Alert>
            )}

            {/* Overall Pipeline Progress */}
            {showPipelineStepper && (
              <div className="space-y-2">
                <Progress
                  value={pipelineProgress}
                  label={
                    pipelineStatus === 'done'
                      ? 'One-Click Pipeline Complete (100%)'
                      : pipelineStatus === 'failed'
                      ? 'Pipeline Halted on Error'
                      : `Overall Pipeline Progress: ${pipelineProgress}%`
                  }
                  severity={
                    pipelineStatus === 'done'
                      ? 'low'
                      : pipelineStatus === 'failed'
                      ? 'critical'
                      : 'medium'
                  }
                />
              </div>
            )}

            {/* Stage Stepper Driven by Job Polling */}
            {showPipelineStepper && (
              <div className="space-y-2">
                <p className="text-xs font-semibold text-slate-400 uppercase tracking-wider mb-2">
                  Analysis Pipeline Stages (8 Stages)
                </p>

                <div className="divide-y divide-slate-800/60 border border-slate-800/80 rounded-xl bg-slate-950/40 overflow-hidden">
                  {PIPELINE_STAGE_CONFIG.map(({ key, label, description }, index) => {
                    const stage = stagesRecord[key] || {
                      name: label,
                      status: 'pending',
                      progress_pct: 0,
                    };
                    const isDone = stage.status === 'done';
                    const isRunning = stage.status === 'running';
                    const isFailed = stage.status === 'failed';

                    return (
                      <div
                        key={key}
                        className={`p-3 flex items-center justify-between gap-3 transition-colors ${
                          isRunning
                            ? 'bg-indigo-950/20 border-l-2 border-indigo-500'
                            : isFailed
                            ? 'bg-rose-950/20 border-l-2 border-rose-500'
                            : isDone
                            ? 'bg-emerald-950/10'
                            : ''
                        }`}
                      >
                        <div className="flex items-center gap-3">
                          <div className="flex-shrink-0">
                            {isDone ? (
                              <CheckCircle2 className="w-5 h-5 text-emerald-400" />
                            ) : isRunning ? (
                              <Loader2 className="w-5 h-5 text-indigo-400 animate-spin" />
                            ) : isFailed ? (
                              <AlertCircle className="w-5 h-5 text-rose-400" />
                            ) : (
                              <Clock className="w-5 h-5 text-slate-600" />
                            )}
                          </div>
                          <div>
                            <div className="flex items-center gap-2">
                              <span className="text-xs font-mono text-slate-500">{index + 1}.</span>
                              <span className={`text-xs font-semibold ${isDone ? 'text-slate-200' : isRunning ? 'text-indigo-300 font-bold' : isFailed ? 'text-rose-300 font-bold' : 'text-slate-400'}`}>
                                {label}
                              </span>
                            </div>
                            <p className="text-[11px] text-slate-500 mt-0.5">{description}</p>
                          </div>
                        </div>

                        <div className="flex items-center gap-2">
                          <Badge
                            size="sm"
                            variant={
                              isDone ? 'low' : isFailed ? 'critical' : isRunning ? 'medium' : 'high'
                            }
                          >
                            {stage.status.toUpperCase()}
                          </Badge>
                        </div>
                      </div>
                    );
                  })}
                </div>
              </div>
            )}

            {/* Per-Stage Error Card & Retry Button */}
            {pipelineStatus === 'failed' && (
              <div className="space-y-3">
                <Alert severity="critical" title={`Pipeline Error: Stage '${failedStageInfo?.name || failedStageKey || 'Analysis'}' Failed`}>
                  <p className="text-xs text-rose-200 mt-1">
                    {failedStageInfo?.error || pipelineError || pipelineJob?.error_message || 'A stage failed during processing.'}
                  </p>
                  <p className="text-[11px] text-rose-300/80 mt-1">
                    Completed stages are preserved. Click below to resume pipeline execution from this stage.
                  </p>
                </Alert>

                <Button
                  variant="primary"
                  className="w-full justify-center"
                  onClick={handleRetryPipeline}
                  disabled={isRetrying}
                >
                  <RefreshCw className={`w-4 h-4 mr-2 inline ${isRetrying ? 'animate-spin' : ''}`} />
                  {isRetrying ? 'Resuming Pipeline...' : 'Retry / Resume Analysis'}
                </Button>
              </div>
            )}

            {/* Ingest Done without Auto-Analyze */}
            {!autoAnalyze && ingestStatus === 'done' && !pipelineJobId && (
              <div className="space-y-3">
                <Alert severity="low" title="Ingestion Ready">
                  Audio extracted and ready. Click below to start the unified 8-stage pedagogy analysis.
                </Alert>
                <Button
                  variant="primary"
                  className="w-full justify-center"
                  onClick={handleManualStartAnalysis}
                  disabled={isRetrying}
                >
                  <Sparkles className="w-4 h-4 mr-2 inline" />
                  Run Full Analysis Pipeline
                </Button>
              </div>
            )}

            {/* Success Alert & Actions */}
            {pipelineStatus === 'done' && (
              <Alert severity="low" title="All 8 Stages Analyzed Successfully">
                Full pedagogy analysis completed! Topics segmented, confusion moments flagged, potential misconceptions inferred from lecture speech,
                prerequisite knowledge graph traced, interventions generated, and comprehensive pedagogy audit report ready.
              </Alert>
            )}

            {/* Action Buttons */}
            <div className="flex gap-3 pt-2">
              {pipelineStatus === 'done' && onNavigate && (
                <Button
                  variant="primary"
                  className="flex-1 justify-center"
                  onClick={() => onNavigate('analysis')}
                >
                  <CheckCircle2 className="w-4 h-4 mr-1.5 inline" /> View Full Analysis
                </Button>
              )}
              <Button
                variant="secondary"
                className="justify-center"
                onClick={handleReset}
              >
                <RefreshCw className="w-4 h-4 mr-1.5 inline" /> Ingest Another
              </Button>
            </div>
          </Card>
        )}
      </div>
    </div>
  );
};
