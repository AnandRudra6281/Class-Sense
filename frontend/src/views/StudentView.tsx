import React, { useState } from 'react';
import { GraduationCap, Lightbulb, HelpCircle, Check } from 'lucide-react';
import { Card, Badge } from '../components/ui';
import { StudentCatchUp, Coordinates3D } from '../types';

export const StudentView: React.FC = () => {
  const [selectedOption, setSelectedOption] = useState<number | null>(null);

  const dummyCatchUp: StudentCatchUp = {
    id: 'catchup-1',
    lecture_id: 'lec-1',
    title: 'Demystifying Backpropagation: The Assembly Line Analogy',
    summary: 'Think of a neural network as an assembly line producing toy cars. If a car comes out with crooked wheels, backpropagation tells each worker backwards along the line exactly how much their tool contributed to the error.',
    concrete_analogy: 'Factory quality inspector tracing faults upstream to the root supplier.',
    key_takeaways: [
      'Gradients measure sensitivity: how much output moves when a parameter is nudged.',
      'The Chain Rule lets us multiply sensitivities backwards layer by layer.',
      'Weights are updated opposite the gradient direction to minimize loss.',
    ],
    coordinates: { x: 42.0, y: 70.0, z: 1.5 } as Coordinates3D,
  };

  const sampleQuestion = {
    question: 'Why do we multiply by the negative gradient when updating weights during gradient descent?',
    options: [
      'To increase the learning rate dynamically over time.',
      'Because the gradient points in the direction of steepest increase, so negative points to steepest decrease.',
      'To invert the matrix dimensions to match the layer inputs.',
      'Because backpropagation requires negative real numbers only.',
    ],
    correctIndex: 1,
  };

  return (
    <div className="space-y-6" data-testid="view-student">
      <div className="flex flex-col md:flex-row md:items-center justify-between gap-4 pb-4 border-b border-slate-800">
        <div>
          <div className="flex items-center gap-2 mb-1">
            <span className="text-xs font-semibold tracking-wider text-indigo-400 uppercase">Personalized Catch-Up</span>
            <Badge variant="indigo" size="sm">Socratic Tutor</Badge>
          </div>
          <h1 className="text-2xl font-bold tracking-tight text-white flex items-center gap-2">
            <GraduationCap className="w-6 h-6 text-indigo-400" />
            Student Catch-Up & Practice
          </h1>
          <p className="text-slate-400 text-sm mt-1">
            Intuitive analogies, plain-English summaries, and Socratic self-check questions for struggling concepts.
          </p>
        </div>
      </div>

      <Card variant="glow" className="space-y-4">
        <div className="flex items-center justify-between">
          <Badge variant="medium" size="sm">Targeted Module</Badge>
          <Badge variant="default" size="sm">
            Coord: ({dummyCatchUp.coordinates.x}, {dummyCatchUp.coordinates.y}, {dummyCatchUp.coordinates.z})
          </Badge>
        </div>

        <h3 className="text-lg font-bold text-white">{dummyCatchUp.title}</h3>
        <p className="text-slate-300 text-sm leading-relaxed">{dummyCatchUp.summary}</p>

        <div className="p-3.5 bg-indigo-950/40 border border-indigo-800/60 rounded-xl space-y-1">
          <span className="text-xs font-semibold text-indigo-300 flex items-center gap-1.5">
            <Lightbulb className="w-4 h-4 text-amber-400" /> Concrete Analogy
          </span>
          <p className="text-xs text-slate-200">{dummyCatchUp.concrete_analogy}</p>
        </div>

        <div className="space-y-2">
          <h5 className="text-xs font-semibold text-slate-300 uppercase tracking-wider">Key Takeaways</h5>
          <ul className="space-y-1.5 text-xs text-slate-300">
            {dummyCatchUp.key_takeaways.map((point, i) => (
              <li key={i} className="flex items-start gap-2">
                <Check className="w-4 h-4 text-emerald-400 shrink-0 mt-0.5" />
                <span>{point}</span>
              </li>
            ))}
          </ul>
        </div>
      </Card>

      <Card className="space-y-4">
        <div className="flex items-center gap-2">
          <HelpCircle className="w-5 h-5 text-indigo-400" />
          <h4 className="text-base font-semibold text-white">Socratic Diagnostic Check</h4>
        </div>

        <p className="text-sm text-slate-200">{sampleQuestion.question}</p>

        <div className="space-y-2">
          {sampleQuestion.options.map((opt, idx) => {
            const isSelected = selectedOption === idx;
            const isCorrect = idx === sampleQuestion.correctIndex;
            return (
              <button
                key={idx}
                onClick={() => setSelectedOption(idx)}
                className={`w-full text-left p-3 rounded-xl border text-xs font-medium transition-all ${
                  isSelected
                    ? isCorrect
                      ? 'bg-emerald-950/50 border-emerald-500 text-emerald-200'
                      : 'bg-rose-950/50 border-rose-500 text-rose-200'
                    : 'bg-slate-900 border-slate-800 text-slate-300 hover:border-slate-700'
                }`}
              >
                <div className="flex items-center justify-between">
                  <span>{opt}</span>
                  {isSelected && (
                    <Badge variant={isCorrect ? 'low' : 'critical'} size="sm">
                      {isCorrect ? 'Correct!' : 'Try Again'}
                    </Badge>
                  )}
                </div>
              </button>
            );
          })}
        </div>
      </Card>
    </div>
  );
};
