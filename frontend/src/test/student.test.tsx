import { describe, it, expect, vi, beforeEach } from 'vitest';
import { render, screen, fireEvent, waitFor } from '@testing-library/react';
import { StudentView } from '../views/StudentView';
import { lectureService } from '../services/lectureService';
import { Lecture, StudentCatchUp, TutorChatResponse } from '../types';

vi.mock('../services/lectureService', () => ({
  lectureService: {
    listLectures: vi.fn(),
    getStudentCatchUp: vi.fn(),
    generateStudentCatchUp: vi.fn(),
    sendTutorChatMessage: vi.fn(),
  },
}));

describe('Phase 7 Student Catch-Up & Socratic Tutor Tests', () => {
  const mockLectures: Lecture[] = [
    {
      id: 'lec-701',
      title: 'Neural Networks: Backpropagation Dynamics',
      source_type: 'upload',
      duration_seconds: 640.0,
      status: 'analyzed',
      coordinates: { x: 30.0, y: 88.0, z: 2.0 },
      created_at: '2026-10-16T12:00:00Z',
      updated_at: '2026-10-16T12:05:00Z',
    },
  ];

  const mockCatchups: StudentCatchUp[] = [
    {
      id: 'cu-701',
      lecture_id: 'lec-701',
      title: 'Demystifying Matrix Gradients: The Shape Matching Blueprint',
      summary: 'In backpropagation, gradients measure parameter sensitivities. The gradient of a scalar loss with respect to any matrix must preserve that matrix footprint.',
      concrete_analogy: 'Think of cookie cutters: the cutter must match the dough tray dimensions exactly.',
      key_takeaways: [
        'Scalar loss requires dL/dW to match W dimensions.',
        'Transposing matrices maintains valid dimension alignment.',
        'Track input and output box dimensions before taking derivatives.',
      ],
      coordinates: { x: 25.0, y: 92.0, z: 2.0 },
      quiz_questions: [
        {
          id: 'qq-701',
          catchup_id: 'cu-701',
          question: 'If weight matrix W has shape (M, N) and loss L is scalar, what is the shape of dL/dW?',
          options: [
            '(M, N), because each entry requires its own partial derivative',
            '(N, M), because gradients are always transposed',
            '(M, 1), because loss is a single value',
            '(1, N), representing row-wise sensitivities',
          ],
          correct_option_index: 0,
          hints: [
            { step: 1, hint: 'Consider what a gradient represents: one partial derivative for every element in W.' },
            { step: 2, hint: 'Since each element has a corresponding sensitivity, the shape must match W itself.' },
          ],
          explanation: 'The gradient dL/dW contains partial derivatives for every element, mirroring the shape of W.',
          coordinates: { x: 26.5, y: 92.0, z: 2.5 },
        },
      ],
    },
  ];

  beforeEach(() => {
    vi.clearAllMocks();
  });

  it('renders student catch-up guides with concrete analogy and interactive takeaway checklist', async () => {
    (lectureService.listLectures as any).mockResolvedValue(mockLectures);
    (lectureService.getStudentCatchUp as any).mockResolvedValue(mockCatchups);

    render(<StudentView />);

    await waitFor(() => {
      expect(screen.getByRole('heading', { level: 1, name: /Student Catch-Up & Socratic Tutor/i })).toBeInTheDocument();
      expect(screen.getByText('Demystifying Matrix Gradients: The Shape Matching Blueprint')).toBeInTheDocument();
    });

    // Check concrete analogy
    expect(screen.getByText(/Think of cookie cutters/i)).toBeInTheDocument();

    // Check takeaways checklist
    expect(screen.getByText(/Scalar loss requires dL\/dW to match W dimensions/i)).toBeInTheDocument();
    expect(screen.getByText(/Pedagogical 3D: \(25, 92, 2\)/i)).toBeInTheDocument();

    // Toggle takeaway checkbox
    const takeawayItem = screen.getByText(/Scalar loss requires dL\/dW to match W dimensions/i);
    fireEvent.click(takeawayItem);
    await waitFor(() => {
      expect(screen.getByText('1 / 3 mastered')).toBeInTheDocument();
    });
  });

  it('switches to quiz tab, reveals progressive hints, and validates student answer', async () => {
    (lectureService.listLectures as any).mockResolvedValue(mockLectures);
    (lectureService.getStudentCatchUp as any).mockResolvedValue(mockCatchups);

    render(<StudentView />);

    // Click Quiz tab
    const quizTab = await screen.findByTestId('tab-quiz');
    fireEvent.click(quizTab);

    // Question content visible
    await waitFor(() => {
      expect(screen.getByText(/If weight matrix W has shape \(M, N\) and loss L is scalar/i)).toBeInTheDocument();
    });

    // Reveal progressive hint
    const hintBtn = screen.getByTestId('reveal-hint-qq-701');
    expect(hintBtn).toHaveTextContent(/Reveal Hint 1 of 2/i);
    fireEvent.click(hintBtn);

    await waitFor(() => {
      expect(screen.getByText(/Hint 1:/i)).toBeInTheDocument();
      expect(screen.getByText(/Consider what a gradient represents/i)).toBeInTheDocument();
    });

    // Select the correct option
    const correctOpt = screen.getByTestId('quiz-opt-qq-701-0');
    fireEvent.click(correctOpt);

    await waitFor(() => {
      expect(screen.getByText(/Correct!/i)).toBeInTheDocument();
      expect(screen.getByText(/The gradient dL\/dW contains partial derivatives/i)).toBeInTheDocument();
    });
  });

  it('switches to Socratic tutor tab, engages in dialogue, and tests suggested follow-up clicks', async () => {
    (lectureService.listLectures as any).mockResolvedValue(mockLectures);
    (lectureService.getStudentCatchUp as any).mockResolvedValue(mockCatchups);

    const mockTutorReply: TutorChatResponse = {
      reply: 'Consider how backpropagation walks backwards through each operation. When you multiply two matrices, what constraint must their inner dimensions satisfy?',
      suggested_followups: [
        'Why do the inner dimensions have to match?',
        'Can you show me what happens with a 2x3 matrix?',
      ],
      grounded_timestamp: 155.0,
      coordinates: { x: 155.0, y: 50.0, z: 2.0 },
    };
    (lectureService.sendTutorChatMessage as any).mockResolvedValue(mockTutorReply);

    render(<StudentView />);

    // Click Socratic Tutor tab
    const tutorTab = await screen.findByTestId('tab-tutor');
    fireEvent.click(tutorTab);

    await waitFor(() => {
      expect(screen.getByText(/Socratic AI Dialogue/i)).toBeInTheDocument();
      expect(screen.getByText(/Greetings! I am your Socratic AI Teaching Assistant/i)).toBeInTheDocument();
    });

    // Type a question in the chat input
    const input = screen.getByTestId('tutor-chat-input');
    fireEvent.change(input, { target: { value: 'Why does the chain rule transpose matrices?' } });

    const sendBtn = screen.getByTestId('tutor-chat-send-btn');
    fireEvent.click(sendBtn);

    await waitFor(() => {
      expect(lectureService.sendTutorChatMessage).toHaveBeenCalledWith(
        'lec-701',
        'Why does the chain rule transpose matrices?',
        expect.any(Array),
        'cu-701'
      );
    });

    // Check tutor response in chat stream
    await waitFor(() => {
      expect(screen.getByText(/When you multiply two matrices, what constraint must their inner dimensions satisfy\?/i)).toBeInTheDocument();
      expect(screen.getByText(/Lecture moment: 2:35/i)).toBeInTheDocument();
      expect(screen.getByText('Why do the inner dimensions have to match?')).toBeInTheDocument();
    });

    // Click suggested follow-up chip
    const followUpBtn = screen.getByText('Why do the inner dimensions have to match?');
    fireEvent.click(followUpBtn);

    await waitFor(() => {
      expect(lectureService.sendTutorChatMessage).toHaveBeenCalledTimes(2);
    });
  });
});
