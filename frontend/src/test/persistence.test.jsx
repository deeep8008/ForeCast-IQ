import React from 'react';
import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest';
import { render, screen, waitFor, fireEvent } from '@testing-library/react';
import App from '../App';
import * as api from '../services/api';

vi.mock('../services/api', () => ({
  restoreDatasetFromBackend: vi.fn(),
  getDatasetSummaryFromBackend: vi.fn(),
  getEvaluationComparisonFromBackend: vi.fn(),
  runBacktestInBackend: vi.fn(),
  getExplorerDataFromBackend: vi.fn(),
  generateForecastInBackend: vi.fn(),
  uploadDatasetToBackend: vi.fn(),
  remapDatasetInBackend: vi.fn(),
}));

describe('Route and Dataset Persistence Across Refresh / Restart', () => {
  beforeEach(() => {
    localStorage.clear();
    window.location.hash = '';
    vi.clearAllMocks();
  });

  afterEach(() => {
    localStorage.clear();
    window.location.hash = '';
  });

  const mockRestoredDataset = {
    dataset_id: 'ds-edge-03-test',
    filename: '03_edge_case_retail.csv',
    mapping: { date: 'date', series_id: 'series_id', target: 'target', optional: [] },
    profile: {
      filename: '03_edge_case_retail.csv',
      rowsCount: 625,
      columnsCount: 9,
      headers: ['date', 'series_id', 'target', 'store_id', 'item_id', 'category', 'price', 'promo', 'holiday'],
      dateCol: 'date',
      seriesCol: 'series_id',
      targetCol: 'target',
      detectedFrequency: 'Daily (D)',
      uniqueSeriesCount: 2,
      dateRange: { start: '2024-01-01', end: '2025-09-17', spanDays: 625 }
    },
    quality: {
      overallStatus: 'FORECAST READY',
      statusIssues: [],
      missingValuesCount: 0,
      missingPct: '0.00',
      duplicateRowsCount: 4,
      conflictingPairsCount: 0,
      invalidDatesCount: 0,
      invalidTargetCount: 0,
      negativeTargetCount: 0,
      featureWarnings: [],
      leakageWarnings: []
    },
    splits: {
      split_strategy: 'Chronological Rolling Horizon',
      train_row_count: 538,
      validation_row_count: 28,
      test_row_count: 55,
      train: { name: 'Training Split', start_date: '2024-01-01', end_date: '2025-06-23', rows_count: 538, series_count: 2 },
      val: { name: 'Validation Split', start_date: '2025-06-24', end_date: '2025-07-21', rows_count: 28, series_count: 2 },
      test: { name: 'Test Split', start_date: '2025-07-22', end_date: '2025-09-15', rows_count: 55, series_count: 2 }
    },
    cleaning: {
      raw_rows: 625,
      cleaned_rows: 621,
      exact_duplicates_removed: 4,
      conflicts_resolved: 0,
      aggregation_rule: 'SUM',
      zero_targets_preserved: 12,
      summary_notes: ['Exact duplicates purged', 'Target values validated']
    },
    readiness: {
      checklist: [{ title: 'Temporal Continuity', detail: 'Cadence regular', passed: true }],
      horizons: { h7: { days: 7, label: '7-Day Tactical', status: 'Supported', note: 'Ready' } },
      models: [{ model: 'ARIMA', type: 'Statistical', ready: true, requirement: 'Sufficient observations' }]
    }
  };

  it('restores route from window.location.hash on page load', async () => {
    window.location.hash = '#/comparison';
    render(<App />);

    await waitFor(() => {
      const headings = screen.getAllByRole('heading', { name: /Model Comparison/i });
      expect(headings.length).toBeGreaterThan(0);
    }, { timeout: 8000 });
  });

  it('restores route from localStorage when hash is absent', async () => {
    window.location.hash = '';
    localStorage.setItem('forecastiq_active_tab', 'evaluation');
    render(<App />);

    await waitFor(() => {
      const evalHeadings = screen.getAllByText(/Evaluation/i);
      expect(evalHeadings.length).toBeGreaterThan(0);
    });
  });

  it('restores custom dataset and updates Sidebar active dataset card on page refresh', async () => {
    localStorage.setItem('forecastiq_active_dataset_id', 'ds-edge-03-test');
    api.restoreDatasetFromBackend.mockResolvedValueOnce(mockRestoredDataset);

    render(<App />);

    // Shows loading state initially
    expect(screen.getByTestId('restoring-dataset-spinner')).toBeInTheDocument();

    // After restoration completes
    await waitFor(() => {
      expect(screen.queryByTestId('restoring-dataset-spinner')).not.toBeInTheDocument();
      // Sidebar should display restored dataset name
      expect(screen.getByText('03_edge_case_retail.csv')).toBeInTheDocument();
      expect(screen.getByText(/625 observation rows/i)).toBeInTheDocument();
    });

    expect(api.restoreDatasetFromBackend).toHaveBeenCalledWith('ds-edge-03-test');
  });

  it('displays recovery banner and gives retry / reset options when backend restoration fails', async () => {
    localStorage.setItem('forecastiq_active_dataset_id', 'ds-deleted-or-missing');
    api.restoreDatasetFromBackend.mockRejectedValueOnce(
      new Error("Dataset 'ds-deleted-or-missing' not found on server.")
    );

    render(<App />);

    await waitFor(() => {
      expect(screen.getByTestId('dataset-restoration-error-banner')).toBeInTheDocument();
      expect(screen.getByText(/Dataset 'ds-deleted-or-missing' not found on server/i)).toBeInTheDocument();
    });

    // Reset to benchmark button clears the error and removes custom dataset
    const resetBtn = screen.getByTestId('reset-to-benchmark-btn');
    fireEvent.click(resetBtn);

    await waitFor(() => {
      expect(screen.queryByTestId('dataset-restoration-error-banner')).not.toBeInTheDocument();
      expect(screen.getByText(/M5 Forecasting Accuracy/i)).toBeInTheDocument();
    });
  });

  it('restores upload dataset analysis results when refreshing while on upload page', async () => {
    window.location.hash = '#/upload';
    localStorage.setItem('forecastiq_active_tab', 'upload');
    localStorage.setItem('forecastiq_active_dataset_id', 'ds-edge-03-test');
    api.restoreDatasetFromBackend.mockResolvedValueOnce(mockRestoredDataset);

    render(<App />);

    await waitFor(() => {
      expect(screen.queryByTestId('restoring-dataset-spinner')).not.toBeInTheDocument();
      // Should render the analysis view and NOT the empty drop zone
      expect(screen.getByTestId('analysis-results')).toBeInTheDocument();
      expect(screen.getByTestId('dataset-profile-section')).toBeInTheDocument();
      expect(screen.getByTestId('profile-rows-count')).toHaveTextContent('625');
    });
  });
});

