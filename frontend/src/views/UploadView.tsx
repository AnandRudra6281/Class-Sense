import React, { useState } from 'react';
import { UploadCloud, Youtube, FileVideo, ArrowRight } from 'lucide-react';
import { Card, Badge, Button, Alert } from '../components/ui';

export const UploadView: React.FC = () => {
  const [sourceType, setSourceType] = useState<'upload' | 'youtube'>('upload');
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [submitted, setSubmitted] = useState(false);

  const handleSimulateUpload = (e: React.FormEvent) => {
    e.preventDefault();
    setIsSubmitting(true);
    setTimeout(() => {
      setIsSubmitting(false);
      setSubmitted(true);
    }, 600);
  };

  return (
    <div className="space-y-6" data-testid="view-upload">
      <div className="flex flex-col md:flex-row md:items-center justify-between gap-4 pb-4 border-b border-slate-800">
        <div>
          <div className="flex items-center gap-2 mb-1">
            <span className="text-xs font-semibold tracking-wider text-indigo-400 uppercase">Ingestion</span>
            <Badge variant="indigo" size="sm">Pipeline Entry</Badge>
          </div>
          <h1 className="text-2xl font-bold tracking-tight text-white flex items-center gap-2">
            <UploadCloud className="w-6 h-6 text-indigo-400" />
            Ingest Lecture Video / Audio
          </h1>
          <p className="text-slate-400 text-sm mt-1">
            Upload local MP4/WAV/MP3 recordings or supply a YouTube lecture URL to start transcription & analysis.
          </p>
        </div>
      </div>

      <div className="max-w-2xl mx-auto space-y-6">
        <div className="flex p-1 bg-slate-900 border border-slate-800 rounded-xl">
          <button
            type="button"
            onClick={() => { setSourceType('upload'); setSubmitted(false); }}
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
            onClick={() => { setSourceType('youtube'); setSubmitted(false); }}
            className={`flex-1 py-2 text-xs font-semibold rounded-lg flex items-center justify-center gap-2 transition-colors ${
              sourceType === 'youtube'
                ? 'bg-indigo-600 text-white shadow-sm'
                : 'text-slate-400 hover:text-slate-200'
            }`}
          >
            <Youtube className="w-4 h-4" />
            YouTube Link
          </button>
        </div>

        <Card className="space-y-5">
          <form onSubmit={handleSimulateUpload} className="space-y-4">
            <div>
              <label className="block text-xs font-medium text-slate-300 mb-1.5">Lecture Title</label>
              <input
                type="text"
                defaultValue="Lecture 04: Vector Calculus & Gradient Descent"
                className="w-full bg-slate-950 border border-slate-800 rounded-xl px-3.5 py-2.5 text-sm text-slate-100 focus:outline-none focus:border-indigo-500"
              />
            </div>

            {sourceType === 'upload' ? (
              <div>
                <label className="block text-xs font-medium text-slate-300 mb-1.5">Media File (MP4, MKV, WAV, MP3)</label>
                <div className="border-2 border-dashed border-slate-800 hover:border-slate-700 rounded-xl p-8 text-center bg-slate-950/40 cursor-pointer">
                  <UploadCloud className="w-10 h-10 text-indigo-400 mx-auto mb-2" />
                  <p className="text-sm font-medium text-slate-200">Drag and drop lecture audio or video</p>
                  <p className="text-xs text-slate-500 mt-1">Audio extracted via ffmpeg; local fast fallback available</p>
                </div>
              </div>
            ) : (
              <div>
                <label className="block text-xs font-medium text-slate-300 mb-1.5">YouTube Lecture URL</label>
                <input
                  type="url"
                  placeholder="https://www.youtube.com/watch?v=..."
                  defaultValue="https://www.youtube.com/watch?v=sample123"
                  className="w-full bg-slate-950 border border-slate-800 rounded-xl px-3.5 py-2.5 text-sm text-slate-100 focus:outline-none focus:border-indigo-500"
                />
              </div>
            )}

            <Button type="submit" variant="primary" className="w-full justify-center" disabled={isSubmitting}>
              {isSubmitting ? 'Submitting to Queue...' : 'Queue Ingestion Pipeline'}
              <ArrowRight className="w-4 h-4 ml-1 inline" />
            </Button>
          </form>

          {submitted && (
            <Alert severity="low" title="Ingestion Job Queued Successfully">
              Job ID: <span className="font-mono text-xs">job-phase0-mock-998</span>. Progress is trackable via background task polling.
            </Alert>
          )}
        </Card>
      </div>
    </div>
  );
};
