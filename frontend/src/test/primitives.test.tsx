import { describe, it, expect } from 'vitest';
import { render, screen } from '@testing-library/react';
import { Button, Card, Badge, Progress, Alert } from '../components/ui';
import { SeverityLevel } from '../types';

describe('UI Primitives & Severity Palette', () => {
  it('renders Button with variants and loading state', () => {
    const { rerender } = render(<Button variant="primary">Submit</Button>);
    expect(screen.getByRole('button', { name: /submit/i })).toBeInTheDocument();

    rerender(<Button isLoading>Submit</Button>);
    expect(screen.getByRole('button')).toBeDisabled();
  });

  it('renders Card with standard and glow variants', () => {
    render(<Card variant="glow" data-testid="card-element">Glow Content</Card>);
    expect(screen.getByTestId('card-element')).toHaveTextContent('Glow Content');
  });

  it('renders Badge across all severity palette levels', () => {
    const severities: SeverityLevel[] = ['low', 'medium', 'high', 'critical'];
    const { rerender } = render(<div>Container</div>);

    severities.forEach((sev) => {
      rerender(<Badge variant={sev} data-testid={`badge-${sev}`}>{sev.toUpperCase()}</Badge>);
      const badge = screen.getByTestId(`badge-${sev}`);
      expect(badge).toBeInTheDocument();
      expect(badge).toHaveTextContent(sev.toUpperCase());
    });
  });

  it('renders Progress with clamped percentage and severity', () => {
    render(<Progress value={75} max={100} label="Ingestion Progress" severity="high" />);
    expect(screen.getByText('75%')).toBeInTheDocument();
    expect(screen.getByText('Ingestion Progress')).toBeInTheDocument();
  });

  it('renders Alert across all severity palette levels', () => {
    const severities: SeverityLevel[] = ['low', 'medium', 'high', 'critical'];
    const { rerender } = render(<div>Alert Container</div>);

    severities.forEach((sev) => {
      rerender(
        <Alert severity={sev} title={`${sev} alert title`}>
          Detailed warning message for {sev}
        </Alert>
      );
      expect(screen.getByText(`${sev} alert title`)).toBeInTheDocument();
      expect(screen.getByText(`Detailed warning message for ${sev}`)).toBeInTheDocument();
    });
  });
});
