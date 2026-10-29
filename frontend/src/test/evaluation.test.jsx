import React from 'react';
import { describe, it, expect, vi, beforeEach } from 'vitest';
import { render, screen, waitFor } from '@testing-library/react';
import EvaluationPage from '../pages/EvaluationPage';
import * as api from '../services/api';

vi.mock('../services/api', () => ({
  getEvaluationFromBackend: vi.fn(),
  runBacktestInBackend: vi.fn(),
}));

describe('EvaluationPage - Active Dataset Integration', () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  const mockActiveDataset = {
    dataset_id: 'cddccc63-6774-4114-b5d5-b68b234d4284',
    filename: 'm5_canonical_sample.csv',
    profile: {
      filename: 'm5_canonical_sample.csv',
      rowsCount: 582,
      columnsCount: 9,
      uniqueSeriesCount: 3,
      dateRange: { start_date: '2015-10-14', end_date: '2016-04-24' },
    },
    mapping: {
      date: 'date',
      series_id: 'series_id',
      target: 'target',
    },
  };

  const mockEvalData = {
    dataset_id: 'cddccc63-6774-4114-b5d5-b68b234d4284',
    models_evaluated: ['arima', 'lightgbm'],
    horizons_evaluated: ['7D', '28D'],
    table_1_model_x_horizon_mape: {
      arima: { '7D': 28.5, '28D': 31.2, '90D': null },
      sarima: { '7D': null, '28D': null, '90D': null },
      prophet: { '7D': null, '28D': null, '90D': null },
      lightgbm: { '7D': 24.2, '28D': 27.8, '90D': null },
      deepar: { '7D': null, '28D': null, '90D': null },
      tft: { '7D': null, '28D': null, '90D': null },
    },
    table_2_model_x_horizon_rmse: {
      arima: { '7D': 3.1, '28D': 3.8, '90D': null },
      sarima: { '7D': null, '28D': null, '90D': null },
      prophet: { '7D': null, '28D': null, '90D': null },
      lightgbm: { '7D': 2.7, '28D': 3.2, '90D': null },
      deepar: { '7D': null, '28D': null, '90D': null },
      tft: { '7D': null, '28D': null, '90D': null },
    },
    best_per_horizon: {
      '7D': { best_model: 'lightgbm', mape: 24.2, rmse: 2.7, is_tie: false, tied_models: [] },
      '28D': { best_model: 'lightgbm', mape: 27.8, rmse: 3.2, is_tie: false, tied_models: [] },
      '90D': null,
    },
    best_model_overall: { model: 'lightgbm', overall_mape: 26.0, horizons_covered: 2 },
    table_3_series_evaluations: [
      {
        series_id: 'HOBBIES_1_001_CA_1', model: 'lightgbm',
        horizon: '7D', mape: 24.2, rmse: 2.7, folds_evaluated: 2, sample_count: 14,
      },
    ],
    series_details: [
      {
        dataset_id: 'cddccc63-6774-4114-b5d5-b68b234d4284',
        series_id: 'HOBBIES_1_001_CA_1',
        model: 'arima',
        horizon: 28,
        status: 'SUCCESS',
        fold_count: 2,
        mape: 31.2,
        rmse: 3.8,
        folds: [
          {
            fold: 1, train_start: '2015-10-14', train_end: '2016-03-11',
            forecast_start: '2016-03-12', forecast_end: '2016-04-08',
            train_count: 149, test_count: 28, status: 'SUCCESS', mape: 30.5, rmse: 3.7
          },
          {
            fold: 2, train_start: '2015-10-14', train_end: '2016-03-27',
            forecast_start: '2016-03-28', forecast_end: '2016-04-24',
            train_count: 165, test_count: 28, status: 'SUCCESS', mape: 32.1, rmse: 3.9
          },
        ]
      }
    ],
    execution_duration_ms: 1234.5,
  };

  it('renders "Run Dataset Backtest" prompt and no stale 1913 indices when no evalData cached', async () => {
    api.getEvaluationFromBackend.mockResolvedValue(null);
    render(<EvaluationPage uploadedDataset={mockActiveDataset} />);
    await waitFor(() => {
      expect(screen.getByRole('button', { name: /Run Dataset Backtest/i })).toBeInTheDocument();
    });
    expect(screen.queryByText(/1913/)).not.toBeInTheDocument();
    expect(screen.queryByText(/1773/)).not.toBeInTheDocument();
  });

  it('displays actual fold dates (2015-2016) not stale demo dates after backtest', async () => {
    api.getEvaluationFromBackend.mockResolvedValue(mockEvalData);
    render(<EvaluationPage uploadedDataset={mockActiveDataset} />);
    await waitFor(() => {
      expect(screen.getAllByText(/2016-03-12/).length).toBeGreaterThan(0);
    });
    expect(screen.getAllByText(/2016-04-24/).length).toBeGreaterThan(0);
    expect(screen.queryByText(/1774/)).not.toBeInTheDocument();
  });

  it('shows Not Evaluated for 90D horizon on 194-day dataset', async () => {
    api.getEvaluationFromBackend.mockResolvedValue(mockEvalData);
    render(<EvaluationPage uploadedDataset={mockActiveDataset} />);
    await waitFor(() => {
      expect(screen.getAllByText(/Not Evaluated/i).length).toBeGreaterThan(0);
    });
  });

  it('shows real MAPE from backtest results not hardcoded demo values', async () => {
    api.getEvaluationFromBackend.mockResolvedValue(mockEvalData);
    render(<EvaluationPage uploadedDataset={mockActiveDataset} />);
    await waitFor(() => {
      expect(screen.getAllByText(/24\.2%/).length).toBeGreaterThan(0);
    });
    // These are hardcoded demo values that should NOT appear
    expect(screen.queryByText(/9\.4%/)).not.toBeInTheDocument();
  });

  it('shows "Not evaluated yet" when backtest has not been run for active dataset', async () => {
    api.getEvaluationFromBackend.mockResolvedValue(null);
    render(<EvaluationPage uploadedDataset={mockActiveDataset} />);
    await waitFor(() => {
      expect(screen.getAllByText(/Not evaluated yet/i).length).toBeGreaterThan(0);
    });
  });
});
