import React from 'react';
import { Settings, Key, Database, Cpu, ShieldCheck } from 'lucide-react';
import { Card, Badge, Alert } from '../components/ui';

export const SettingsView: React.FC = () => {
  return (
    <div className="space-y-6" data-testid="view-settings">
      <div className="flex flex-col md:flex-row md:items-center justify-between gap-4 pb-4 border-b border-slate-800">
        <div>
          <div className="flex items-center gap-2 mb-1">
            <span className="text-xs font-semibold tracking-wider text-indigo-400 uppercase">Configuration</span>
            <Badge variant="indigo" size="sm">System State</Badge>
          </div>
          <h1 className="text-2xl font-bold tracking-tight text-white flex items-center gap-2">
            <Settings className="w-6 h-6 text-indigo-400" />
            System & Provider Settings
          </h1>
          <p className="text-slate-400 text-sm mt-1">
            Inspect active LLM, ASR, and Embedding providers, API keys status, and ChromaDB vector persistence.
          </p>
        </div>
      </div>

      <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
        <Card className="space-y-3">
          <div className="flex items-center justify-between">
            <div className="flex items-center gap-2">
              <Cpu className="w-5 h-5 text-indigo-400" />
              <h3 className="font-semibold text-white">LLM Provider</h3>
            </div>
            <Badge variant="low" size="sm">Active: Gemini / Mistral</Badge>
          </div>
          <p className="text-xs text-slate-400 leading-relaxed">
            Configured with structured JSON mode and Pydantic validation. Supports retry once on schema mismatch.
          </p>
          <div className="text-xs font-mono text-slate-300 bg-slate-950 p-2.5 rounded-lg border border-slate-800">
            LLM_PROVIDER = auto (Gemini / Mistral / Sarvam)
          </div>
        </Card>

        <Card className="space-y-3">
          <div className="flex items-center justify-between">
            <div className="flex items-center gap-2">
              <Key className="w-5 h-5 text-indigo-400" />
              <h3 className="font-semibold text-white">ASR Transcription</h3>
            </div>
            <Badge variant="low" size="sm">Voxtral + Faster-Whisper</Badge>
          </div>
          <p className="text-xs text-slate-400 leading-relaxed">
            Mistral Voxtral / Gemini multimodal primary, faster-whisper local CPU/GPU fallback for zero external key dependency.
          </p>
          <div className="text-xs font-mono text-slate-300 bg-slate-950 p-2.5 rounded-lg border border-slate-800">
            ASR_PROVIDER = auto (faster-whisper ready)
          </div>
        </Card>

        <Card className="space-y-3">
          <div className="flex items-center justify-between">
            <div className="flex items-center gap-2">
              <Database className="w-5 h-5 text-indigo-400" />
              <h3 className="font-semibold text-white">Vector Knowledge Graph</h3>
            </div>
            <Badge variant="low" size="sm">ChromaDB Persistent</Badge>
          </div>
          <p className="text-xs text-slate-400 leading-relaxed">
            Persistent on-disk vector store storing concept graphs, prerequisites, and historical misconception vectors.
          </p>
          <div className="text-xs font-mono text-slate-300 bg-slate-950 p-2.5 rounded-lg border border-slate-800">
            VECTOR_DB = chromadb (./data/chroma)
          </div>
        </Card>

        <Card className="space-y-3">
          <div className="flex items-center justify-between">
            <div className="flex items-center gap-2">
              <ShieldCheck className="w-5 h-5 text-emerald-400" />
              <h3 className="font-semibold text-white">API Security</h3>
            </div>
            <Badge variant="low" size="sm">CORS & Envelopes</Badge>
          </div>
          <p className="text-xs text-slate-400 leading-relaxed">
            Enforced uniform JSON envelope with request IDs, ISO timestamps, and strict error structures.
          </p>
          <div className="text-xs font-mono text-slate-300 bg-slate-950 p-2.5 rounded-lg border border-slate-800">
            PREFIX = /api/v1 (CORS enabled)
          </div>
        </Card>
      </div>

      <Alert severity="low" title="Environment Ready">
        All environment variables loaded from .env. Zero secrets hardcoded into codebase.
      </Alert>
    </div>
  );
};
