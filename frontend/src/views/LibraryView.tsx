import React, { useEffect, useState } from 'react';
import { BookOpen, Video, Clock, CheckCircle2, ChevronRight, Trash2, RefreshCw, PlusCircle } from 'lucide-react';
import { Card, Badge, Button, Alert } from '../components/ui';
import { lectureService } from '../services/lectureService';
import { Lecture, ViewId } from '../types';

interface LibraryViewProps {
  onNavigate?: (view: ViewId) => void;
}

export const LibraryView: React.FC<LibraryViewProps> = ({ onNavigate }) => {
  const [lectures, setLectures] = useState<Lecture[]>([]);
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [deletingId, setDeletingId] = useState<string | null>(null);

  const fetchLectures = async () => {
    try {
      setIsLoading(true);
      setError(null);
      const data = await lectureService.listLectures();
      setLectures(data);
    } catch (err: unknown) {
      setError(err instanceof Error ? err.message : 'Failed to load lectures.');
    } finally {
      setIsLoading(false);
    }
  };

  useEffect(() => {
    fetchLectures();
  }, []);

  const handleDelete = async (lectureId: string) => {
    if (!window.confirm('Are you sure you want to delete this lecture and all associated audio/analysis files?')) {
      return;
    }

    try {
      setDeletingId(lectureId);
      await lectureService.deleteLecture(lectureId);
      setLectures((prev) => prev.filter((l) => l.id !== lectureId));
    } catch (err: unknown) {
      alert(err instanceof Error ? err.message : 'Failed to delete lecture');
    } finally {
      setDeletingId(null);
    }
  };

  const formatDuration = (seconds: number) => {
    if (!seconds || seconds <= 0) return '0:00';
    const mins = Math.floor(seconds / 60);
    const secs = Math.floor(seconds % 60);
    if (mins >= 60) {
      const hrs = Math.floor(mins / 60);
      const remMins = mins % 60;
      return `${hrs}h ${remMins}m`;
    }
    return `${mins}m ${secs.toString().padStart(2, '0')}s`;
  };

  return (
    <div className="space-y-6" data-testid="view-library">
      <div className="flex flex-col md:flex-row md:items-center justify-between gap-4 pb-4 border-b border-slate-800">
        <div>
          <div className="flex items-center gap-2 mb-1">
            <span className="text-xs font-semibold tracking-wider text-indigo-400 uppercase">Archive</span>
            <Badge variant="indigo" size="sm">{lectures.length} Ingested</Badge>
          </div>
          <h1 className="text-2xl font-bold tracking-tight text-white flex items-center gap-2">
            <BookOpen className="w-6 h-6 text-indigo-400" />
            Lecture Library
          </h1>
          <p className="text-slate-400 text-sm mt-1">
            Browse ingested lectures, view pedagogical coordinates, and access drill-down analytics.
          </p>
        </div>

        <div className="flex items-center gap-2">
          <Button variant="secondary" size="sm" onClick={fetchLectures} isLoading={isLoading}>
            <RefreshCw className="w-3.5 h-3.5 mr-1.5 inline" /> Refresh
          </Button>
          {onNavigate && (
            <Button variant="primary" size="sm" onClick={() => onNavigate('upload')}>
              <PlusCircle className="w-3.5 h-3.5 mr-1.5 inline" /> Ingest New
            </Button>
          )}
        </div>
      </div>

      {error && (
        <Alert severity="critical" title="Failed to Load Lectures">
          {error}
        </Alert>
      )}

      {isLoading ? (
        <div className="py-12 text-center text-sm text-slate-400">
          <RefreshCw className="w-6 h-6 animate-spin mx-auto text-indigo-400 mb-2" />
          Loading lectures from ClassSense database...
        </div>
      ) : lectures.length === 0 ? (
        <Card className="text-center py-12 space-y-4">
          <BookOpen className="w-12 h-12 text-slate-600 mx-auto" />
          <div>
            <h3 className="text-base font-semibold text-white">No Lectures Ingested Yet</h3>
            <p className="text-xs text-slate-400 mt-1">Upload a video/audio file or submit a YouTube URL to get started.</p>
          </div>
          {onNavigate && (
            <Button variant="primary" size="md" onClick={() => onNavigate('upload')}>
              Go to Ingestion <ChevronRight className="w-4 h-4 ml-1 inline" />
            </Button>
          )}
        </Card>
      ) : (
        <div className="grid grid-cols-1 gap-4" data-testid="lectures-list">
          {lectures.map((lec) => {
            const statusSeverity =
              lec.status === 'ready'
                ? 'low'
                : lec.status === 'processing'
                ? 'medium'
                : lec.status === 'failed'
                ? 'critical'
                : 'high';

            return (
              <Card key={lec.id} variant="interactive" className="flex flex-col sm:flex-row sm:items-center justify-between gap-4">
                <div className="flex items-start gap-3.5 flex-1 min-w-0">
                  <div className="p-2.5 rounded-xl bg-slate-800/80 border border-slate-700/80 text-indigo-400 shrink-0">
                    <Video className="w-5 h-5" />
                  </div>
                  <div className="space-y-1 min-w-0 flex-1">
                    <div className="flex items-center gap-2 flex-wrap">
                      <h4 className="font-semibold text-white text-base truncate">{lec.title}</h4>
                      <Badge variant={lec.source_type === 'youtube' ? 'medium' : 'default'} size="sm">
                        {lec.source_type}
                      </Badge>
                      <Badge variant={statusSeverity} size="sm" className="flex items-center gap-1">
                        {lec.status === 'ready' && <CheckCircle2 className="w-3 h-3" />}
                        {lec.status.toUpperCase()}
                      </Badge>
                    </div>

                    <div className="flex items-center gap-4 text-xs text-slate-400 flex-wrap">
                      <span className="flex items-center gap-1">
                        <Clock className="w-3.5 h-3.5" />
                        {formatDuration(lec.duration_seconds)}
                      </span>
                      <span>
                        3D Coord: ({lec.coordinates?.x?.toFixed(1) ?? 0}, {lec.coordinates?.y?.toFixed(1) ?? 0}, {lec.coordinates?.z?.toFixed(1) ?? 0})
                      </span>
                    </div>
                  </div>
                </div>

                <div className="flex items-center gap-2 shrink-0">
                  {onNavigate && (
                    <Button variant="secondary" size="sm" onClick={() => onNavigate('analysis')}>
                      Analysis <ChevronRight className="w-4 h-4 ml-1 inline" />
                    </Button>
                  )}
                  <Button
                    variant="ghost"
                    size="sm"
                    className="text-rose-400 hover:text-rose-300 hover:bg-rose-950/30"
                    onClick={() => handleDelete(lec.id)}
                    disabled={deletingId === lec.id}
                    aria-label="Delete lecture"
                  >
                    <Trash2 className="w-4 h-4" />
                  </Button>
                </div>
              </Card>
            );
          })}
        </div>
      )}
    </div>
  );
};
