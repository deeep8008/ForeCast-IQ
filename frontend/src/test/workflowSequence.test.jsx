import React from 'react';
import { describe, it, expect } from 'vitest';
import { render, screen, fireEvent, waitFor } from '@testing-library/react';
import App from '../App';

describe('Workflow Navigation & Page Sequencing (Phases 3 & 4)', () => {
  it('renders Sidebar with approved 4-step sequence badges', () => {
    render(<App />);

    // Step 1: Upload Dataset
    const step1Badge = screen.getByText('Step 1');
    expect(step1Badge).toBeInTheDocument();

    // Step 2: Evaluation & Backtesting
    const step2Badge = screen.getByText('Step 2');
    expect(step2Badge).toBeInTheDocument();

    // Step 3: Generate Forecast
    const step3Badge = screen.getByText('Step 3');
    expect(step3Badge).toBeInTheDocument();

    // Step 4: Model Comparison
    const step4Badge = screen.getByText('Step 4');
    expect(step4Badge).toBeInTheDocument();
  });

  it('allows non-linear navigation via sidebar without rigid wizard lock', async () => {
    render(<App />);

    // Click directly on Model Comparison in sidebar
    const comparisonButtons = screen.getAllByRole('button', { name: /Model Comparison/i });
    fireEvent.click(comparisonButtons[0]);

    await waitFor(() => {
      expect(window.location.hash).toContain('comparison');
    });

    // Click directly on Generate Forecast in sidebar
    const forecastButtons = screen.getAllByRole('button', { name: /Generate Forecast/i });
    fireEvent.click(forecastButtons[0]);

    await waitFor(() => {
      expect(window.location.hash).toContain('forecast');
    });

    // Click directly on Evaluation & Backtesting in sidebar
    const evalButtons = screen.getAllByRole('button', { name: /Evaluation & Backtesting/i });
    fireEvent.click(evalButtons[0]);

    await waitFor(() => {
      expect(window.location.hash).toContain('evaluation');
    });
  });

  it('provides step-through continuation buttons between workflow pages', async () => {
    render(<App />);

    // In Evaluation page, check continuation button to Step 3
    const evalButtons = screen.getAllByRole('button', { name: /Evaluation & Backtesting/i });
    fireEvent.click(evalButtons[0]);

    await waitFor(() => {
      expect(window.location.hash).toContain('evaluation');
    });

    const evalNextBtn = screen.getByTestId('continue-to-forecast-step-btn');
    expect(evalNextBtn).toBeInTheDocument();

    // Clicking next button in Evaluation advances to forecast
    fireEvent.click(evalNextBtn);
    await waitFor(() => {
      expect(window.location.hash).toContain('forecast');
    });
  });
});
