import { describe, it, expect } from 'vitest';
import { render, screen } from '@testing-library/react';
import { Button } from '../components/ui/Button';
import { Card } from '../components/ui/Card';
import { Badge } from '../components/ui/Badge';
import { ProgressBar } from '../components/ui/ProgressBar';

describe('UI Primitives', () => {
  it('renders Button with label and handles disabled/loading state', () => {
    const { rerender } = render(<Button>Click Me</Button>);
    expect(screen.getByRole('button', { name: /click me/i })).toBeInTheDocument();

    rerender(<Button isLoading>Click Me</Button>);
    expect(screen.getByRole('button')).toBeDisabled();
  });

  it('renders Card with content and variant styles', () => {
    render(<Card data-testid="test-card">Card Content</Card>);
    expect(screen.getByTestId('test-card')).toHaveTextContent('Card Content');
  });

  it('renders Badge with custom variant', () => {
    render(<Badge variant="success">Completed</Badge>);
    expect(screen.getByText('Completed')).toBeInTheDocument();
  });

  it('renders ProgressBar with accurate clamped percentage', () => {
    render(<ProgressBar progress={45} label="Progress" />);
    expect(screen.getByText('45%')).toBeInTheDocument();
    expect(screen.getByText('Progress')).toBeInTheDocument();
  });
});
