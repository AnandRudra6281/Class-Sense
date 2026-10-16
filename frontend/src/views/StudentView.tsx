import React, { useState, useEffect, useCallback } from 'react';
import {
  GraduationCap,
  Lightbulb,
  HelpCircle,
  Check,
  Sparkles,
  RefreshCw,
  Send,
  MessageSquare,
  BookOpen,
  CheckCircle2,
  Compass,
  ArrowRight,
  Clock,
} from 'lucide-react';
import { Card, Badge, Button, Progress, Alert } from '../components/ui';
import { lectureService } from '../services/lectureService';
import { useJobPolling } from '../hooks/useJobPolling';
import {
  Lecture,
  StudentCatchUp,
  QuizQuestion,
  TutorChatMessage,
  TutorChatResponse,
} from '../types';

export const StudentView: React.FC = () => {
  const [lectures, setLectures] = useState<Lecture[]>([]);
  const [selectedLectureId, setSelectedLectureId] = useState<string>('');
  const [loadingLectures, setLoadingLectures] = useState<boolean>(true);
  const [catchups, setCatchups] = useState<StudentCatchUp[]>([]);
  const [loadingCatchups, setLoadingCatchups] = useState<boolean>(false);
  const [activeTab, setActiveTab] = useState<'catchup' | 'quiz' | 'tutor'>('catchup');
  const [error, setError] = useState<string | null>(null);

  // Catch-Up Checkbox progress state
  const [checkedTakeaways, setCheckedTakeaways] = useState<Record<string, boolean>>({});

  // Quiz interactive state
  const [quizAnswers, setQuizAnswers] = useState<Record<string, number>>({});
  const [unlockedHints, setUnlockedHints] = useState<Record<string, number>>({});

  // Socratic Tutor chat state
  const [chatMessages, setChatMessages] = useState<
    Array<{
      id: string;
      role: 'user' | 'assistant';
      content: string;
      timestamp?: number | null;
      followups?: string[];
    }>
  >([
    {
      id: 'welcome-1',
      role: 'assistant',
      content:
        'Greetings! I am your Socratic AI Teaching Assistant. I am here to guide your inquiry through this lecture. Instead of giving you rote answers, I will ask calibrated questions to help you uncover the underlying mechanics yourself. What concept or formula would you like to explore?',
      followups: [
        'Can you walk me through the main concept with a simple analogy?',
        'What were the most common mistakes students made in this lecture?',
        'How does this topic connect to the prerequisite foundations?',
      ],
    },
  ]);
  const [inputMessage, setInputMessage] = useState<string>('');
  const [isSending, setIsSending] = useState<boolean>(false);

  // Background Job Polling
  const [activeJobId, setActiveJobId] = useState<string | null>(null);

  const { status: jobStatus, progress: jobProgress } = useJobPolling(activeJobId, {
    onSuccess: () => {
      if (selectedLectureId) {
        fetchCatchUpData(selectedLectureId);
      }
    },
    onError: (err: Error) => {
      setError(`Catch-up generation failed: ${err.message}`);
    },
  });

  const fetchLectures = async () => {
    try {
      setLoadingLectures(true);
      setError(null);
      const data = await lectureService.listLectures();
      setLectures(data);
      if (data.length > 0 && !selectedLectureId) {
        setSelectedLectureId(data[0].id);
      }
    } catch (err: unknown) {
      setError(err instanceof Error ? err.message : 'Failed to load lectures.');
    } finally {
      setLoadingLectures(false);
    }
  };

  const fetchCatchUpData = useCallback(async (lectureId: string) => {
    try {
      setLoadingCatchups(true);
      setError(null);
      const data = await lectureService.getStudentCatchUp(lectureId);
      setCatchups(data);
    } catch (err: unknown) {
      setError(err instanceof Error ? err.message : 'Failed to load catch-up packages.');
    } finally {
      setLoadingCatchups(false);
    }
  }, []);

  useEffect(() => {
    fetchLectures();
  }, []);

  useEffect(() => {
    if (selectedLectureId) {
      fetchCatchUpData(selectedLectureId);
    }
  }, [selectedLectureId, fetchCatchUpData]);

  const handleGenerateCatchUp = async () => {
    if (!selectedLectureId) return;
    try {
      setError(null);
      const res = await lectureService.generateStudentCatchUp(selectedLectureId);
      setActiveJobId(res.job_id);
    } catch (err: unknown) {
      setError(err instanceof Error ? err.message : 'Failed to launch catch-up generation.');
    }
  };

  const handleToggleTakeaway = (key: string) => {
    setCheckedTakeaways((prev) => ({ ...prev, [key]: !prev[key] }));
  };

  const handleSelectQuizOption = (questionId: string, optionIdx: number) => {
    setQuizAnswers((prev) => ({ ...prev, [questionId]: optionIdx }));
  };

  const handleRevealNextHint = (questionId: string, totalHints: number) => {
    setUnlockedHints((prev) => {
      const current = prev[questionId] || 0;
      if (current < totalHints) {
        return { ...prev, [questionId]: current + 1 };
      }
      return prev;
    });
  };

  const handleSendChatMessage = async (messageText: string) => {
    if (!messageText.trim() || !selectedLectureId || isSending) return;

    const userMsg = {
      id: `usr-${Date.now()}`,
      role: 'user' as const,
      content: messageText.trim(),
    };

    setChatMessages((prev) => [...prev, userMsg]);
    setInputMessage('');
    setIsSending(true);
    setError(null);

    try {
      const historyPayload: TutorChatMessage[] = chatMessages.map((m) => ({
        role: m.role,
        content: m.content,
      }));

      const activeModule = catchups.length > 0 ? catchups[0].id : undefined;
      const response: TutorChatResponse = await lectureService.sendTutorChatMessage(
        selectedLectureId,
        userMsg.content,
        historyPayload,
        activeModule
      );

      const assistantMsg = {
        id: `asst-${Date.now()}`,
        role: 'assistant' as const,
        content: response.reply,
        timestamp: response.grounded_timestamp,
        followups: response.suggested_followups,
      };

      setChatMessages((prev) => [...prev, assistantMsg]);
    } catch (err: unknown) {
      setError(err instanceof Error ? err.message : 'Failed to reach Socratic tutor.');
    } finally {
      setIsSending(false);
    }
  };

  // Collect all questions for quiz tab
  const allQuizQuestions: Array<{ moduleTitle: string; question: QuizQuestion }> = [];
  catchups.forEach((cu) => {
    if (cu.quiz_questions) {
      cu.quiz_questions.forEach((q) => {
        allQuizQuestions.push({ moduleTitle: cu.title, question: q });
      });
    }
  });

  const isJobRunning = jobStatus === 'running' || jobStatus === 'queued';

  return (
    <div className="space-y-6" data-testid="view-student">
      {/* Top Header & Lecture Selector */}
      <div className="flex flex-col md:flex-row md:items-center justify-between gap-4 pb-4 border-b border-slate-800">
        <div>
          <div className="flex items-center gap-2 mb-1">
            <span className="text-xs font-semibold tracking-wider text-indigo-400 uppercase">Student Learning Portal</span>
            <Badge variant="indigo" size="sm">Socratic AI Engine</Badge>
          </div>
          <h1 className="text-2xl font-bold tracking-tight text-white flex items-center gap-2">
            <GraduationCap className="w-6 h-6 text-indigo-400" />
            Student Catch-Up & Socratic Tutor
          </h1>
          <p className="text-slate-400 text-sm mt-1">
            Plain-English conceptual bridges, intuitive real-world analogies, diagnostic checkpoint quizzes, and conversational Socratic inquiry.
          </p>
        </div>

        <div className="flex flex-wrap items-center gap-3">
          <select
            value={selectedLectureId}
            onChange={(e) => setSelectedLectureId(e.target.value)}
            disabled={loadingLectures || isJobRunning}
            className="bg-slate-900 border border-slate-700 text-slate-200 text-xs rounded-xl px-3 py-2 focus:ring-2 focus:ring-indigo-500 focus:outline-none"
            data-testid="student-lecture-select"
          >
            {loadingLectures ? (
              <option>Loading lectures...</option>
            ) : lectures.length === 0 ? (
              <option>No lectures available</option>
            ) : (
              lectures.map((lec) => (
                <option key={lec.id} value={lec.id}>
                  {lec.title} ({Math.round(lec.duration_seconds)}s)
                </option>
              ))
            )}
          </select>

          <Button
            variant="primary"
            size="sm"
            onClick={handleGenerateCatchUp}
            disabled={!selectedLectureId || isJobRunning}
            data-testid="generate-catchup-btn"
          >
            <Sparkles className="w-4 h-4 mr-1.5" />
            Synthesize Catch-Up
          </Button>

          <Button
            variant="secondary"
            size="sm"
            onClick={() => selectedLectureId && fetchCatchUpData(selectedLectureId)}
            disabled={loadingCatchups}
            title="Refresh"
          >
            <RefreshCw className={`w-4 h-4 ${loadingCatchups ? 'animate-spin' : ''}`} />
          </Button>
        </div>
      </div>

      {/* Error alert */}
      {error && (
        <Alert severity="critical" title="Error">
          {error}
        </Alert>
      )}

      {/* Asynchronous Job Progress */}
      {isJobRunning && (
        <Card variant="default" className="border-indigo-500/40 bg-indigo-950/20 space-y-2">
          <div className="flex items-center justify-between text-xs font-semibold text-indigo-300">
            <span className="flex items-center gap-2">
              <Sparkles className="w-4 h-4 text-indigo-400 animate-pulse" />
              Synthesizing Student Catch-Up Materials (Structured JSON LLM Mode)...
            </span>
            <span>{jobProgress}%</span>
          </div>
          <Progress value={jobProgress} />
          <p className="text-[11px] text-slate-400">
            Translating cognitive confusion points into plain analogies and multi-step hint quizzes.
          </p>
        </Card>
      )}

      {/* Navigation Tabs */}
      <div className="flex items-center gap-2 border-b border-slate-800 pb-2">
        <button
          onClick={() => setActiveTab('catchup')}
          className={`flex items-center gap-2 px-4 py-2 rounded-xl text-xs font-semibold transition-all ${
            activeTab === 'catchup'
              ? 'bg-indigo-600/20 text-indigo-300 border border-indigo-500/40'
              : 'text-slate-400 hover:text-slate-200 hover:bg-slate-900 border border-transparent'
          }`}
          data-testid="tab-catchup"
        >
          <BookOpen className="w-4 h-4" />
          Catch-Up Guides
          {catchups.length > 0 && (
            <Badge variant="indigo" size="sm">
              {catchups.length}
            </Badge>
          )}
        </button>

        <button
          onClick={() => setActiveTab('quiz')}
          className={`flex items-center gap-2 px-4 py-2 rounded-xl text-xs font-semibold transition-all ${
            activeTab === 'quiz'
              ? 'bg-indigo-600/20 text-indigo-300 border border-indigo-500/40'
              : 'text-slate-400 hover:text-slate-200 hover:bg-slate-900 border border-transparent'
          }`}
          data-testid="tab-quiz"
        >
          <HelpCircle className="w-4 h-4" />
          Socratic Practice Quiz
          {allQuizQuestions.length > 0 && (
            <Badge variant="medium" size="sm">
              {allQuizQuestions.length}
            </Badge>
          )}
        </button>

        <button
          onClick={() => setActiveTab('tutor')}
          className={`flex items-center gap-2 px-4 py-2 rounded-xl text-xs font-semibold transition-all ${
            activeTab === 'tutor'
              ? 'bg-indigo-600/20 text-indigo-300 border border-indigo-500/40'
              : 'text-slate-400 hover:text-slate-200 hover:bg-slate-900 border border-transparent'
          }`}
          data-testid="tab-tutor"
        >
          <MessageSquare className="w-4 h-4" />
          Socratic AI Tutor
          <Badge variant="low" size="sm">
            Live
          </Badge>
        </button>
      </div>

      {/* TAB 1: CATCH-UP GUIDES */}
      {activeTab === 'catchup' && (
        <div className="space-y-6">
          {catchups.length === 0 ? (
            <Card variant="default" className="text-center py-12 space-y-3">
              <BookOpen className="w-10 h-10 text-slate-500 mx-auto" />
              <h3 className="text-base font-bold text-white">No Catch-Up Modules Generated Yet</h3>
              <p className="text-xs text-slate-400 max-w-md mx-auto">
                Trigger synthesis above to transform diagnosed lecture misconceptions into plain-English conceptual guides, real-world analogies, and core takeaway checklists.
              </p>
              <Button
                variant="primary"
                size="sm"
                onClick={handleGenerateCatchUp}
                disabled={!selectedLectureId || isJobRunning}
              >
                <Sparkles className="w-4 h-4 mr-1.5" />
                Synthesize Now
              </Button>
            </Card>
          ) : (
            catchups.map((cu, idx) => (
              <Card key={cu.id} variant="glow" className="space-y-4">
                <div className="flex flex-wrap items-center justify-between gap-2 border-b border-slate-800/80 pb-3">
                  <div className="flex items-center gap-2">
                    <Badge variant="indigo" size="sm">Module #{idx + 1}</Badge>
                    <span className="text-xs text-slate-400">Targeted Remediation</span>
                  </div>
                  <Badge variant="default" size="sm" className="font-mono text-[10px]">
                    Pedagogical 3D: ({cu.coordinates.x}, {cu.coordinates.y}, {cu.coordinates.z})
                  </Badge>
                </div>

                <div>
                  <h3 className="text-lg font-bold text-white mb-2">{cu.title}</h3>
                  <p className="text-sm text-slate-300 leading-relaxed">{cu.summary}</p>
                </div>

                {/* Concrete Analogy Box */}
                <div className="p-4 bg-gradient-to-r from-amber-950/30 to-indigo-950/30 border border-amber-800/40 rounded-xl space-y-1.5">
                  <span className="text-xs font-semibold text-amber-300 flex items-center gap-1.5 uppercase tracking-wide">
                    <Lightbulb className="w-4 h-4 text-amber-400" /> Concrete Real-World Analogy
                  </span>
                  <p className="text-xs text-slate-200 leading-relaxed">{cu.concrete_analogy}</p>
                </div>

                {/* Key Takeaways Interactive Checklist */}
                <div className="space-y-2 pt-2">
                  <div className="flex items-center justify-between">
                    <h5 className="text-xs font-semibold text-slate-300 uppercase tracking-wider flex items-center gap-1.5">
                      <CheckCircle2 className="w-4 h-4 text-indigo-400" /> Core Takeaways Checklist
                    </h5>
                    <span className="text-[11px] text-slate-400">
                      {cu.key_takeaways.filter((_, i) => checkedTakeaways[`${cu.id}-${i}`]).length} / {cu.key_takeaways.length} mastered
                    </span>
                  </div>
                  <div className="space-y-2">
                    {cu.key_takeaways.map((point, i) => {
                      const itemKey = `${cu.id}-${i}`;
                      const isChecked = !!checkedTakeaways[itemKey];
                      return (
                        <div
                          key={i}
                          onClick={() => handleToggleTakeaway(itemKey)}
                          className={`flex items-start gap-3 p-2.5 rounded-xl border text-xs cursor-pointer transition-all ${
                            isChecked
                              ? 'bg-emerald-950/20 border-emerald-800/60 text-slate-200'
                              : 'bg-slate-900/60 border-slate-800 text-slate-300 hover:border-slate-700'
                          }`}
                        >
                          <div
                            className={`w-4 h-4 rounded mt-0.5 flex items-center justify-center shrink-0 transition-all ${
                              isChecked ? 'bg-emerald-500 text-slate-950' : 'border border-slate-600 bg-slate-800'
                            }`}
                          >
                            {isChecked && <Check className="w-3 h-3 stroke-[3]" />}
                          </div>
                          <span className={isChecked ? 'line-through text-slate-400' : ''}>{point}</span>
                        </div>
                      );
                    })}
                  </div>
                </div>
              </Card>
            ))
          )}
        </div>
      )}

      {/* TAB 2: SOCRATIC PRACTICE QUIZ */}
      {activeTab === 'quiz' && (
        <div className="space-y-6">
          {allQuizQuestions.length === 0 ? (
            <Card variant="default" className="text-center py-12 space-y-3">
              <HelpCircle className="w-10 h-10 text-slate-500 mx-auto" />
              <h3 className="text-base font-bold text-white">No Practice Questions Available</h3>
              <p className="text-xs text-slate-400 max-w-md mx-auto">
                Generate student catch-up materials to produce diagnostic multiple-choice checkpoints equipped with progressive Socratic hints.
              </p>
            </Card>
          ) : (
            allQuizQuestions.map(({ moduleTitle, question: q }, qIndex) => {
              const selectedIdx = quizAnswers[q.id];
              const isAnswered = selectedIdx !== undefined;
              const isCorrect = isAnswered && selectedIdx === q.correct_option_index;
              const hintsCount = q.hints ? q.hints.length : 0;
              const revealedCount = unlockedHints[q.id] || 0;

              return (
                <Card key={q.id} variant="default" className="space-y-4">
                  <div className="flex flex-wrap items-center justify-between gap-2 border-b border-slate-800 pb-3">
                    <div className="flex items-center gap-2">
                      <Badge variant="medium" size="sm">Question #{qIndex + 1}</Badge>
                      <span className="text-xs text-slate-400">{moduleTitle}</span>
                    </div>
                    <Badge variant="default" size="sm" className="font-mono text-[10px]">
                      Coord: ({q.coordinates.x}, {q.coordinates.y}, {q.coordinates.z})
                    </Badge>
                  </div>

                  <p className="text-sm font-semibold text-slate-100">{q.question}</p>

                  {/* Options */}
                  <div className="space-y-2">
                    {q.options.map((opt, optIdx) => {
                      const isOptionSelected = selectedIdx === optIdx;
                      let optionClasses = 'bg-slate-900 border-slate-800 text-slate-300 hover:border-slate-700';

                      if (isAnswered) {
                        if (optIdx === q.correct_option_index) {
                          optionClasses = 'bg-emerald-950/40 border-emerald-500 text-emerald-200';
                        } else if (isOptionSelected) {
                          optionClasses = 'bg-rose-950/40 border-rose-500 text-rose-200';
                        } else {
                          optionClasses = 'bg-slate-900/40 border-slate-800/40 text-slate-500';
                        }
                      }

                      return (
                        <button
                          key={optIdx}
                          onClick={() => handleSelectQuizOption(q.id, optIdx)}
                          className={`w-full text-left p-3 rounded-xl border text-xs font-medium transition-all ${optionClasses}`}
                          data-testid={`quiz-opt-${q.id}-${optIdx}`}
                        >
                          <div className="flex items-center justify-between">
                            <span className="flex items-center gap-2">
                              <span className="w-5 h-5 rounded-full bg-slate-800 border border-slate-700 flex items-center justify-center text-[10px] text-slate-300 font-mono">
                                {String.fromCharCode(65 + optIdx)}
                              </span>
                              <span>{opt}</span>
                            </span>

                            {isOptionSelected && (
                              <Badge variant={isCorrect ? 'low' : 'critical'} size="sm">
                                {isCorrect ? 'Correct!' : 'Incorrect'}
                              </Badge>
                            )}
                          </div>
                        </button>
                      );
                    })}
                  </div>

                  {/* Progressive Hints Section */}
                  {hintsCount > 0 && (
                    <div className="pt-2 border-t border-slate-800 space-y-2">
                      <div className="flex items-center justify-between">
                        <span className="text-xs font-semibold text-indigo-300 flex items-center gap-1.5">
                          <Compass className="w-4 h-4 text-indigo-400" /> Socratic Progressive Hints
                        </span>
                        {revealedCount < hintsCount && (
                          <Button
                            variant="secondary"
                            size="sm"
                            onClick={() => handleRevealNextHint(q.id, hintsCount)}
                            className="text-[11px] h-7 px-2.5"
                            data-testid={`reveal-hint-${q.id}`}
                          >
                            <Lightbulb className="w-3.5 h-3.5 mr-1 text-amber-400" />
                            Reveal Hint {revealedCount + 1} of {hintsCount}
                          </Button>
                        )}
                      </div>

                      {revealedCount > 0 && (
                        <div className="space-y-1.5">
                          {q.hints.slice(0, revealedCount).map((hintObj, hIdx) => (
                            <div
                              key={hIdx}
                              className="p-2.5 bg-indigo-950/30 border border-indigo-800/40 rounded-xl text-xs text-indigo-200"
                            >
                              <span className="font-semibold text-indigo-400 mr-1.5">Hint {hintObj.step}:</span>
                              {hintObj.hint}
                            </div>
                          ))}
                        </div>
                      )}
                    </div>
                  )}

                  {/* Explanation reveal on answer */}
                  {isAnswered && (
                    <div
                      className={`p-3.5 rounded-xl border text-xs leading-relaxed ${
                        isCorrect
                          ? 'bg-emerald-950/20 border-emerald-800/50 text-emerald-300'
                          : 'bg-rose-950/20 border-rose-800/50 text-rose-300'
                      }`}
                    >
                      <span className="font-bold uppercase tracking-wider block mb-1">
                        {isCorrect ? 'Why this is correct:' : 'Misconception Breakdown:'}
                      </span>
                      {q.explanation}
                    </div>
                  )}
                </Card>
              );
            })
          )}
        </div>
      )}

      {/* TAB 3: SOCRATIC AI TUTOR */}
      {activeTab === 'tutor' && (
        <Card variant="glow" className="space-y-4">
          <div className="flex items-center justify-between pb-3 border-b border-slate-800">
            <div className="flex items-center gap-2">
              <div className="w-8 h-8 rounded-xl bg-indigo-600/30 border border-indigo-500/50 flex items-center justify-center text-indigo-300">
                <GraduationCap className="w-5 h-5" />
              </div>
              <div>
                <h3 className="text-sm font-bold text-white">Socratic AI Dialogue</h3>
                <p className="text-[11px] text-slate-400">
                  Grounded in lecture transcript segments and diagnosed cognitive struggle points.
                </p>
              </div>
            </div>
            <Badge variant="indigo" size="sm">Guided Inquiry Mode</Badge>
          </div>

          {/* Chat Messages Stream */}
          <div className="space-y-3 max-h-[460px] overflow-y-auto pr-2" data-testid="tutor-chat-stream">
            {chatMessages.map((msg) => {
              const isUser = msg.role === 'user';
              return (
                <div key={msg.id} className={`flex ${isUser ? 'justify-end' : 'justify-start'}`}>
                  <div
                    className={`max-w-[85%] rounded-2xl p-4 text-xs space-y-2 ${
                      isUser
                        ? 'bg-indigo-600 text-white rounded-tr-none'
                        : 'bg-slate-900 border border-slate-800 text-slate-200 rounded-tl-none'
                    }`}
                  >
                    <div className="flex items-center justify-between gap-3 text-[10px] text-slate-400">
                      <span className="font-semibold text-indigo-300">{isUser ? 'You' : 'Socratic Tutor'}</span>
                      {msg.timestamp !== undefined && msg.timestamp !== null && (
                        <span className="flex items-center gap-1 text-indigo-300 bg-indigo-950/60 px-2 py-0.5 rounded border border-indigo-800/40">
                          <Clock className="w-3 h-3" />
                          Lecture moment: {Math.floor(msg.timestamp / 60)}:{Math.floor(msg.timestamp % 60).toString().padStart(2, '0')}
                        </span>
                      )}
                    </div>

                    <p className="leading-relaxed whitespace-pre-wrap">{msg.content}</p>

                    {/* Proactive suggested follow-up chips */}
                    {!isUser && msg.followups && msg.followups.length > 0 && (
                      <div className="pt-2 border-t border-slate-800/80 space-y-1.5">
                        <span className="text-[10px] uppercase tracking-wider text-slate-400 block">Suggested Inquiries:</span>
                        <div className="flex flex-wrap gap-1.5">
                          {msg.followups.map((suggestion, sIdx) => (
                            <button
                              key={sIdx}
                              onClick={() => handleSendChatMessage(suggestion)}
                              disabled={isSending}
                              className="text-[11px] text-left bg-slate-800/80 hover:bg-indigo-950 hover:text-indigo-300 border border-slate-700/80 hover:border-indigo-600/50 rounded-lg px-2.5 py-1 text-slate-300 transition-all flex items-center gap-1"
                              data-testid={`suggested-followup-${sIdx}`}
                            >
                              <ArrowRight className="w-3 h-3 shrink-0 text-indigo-400" />
                              <span>{suggestion}</span>
                            </button>
                          ))}
                        </div>
                      </div>
                    )}
                  </div>
                </div>
              );
            })}

            {isSending && (
              <div className="flex justify-start">
                <div className="bg-slate-900 border border-slate-800 rounded-2xl rounded-tl-none p-3.5 text-xs text-indigo-300 flex items-center gap-2 animate-pulse">
                  <Sparkles className="w-4 h-4 animate-spin" />
                  Formulating Socratic inquiry...
                </div>
              </div>
            )}
          </div>

          {/* Inline Chat Error Banner */}
          {error && (
            <div className="p-3 bg-rose-950/40 border border-rose-800/60 rounded-xl text-rose-300 text-xs flex items-center justify-between">
              <span>{error}</span>
              <button type="button" onClick={() => setError(null)} className="text-rose-400 hover:text-rose-200 text-xs font-semibold ml-2">
                Dismiss
              </button>
            </div>
          )}

          {/* Chat Input Bar */}
          <form
            onSubmit={(e) => {
              e.preventDefault();
              handleSendChatMessage(inputMessage);
            }}
            className="flex items-center gap-2 pt-2 border-t border-slate-800"
          >
            <input
              type="text"
              value={inputMessage}
              onChange={(e) => setInputMessage(e.target.value)}
              placeholder="Ask a question about the lecture or test your mental model..."
              disabled={isSending || !selectedLectureId}
              className="flex-1 bg-slate-900 border border-slate-800 rounded-xl px-4 py-2.5 text-xs text-white placeholder-slate-500 focus:outline-none focus:ring-2 focus:ring-indigo-500"
              data-testid="tutor-chat-input"
            />
            <Button
              type="submit"
              variant="primary"
              size="sm"
              disabled={!inputMessage.trim() || isSending || !selectedLectureId}
              data-testid="tutor-chat-send-btn"
            >
              <Send className="w-4 h-4" />
            </Button>
          </form>
        </Card>
      )}
    </div>
  );
};
