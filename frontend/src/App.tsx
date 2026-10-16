import React, { useState, useEffect } from 'react';
import { Navbar } from './components/layout/Navbar';
import { Card } from './components/ui/Card';
import { Button } from './components/ui/Button';
import { Badge } from './components/ui/Badge';
import { ProgressBar } from './components/ui/ProgressBar';
import { useJobPolling } from './hooks/useJobPolling';
import { jobService } from './services/jobService';
import { request } from './api/client';
import { mockLectureDetail } from './mocks/sampleLecture';
import { Layers, Cpu, Play, Compass, Database } from 'lucide-react';

interface HealthData {
  status: string;
  environment: string;
  version: string;
  providers: {
    asr: { active: string; enabled: boolean; model: string };
    llm: { active: string; enabled: boolean; model: string };
    embeddings: { active: string; enabled: boolean; model: string };
  };
  adapters: {
    openai_whisper: boolean;
    sarvam_ai: boolean;
  };
}

export const App: React.FC = () => {
  const [demoMode, setDemoMode] = useState<boolean>(false);
  const [health, setHealth] = useState<HealthData | null>(null);
  const [healthError, setHealthError] = useState<string | null>(null);
  const [activeJobId, setActiveJobId] = useState<string | null>(null);
  const [isStartingJob, setIsStartingJob] = useState<boolean>(false);

  // Background Job Polling Hook
  const { job, status: jobStatus, progress: jobProgress, error: jobError, isPolling } = useJobPolling(activeJobId);

  useEffect(() => {
    async function checkHealth() {
      try {
        const data = await request<HealthData>('/health');
        setHealth(data);
        setHealthError(null);
      } catch (err: unknown) {
        setHealthError(err instanceof Error ? err.message : 'Backend unreachable');
      }
    }
    checkHealth();
  }, []);

  const handleStartSimulatedJob = async () => {
    try {
      setIsStartingJob(true);
      const created = await jobService.createSimulatedJob('pipeline_verification', {
        test: true,
        steps: 3,
      });
      setActiveJobId(created.id);
    } catch (err: unknown) {
      alert(err instanceof Error ? err.message : 'Failed to launch background job');
    } finally {
      setIsStartingJob(false);
    }
  };

  return (
    <div className="min-h-screen bg-navy-950 text-slate-100 flex flex-col">
      <Navbar demoMode={demoMode} onToggleDemoMode={() => setDemoMode(!demoMode)} />

      <main className="flex-1 max-w-7xl w-full mx-auto px-4 sm:px-6 lg:px-8 py-8 space-y-8">
        {/* System Architecture Banner */}
        <section className="bg-gradient-to-r from-navy-900 via-indigo-950/40 to-navy-900 border border-slate-800 rounded-2xl p-6 shadow-2xl">
          <div className="flex flex-col md:flex-row md:items-center justify-between gap-6">
            <div className="space-y-2">
              <div className="flex items-center gap-3">
                <span className="text-2xl font-bold tracking-tight text-white">ClassSense Core Architecture</span>
                <Badge variant="success">Phase 1 Verified</Badge>
              </div>
              <p className="text-slate-300 text-sm max-w-2xl leading-relaxed">
                Full-stack foundation active: Provider interfaces (`ASRProvider`, `LLMProvider`, `EmbeddingProvider`),
                persisted background jobs with progress %, deterministic 3D pedagogical coordinates $(x, y, z)$,
                and Mistral structured JSON output with retry-once error recovery.
              </p>
            </div>

            <div className="flex items-center gap-3">
              <Button
                variant="primary"
                onClick={handleStartSimulatedJob}
                isLoading={isStartingJob || isPolling}
                leftIcon={<Play className="w-4 h-4" />}
              >
                Test Background Job
              </Button>
            </div>
          </div>
        </section>

        {/* Status Grid */}
        <div className="grid grid-cols-1 md:grid-cols-3 gap-6">
          {/* Active Providers Card */}
          <Card className="space-y-4">
            <div className="flex items-center justify-between">
              <h3 className="font-semibold text-slate-200 flex items-center gap-2">
                <Cpu className="w-4 h-4 text-indigo-400" />
                AI Providers
              </h3>
              <Badge variant={health ? 'success' : 'warning'}>
                {health ? 'Connected' : 'Checking'}
              </Badge>
            </div>

            {health ? (
              <div className="space-y-2.5 text-xs">
                <div className="flex justify-between items-center py-1.5 border-b border-slate-800">
                  <span className="text-slate-400">LLM Provider:</span>
                  <span className="font-mono text-indigo-300">{health.providers.llm.active} ({health.providers.llm.model})</span>
                </div>
                <div className="flex justify-between items-center py-1.5 border-b border-slate-800">
                  <span className="text-slate-400">ASR Provider:</span>
                  <span className="font-mono text-indigo-300">{health.providers.asr.active} ({health.providers.asr.model})</span>
                </div>
                <div className="flex justify-between items-center py-1.5 border-b border-slate-800">
                  <span className="text-slate-400">Embeddings:</span>
                  <span className="font-mono text-indigo-300">{health.providers.embeddings.model}</span>
                </div>
                <div className="flex justify-between items-center py-1.5 text-slate-400">
                  <span>Whisper / Sarvam:</span>
                  <span>{health.adapters.openai_whisper ? 'Enabled' : 'Disabled (Key missing)'}</span>
                </div>
              </div>
            ) : (
              <p className="text-xs text-slate-400">{healthError || 'Connecting to backend /api/v1/health...'}</p>
            )}
          </Card>

          {/* Background Job Runner & Polling Status */}
          <Card className="space-y-4">
            <div className="flex items-center justify-between">
              <h3 className="font-semibold text-slate-200 flex items-center gap-2">
                <Database className="w-4 h-4 text-emerald-400" />
                Background Job Pipeline
              </h3>
              {jobStatus && (
                <Badge
                  variant={
                    jobStatus === 'done'
                      ? 'success'
                      : jobStatus === 'failed'
                      ? 'error'
                      : 'indigo'
                  }
                >
                  {jobStatus.toUpperCase()}
                </Badge>
              )}
            </div>

            {job ? (
              <div className="space-y-3">
                <div className="text-xs font-mono text-slate-400 truncate">
                  Job ID: <span className="text-slate-200">{job.id}</span>
                </div>
                <ProgressBar progress={jobProgress} label="Execution Progress" />
                {job.result && (
                  <div className="p-2.5 rounded-lg bg-emerald-950/40 border border-emerald-800/40 text-xs text-emerald-300 font-mono">
                    {JSON.stringify(job.result)}
                  </div>
                )}
                {jobError && (
                  <div className="p-2.5 rounded-lg bg-rose-950/40 border border-rose-800/40 text-xs text-rose-300 font-mono">
                    {jobError}
                  </div>
                )}
              </div>
            ) : (
              <p className="text-xs text-slate-400">
                Click &quot;Test Background Job&quot; above to launch a persisted background worker and watch real-time polling in action.
              </p>
            )}
          </Card>

          {/* 3D Coordinate System Contract */}
          <Card className="space-y-4">
            <div className="flex items-center justify-between">
              <h3 className="font-semibold text-slate-200 flex items-center gap-2">
                <Compass className="w-4 h-4 text-amber-400" />
                3D Coordinate Contract
              </h3>
              <Badge variant="indigo">Three.js Ready</Badge>
            </div>

            <div className="space-y-2 text-xs text-slate-300">
              <div className="p-2 rounded-lg bg-slate-800/60 border border-slate-700/60 space-y-1">
                <div className="flex justify-between">
                  <span className="text-slate-400">X (Timeline):</span>
                  <span className="font-mono text-amber-300">x = (t / duration) * 100</span>
                </div>
                <div className="flex justify-between">
                  <span className="text-slate-400">Y (Confusion):</span>
                  <span className="font-mono text-amber-300">y = confusion_score * 100</span>
                </div>
                <div className="flex justify-between">
                  <span className="text-slate-400">Z (Topic Depth):</span>
                  <span className="font-mono text-amber-300">z = depth * 1.0</span>
                </div>
              </div>
              <p className="text-slate-400 text-[11px]">
                Every domain schema (lecture, segment, confusion point, prerequisite, intervention) carries deterministic (x, y, z) coordinates.
              </p>
            </div>
          </Card>
        </div>

        {/* Demo Mode / Mock Inspection View */}
        {demoMode && (
          <section className="space-y-4">
            <div className="flex items-center justify-between">
              <h2 className="text-lg font-bold text-white flex items-center gap-2">
                <Layers className="w-5 h-5 text-indigo-400" />
                Demo Mode: Mock Lecture Data (`src/mocks/`)
              </h2>
              <Badge variant="warning">Mock Data Active</Badge>
            </div>

            <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
              {/* Lecture Overview */}
              <Card className="space-y-3">
                <h4 className="font-medium text-slate-200">{mockLectureDetail.title}</h4>
                <div className="flex gap-4 text-xs text-slate-400">
                  <span>Duration: {mockLectureDetail.duration_seconds}s</span>
                  <span>Segments: {mockLectureDetail.segments.length}</span>
                  <span>Coordinates: ({mockLectureDetail.coordinates.x}, {mockLectureDetail.coordinates.y}, {mockLectureDetail.coordinates.z})</span>
                </div>
                <div className="space-y-2 pt-2">
                  <span className="text-xs font-semibold text-slate-300 uppercase tracking-wider">Detected Confusion Point</span>
                  {mockLectureDetail.confusion_points.map((cp) => (
                    <div key={cp.id} className="p-3 rounded-lg bg-rose-950/20 border border-rose-900/40 space-y-1">
                      <div className="flex justify-between text-xs">
                        <span className="font-semibold text-rose-300">{cp.misconception}</span>
                        <Badge variant="error" size="sm">Score: {cp.confusion_score}</Badge>
                      </div>
                      <p className="text-xs text-slate-300 italic">&ldquo;{cp.evidence_text}&rdquo;</p>
                      <div className="flex gap-2 text-[11px] text-slate-400 pt-1">
                        <span>WPM: {cp.signals.wpm}</span>
                        <span>Pause: {cp.signals.pause_density}</span>
                        <span>Disfluency: {cp.signals.disfluency_ratio}</span>
                      </div>
                    </div>
                  ))}
                </div>
              </Card>

              {/* Interventions */}
              <Card className="space-y-3">
                <span className="text-xs font-semibold text-slate-300 uppercase tracking-wider">Generated Interventions</span>
                <div className="space-y-3">
                  {mockLectureDetail.interventions.map((intv) => (
                    <div key={intv.id} className="p-3 rounded-lg bg-indigo-950/20 border border-indigo-900/40 space-y-1.5">
                      <div className="flex justify-between text-xs">
                        <span className="font-medium text-indigo-200">{intv.title}</span>
                        <Badge variant="indigo" size="sm">{intv.target_type.toUpperCase()}</Badge>
                      </div>
                      <div className="text-xs text-slate-300">
                        {'actionable_recap' in intv.content && Array.isArray(intv.content.actionable_recap) && (
                          <ul className="list-disc list-inside space-y-0.5 text-slate-400">
                            {intv.content.actionable_recap.map((step, idx) => (
                              <li key={idx}>{step}</li>
                            ))}
                          </ul>
                        )}
                        {'summary' in intv.content && (
                          <p className="text-slate-400">{intv.content.summary as string}</p>
                        )}
                      </div>
                    </div>
                  ))}
                </div>
              </Card>
            </div>
          </section>
        )}
      </main>
    </div>
  );
};

export default App;
