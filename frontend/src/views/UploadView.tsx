import React, { useRef, useState } from 'react';
import { UploadCloud, Youtube, FileVideo, ArrowRight, CheckCircle2, RefreshCw } from 'lucide-react';
import { Card, Badge, Button, Progress, Alert } from '../components/ui';
import { lectureService } from '../services/lectureService';
import { useJobPolling } from '../hooks/useJobPolling';
import { ViewId } from '../types';

interface UploadViewProps {
  onNavigate?: (view: ViewId) => void;
}

export const UploadView: React.FC<UploadViewProps> = ({ onNavigate }) => {
  const [sourceType, setSourceType] = useState<'upload' | 'youtube'>('upload');
  const [title, setTitle] = useState('');
  const [youtubeUrl, setYoutubeUrl] = useState('');
  const [selectedFile, setSelectedFile] = useState<File | null>(null);
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [submitError, setSubmitError] = useState<string | null>(null);
  const [activeJobId, setActiveJobId] = useState<string | null>(null);

  const fileInputRef = useRef<HTMLInputElement>(null);

  // Background Job Polling
  const { job, status: jobStatus, progress: jobProgress, error: jobError } = useJobPolling(activeJobId);

  const handleFileChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    if (e.target.files && e.target.files[0]) {
      setSelectedFile(e.target.files[0]);
      if (!title) {
        // Auto-populate title from filename
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
        const res = await lectureService.uploadLectureMedia(selectedFile, title);
        setActiveJobId(res.job_id);
      } else {
        if (!youtubeUrl || !youtubeUrl.trim()) {
          throw new Error('Please enter a valid YouTube video URL.');
        }
        const res = await lectureService.ingestYouTubeLecture({ url: youtubeUrl.trim(), title: title.trim() || undefined });
        setActiveJobId(res.job_id);
      }
    } catch (err: unknown) {
      setSubmitError(err instanceof Error ? err.message : 'Ingestion request failed.');
    } finally {
      setIsSubmitting(false);
    }
  };

  const handleReset = () => {
    setActiveJobId(null);
    setSelectedFile(null);
    setTitle('');
    setYoutubeUrl('');
    setSubmitError(null);
  };

  return (
    <div className="space-y-6" data-testid="view-upload">
      <div className="flex flex-col md:flex-row md:items-center justify-between gap-4 pb-4 border-b border-slate-800">
        <div>
          <div className="flex items-center gap-2 mb-1">
            <span className="text-xs font-semibold tracking-wider text-indigo-400 uppercase">Phase 1 Ingestion</span>
            <Badge variant="indigo" size="sm">FFmpeg 16kHz Mono</Badge>
          </div>
          <h1 className="text-2xl font-bold tracking-tight text-white flex items-center gap-2">
            <UploadCloud className="w-6 h-6 text-indigo-400" />
            Ingest Lecture Video / Audio
          </h1>
          <p className="text-slate-400 text-sm mt-1">
            Upload local MP4/WAV/MP3 recordings or supply a YouTube URL. ffmpeg automatically converts to 16kHz mono WAV.
          </p>
        </div>
      </div>

      <div className="max-w-2xl mx-auto space-y-6">
        {/* Source Type Selector */}
        {!activeJobId && (
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

        {/* Ingestion Form */}
        {!activeJobId ? (
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
          /* Live Background Job Progress Card */
          <Card variant="glow" className="space-y-5" data-testid="upload-job-progress">
            <div className="flex items-center justify-between">
              <div className="flex items-center gap-2">
                <span className="text-sm font-bold text-white">Ingestion Pipeline</span>
                <Badge
                  variant={
                    jobStatus === 'done'
                      ? 'low'
                      : jobStatus === 'failed'
                      ? 'critical'
                      : 'medium'
                  }
                  size="sm"
                >
                  {(jobStatus || 'running').toUpperCase()}
                </Badge>
              </div>
              <span className="text-xs font-mono text-slate-400 truncate max-w-[150px]">
                {activeJobId}
              </span>
            </div>

            <div className="space-y-2">
              <Progress
                value={jobProgress}
                label={
                  jobStatus === 'done'
                    ? 'Extraction and Ingestion Complete (100%)'
                    : jobStatus === 'failed'
                    ? 'Ingestion Failed'
                    : `Processing: ${jobProgress}%`
                }
                severity={
                  jobStatus === 'done'
                    ? 'low'
                    : jobStatus === 'failed'
                    ? 'critical'
                    : 'medium'
                }
              />
            </div>

            {/* Stages visualization */}
            <div className="grid grid-cols-3 gap-2 text-center text-xs">
              <div className={`p-2 rounded-lg border ${jobProgress >= 30 ? 'bg-indigo-950/40 border-indigo-800 text-indigo-300' : 'bg-slate-950 border-slate-800 text-slate-500'}`}>
                1. Media Ingestion
              </div>
              <div className={`p-2 rounded-lg border ${jobProgress >= 60 ? 'bg-indigo-950/40 border-indigo-800 text-indigo-300' : 'bg-slate-950 border-slate-800 text-slate-500'}`}>
                2. Metadata Probe
              </div>
              <div className={`p-2 rounded-lg border ${jobProgress >= 100 ? 'bg-emerald-950/40 border-emerald-800 text-emerald-300' : 'bg-slate-950 border-slate-800 text-slate-500'}`}>
                3. 16kHz WAV Ready
              </div>
            </div>

            {jobStatus === 'done' && (
              <Alert severity="low" title="Lecture Successfully Ingested">
                Extracted 16kHz mono audio and initialized 3D coordinates (0, 0, 0).
                The lecture is ready for Phase 2 topic segmentation and transcription.
              </Alert>
            )}

            {jobStatus === 'failed' && (
              <Alert severity="critical" title="Ingestion Failed">
                {jobError || job?.error_message || 'An error occurred during audio extraction.'}
              </Alert>
            )}

            <div className="flex gap-3 pt-2">
              {jobStatus === 'done' && onNavigate && (
                <Button
                  variant="primary"
                  className="flex-1 justify-center"
                  onClick={() => onNavigate('library')}
                >
                  <CheckCircle2 className="w-4 h-4 mr-1.5 inline" /> View in Lecture Library
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
