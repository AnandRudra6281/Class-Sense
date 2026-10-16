import { describe, it, expect } from 'vitest';
import { render, screen, fireEvent, waitFor } from '@testing-library/react';
import App from '../App';

describe('App Navigation and Layout Smoke Tests', () => {
  it('renders App with Dashboard as default view', () => {
    render(<App />);
    expect(screen.getByTestId('view-dashboard')).toBeInTheDocument();
    expect(screen.getByText('Instructor Cockpit')).toBeInTheDocument();
  });

  it('navigates to different views when clicking sidebar navigation links', async () => {
    render(<App />);

    // Click Lecture Library
    const libraryButtons = screen.getAllByRole('button', { name: /lecture library/i });
    fireEvent.click(libraryButtons[0]);
    await waitFor(() => expect(screen.getByTestId('view-library')).toBeInTheDocument());

    // Click Ingest Lecture
    const uploadButtons = screen.getAllByRole('button', { name: /ingest lecture/i });
    fireEvent.click(uploadButtons[0]);
    expect(screen.getByTestId('view-upload')).toBeInTheDocument();

    // Click System Settings
    const settingsButtons = screen.getAllByRole('button', { name: /system settings/i });
    fireEvent.click(settingsButtons[0]);
    expect(screen.getByTestId('view-settings')).toBeInTheDocument();
  });

  it('toggles demo mode button in header', () => {
    render(<App />);
    const demoBtn = screen.getByRole('button', { name: /demo: off/i });
    expect(demoBtn).toBeInTheDocument();

    fireEvent.click(demoBtn);
    expect(screen.getByRole('button', { name: /demo: on/i })).toBeInTheDocument();
  });
});
