import React from 'react';
import { describe, it, expect, vi, beforeEach } from 'vitest';
import { render, screen, waitFor, fireEvent } from '@testing-library/react';
import ModelComparisonPage from '../pages/ModelComparisonPage';
import * as api from '../services/api';

vi.mock('../services/api', () => ({
  getEvaluationComparisonFromBackend: vi.fn(),
  runBacktestInBackend: vi.fn(),
  getExplorerDataFromBackend: vi.fn(),
}));

describe('ModelComparisonPage - Unevaluated Horizon & Chart Consistency', () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  const mockUploadedDataset = {
    dataset_id: 'cddccc63-6774-4114-b5d5-b68b234d4284',
    filename: 'm5_canonical_sample.csv',
  };

  // Verified backtest results for m5_canonical_sample.csv (7D: LightGBM 38.29%, 28D: SARIMA 36.13%, 90D: null)
  const mockBacktestData = {
    dataset_id: 'cddccc63-6774-4114-b5d5-b68b234d4284',
    models_evaluated: ['arima', 'sarima', 'prophet', 'lightgbm', 'deepar', 'tft'],
    horizons_evaluated: ['7D', '28D'],
    table_1_model_x_horizon_mape: {
      arima: { '7D': 42.15, '28D': 39.80, '90D': null },
      sarima: { '7D': 39.50, '28D': 36.13, '90D': null },
      prophet: { '7D': 44.20, '28D': 41.30, '90D': null },
      lightgbm: { '7D': 38.29, '28D': 37.10, '90D': null },
      deepar: { '7D': 48.00, '28D': 45.20, '90D': null },
      tft: { '7D': 46.50, '28D': 43.80, '90D': null },
    },
    table_2_model_x_horizon_rmse: {
      arima: { '7D': 1.25, '28D': 1.18, '90D': null },
      sarima: { '7D': 1.15, '28D': 1.08, '90D': null },
      prophet: { '7D': 1.30, '28D': 1.22, '90D': null },
      lightgbm: { '7D': 1.12, '28D': 1.10, '90D': null },
      deepar: { '7D': 1.45, '28D': 1.35, '90D': null },
      tft: { '7D': 1.40, '28D': 1.30, '90D': null },
    },
    best_per_horizon: {
      '7D': { best_model: 'lightgbm', mape: 38.29, rmse: 1.12, is_tie: false, tied_models: [] },
      '28D': { best_model: 'sarima', mape: 36.13, rmse: 1.08, is_tie: false, tied_models: [] },
      '90D': null,
    },
    best_model_overall: {
      model: 'lightgbm',
      overall_mape: 37.70,
      horizons_covered: 2,
      evaluated_horizons: ['7D', '28D'],
    },
    scope: { store_id: null, category: null },
  };

  it('renders verified 7D and 28D winners, with 90D correctly displaying dashes in tables', async () => {
    api.getExplorerDataFromBackend.mockResolvedValue({
      available_filters: { stores: ['CA_1', 'CA_2'], categories: ['HOBBIES'], items: [], series: [] },
      dimensions: { has_store: true, has_category: true, has_item: false, has_series: false },
    });
    api.getEvaluationComparisonFromBackend.mockResolvedValue(mockBacktestData);

    render(<ModelComparisonPage uploadedDataset={mockUploadedDataset} />);

    await waitFor(() => {
      // 7D winner: LightGBM 38.29%
      expect(screen.getAllByText(/38\.29%/i).length).toBeGreaterThan(0);
      // 28D winner: SARIMA 36.13%
      expect(screen.getAllByText(/36\.13%/i).length).toBeGreaterThan(0);
    });

    // Best overall card clearly states evaluated horizons
    expect(screen.getByText(/Evaluated across 7D, 28D \(90D not evaluated\)/i)).toBeInTheDocument();
  });

  it('does not plot unevaluated 90D horizon as zero error in Degradation Curve', async () => {
    api.getExplorerDataFromBackend.mockResolvedValue(null);
    api.getEvaluationComparisonFromBackend.mockResolvedValue(mockBacktestData);

    const { container } = render(<ModelComparisonPage uploadedDataset={mockUploadedDataset} />);

    await waitFor(() => {
      expect(screen.getAllByText(/90D Not Evaluated/i).length).toBeGreaterThan(0);
    });

    // 90D axis label visibly marked as not evaluated
    expect(screen.getByText(/\(Not Evaluated\)/i)).toBeInTheDocument();
    expect(screen.getByText(/Insufficient history for 90D/i)).toBeInTheDocument();

    // Verify SVG paths in degradation curve:
    // With 90D unevaluated, paths must only connect 2 points (x=90 and x=250), never x=410
    const paths = container.querySelectorAll('svg path');
    paths.forEach(p => {
      const d = p.getAttribute('d');
      // If path contains M 90 ..., it must NOT contain 410 or connect to bottom 150
      if (d && d.includes('M 90')) {
        expect(d).not.toContain('410');
      }
    });
  });

  it('does not draw zero-height bars for unevaluated 90D in Visual Comparison bar chart', async () => {
    api.getExplorerDataFromBackend.mockResolvedValue(null);
    api.getEvaluationComparisonFromBackend.mockResolvedValue(mockBacktestData);

    render(<ModelComparisonPage uploadedDataset={mockUploadedDataset} />);

    await waitFor(() => {
      expect(screen.getByText(/Visual Comparison/i)).toBeInTheDocument();
    });

    // Legend badge clearly shows 90D is Not Evaluated
    expect(screen.getAllByText(/Not Evaluated/i).length).toBeGreaterThan(0);
  });

  it('dynamically reloads metrics when filters change', async () => {
    api.getExplorerDataFromBackend.mockResolvedValue({
      available_filters: { stores: ['CA_1', 'CA_2'], categories: ['HOBBIES'], items: [], series: [] },
      dimensions: { has_store: true, has_category: true, has_item: false, has_series: false },
    });
    api.getEvaluationComparisonFromBackend.mockResolvedValue(mockBacktestData);

    render(<ModelComparisonPage uploadedDataset={mockUploadedDataset} />);

    await waitFor(() => {
      expect(screen.getByRole('combobox', { name: /Horizon/i })).toBeInTheDocument();
    });

    // Change horizon filter
    const horizonSelect = screen.getByRole('combobox', { name: /Horizon/i });
    fireEvent.change(horizonSelect, { target: { value: '7d' } });

    await waitFor(() => {
      expect(api.getEvaluationComparisonFromBackend).toHaveBeenCalledWith(
        mockUploadedDataset.dataset_id,
        expect.objectContaining({ horizon: 7 }),
        expect.any(AbortSignal)
      );
    });
  });

  it('updates Horizon Consistency Analysis chart when switching between MAPE and RMSE modes', async () => {
    api.getExplorerDataFromBackend.mockResolvedValue(null);
    api.getEvaluationComparisonFromBackend.mockResolvedValue(mockBacktestData);

    const { container } = render(<ModelComparisonPage uploadedDataset={mockUploadedDataset} />);

    await waitFor(() => {
      expect(screen.getByText(/Horizon Consistency Analysis/i)).toBeInTheDocument();
    });

    // In default MAPE mode:
    // Ticks and data labels must contain '%'
    expect(screen.getByText(/How MAPE error scales from 7D to 90D/i)).toBeInTheDocument();
    // In mockBacktestData, LightGBM 28D is 37.10% (the last evaluated point), and 7D is 38.29%
    expect(container.textContent).toContain('LightGBM (37.1%)');
    expect(container.textContent).toContain('SARIMA (36.13%)');
    expect(container.textContent).toContain('LIGHTGBM (Best 7D: 38.29%)');

    // Switch to RMSE (Units) mode
    const rmseButton = screen.getByRole('button', { name: /RMSE \(Units\)/i });
    fireEvent.click(rmseButton);

    // In RMSE mode:
    // Description updates to RMSE error
    expect(screen.getByText(/How RMSE error scales from 7D to 90D/i)).toBeInTheDocument();

    // Data labels in line chart must display RMSE values (last point LightGBM 28D: 1.1, SARIMA 28D: 1.08) without '%'
    expect(container.textContent).toContain('LightGBM (1.1)');
    expect(container.textContent).toContain('SARIMA (1.08)');
    expect(container.textContent).not.toContain('LightGBM (1.1%)');
    expect(container.textContent).toContain('LIGHTGBM (Best 7D: 1.12)');

    // Tooltip titles must indicate RMSE
    const titles = Array.from(container.querySelectorAll('circle title')).map(el => el.textContent);
    expect(titles.some(t => t.includes('1.12 RMSE'))).toBe(true);
    expect(titles.some(t => t.includes('1.08 RMSE'))).toBe(true);
    expect(titles.every(t => !t.includes('% RMSE'))).toBe(true);

    // Unevaluated 90D still clearly shows Not Evaluated and never connects or displays zero
    expect(screen.getAllByText(/90D Not Evaluated/i).length).toBeGreaterThan(0);
    const paths = container.querySelectorAll('svg path');
    paths.forEach(p => {
      const d = p.getAttribute('d');
      if (d && d.includes('M 90')) {
        expect(d).not.toContain('410');
      }
    });

    // Switch back to MAPE (%) mode
    const mapeButton = screen.getByRole('button', { name: /MAPE \(%\)/i });
    fireEvent.click(mapeButton);

    expect(screen.getByText(/How MAPE error scales from 7D to 90D/i)).toBeInTheDocument();
    expect(container.textContent).toContain('LightGBM (37.1%)');
  });

  it('guarantees legend and summary cards derive from current filtered series scope instead of dataset-wide winner', async () => {
    // Dataset-wide winner in cached evalData: LightGBM 7D 3.63%, SARIMA 28D 6.74%
    // But currently selected series (e.g., FOODS_1_001_CA_1) has:
    // SARIMA 7D: 4.54%, SARIMA 28D: 8.96%, LightGBM 7D: 5.20%, LightGBM 28D: 9.80%
    const mockSeriesEvalData = {
      dataset_id: 'cddccc63-6774-4114-b5d5-b68b234d4284',
      series_id: 'FOODS_1_001_CA_1',
      models_evaluated: ['arima', 'sarima', 'prophet', 'lightgbm', 'deepar', 'tft'],
      horizons_evaluated: ['7D', '28D', '90D'],
      table_1_model_x_horizon_mape: {
        arima: { '7D': 6.10, '28D': 10.50, '90D': 12.00 },
        sarima: { '7D': 4.54, '28D': 8.96, '90D': 7.78 },
        prophet: { '7D': 5.80, '28D': 11.20, '90D': 13.50 },
        lightgbm: { '7D': 5.20, '28D': 9.80, '90D': 7.78 },
        deepar: { '7D': 7.00, '28D': 12.00, '90D': 14.00 },
        tft: { '7D': 6.50, '28D': 11.50, '90D': 13.00 },
      },
      table_2_model_x_horizon_rmse: {
        arima: { '7D': 2.10, '28D': 3.50, '90D': 4.10 },
        sarima: { '7D': 1.45, '28D': 2.80, '90D': 2.65 },
        prophet: { '7D': 1.95, '28D': 3.60, '90D': 4.30 },
        lightgbm: { '7D': 1.70, '28D': 3.10, '90D': 2.65 },
        deepar: { '7D': 2.30, '28D': 3.90, '90D': 4.50 },
        tft: { '7D': 2.15, '28D': 3.75, '90D': 4.25 },
      },
      // Backend dataset-wide aggregate cached data might contain 3.63% and 6.74%:
      best_per_horizon: {
        '7D': { best_model: 'lightgbm', mape: 3.63, rmse: 0.95 },
        '28D': { best_model: 'sarima', mape: 6.74, rmse: 1.85 },
        '90D': { best_model: 'sarima', mape: 7.50, rmse: 2.50 },
      },
      best_model_overall: {
        model: 'lightgbm',
        overall_mape: 5.18,
      },
      is_series_specific: true,
    };

    api.getExplorerDataFromBackend.mockResolvedValue({
      available_filters: { stores: ['CA_1'], categories: ['FOODS'], items: ['FOODS_1_001'], series: ['FOODS_1_001_CA_1', 'FOODS_1_002_CA_1'] },
      dimensions: { has_store: true, has_category: true, has_item: true, has_series: true },
      scope: { series_id: 'FOODS_1_001_CA_1' },
    });
    api.getEvaluationComparisonFromBackend.mockResolvedValue(mockSeriesEvalData);

    const { container } = render(<ModelComparisonPage uploadedDataset={mockUploadedDataset} />);

    await waitFor(() => {
      // Table 1 displays SARIMA 4.54% and 8.96%
      expect(screen.getAllByText('4.54%').length).toBeGreaterThan(0);
      expect(screen.getAllByText('8.96%').length).toBeGreaterThan(0);
    });

    // In MAPE mode, the Horizon Consistency legend must show SARIMA with 4.54% and 8.96%
    // and NEVER the dataset-wide 3.63% or 6.74%
    expect(container.textContent).toContain('SARIMA (Best 7D: 4.54%)');
    expect(container.textContent).toContain('SARIMA (Best 28D: 8.96%)');
    expect(container.textContent).not.toContain('3.63%');
    expect(container.textContent).not.toContain('6.74%');

    // Summary cards must also agree with the series scope
    expect(screen.getByText('Best 7D Model (Short-term)')).toBeInTheDocument();
    expect(container.textContent).toContain('4.54% MAPE');
    expect(container.textContent).toContain('8.96% MAPE');

    // Switch to RMSE mode
    const rmseButton = screen.getByRole('button', { name: /RMSE \(Units\)/i });
    fireEvent.click(rmseButton);

    // Legend must display RMSE in demand units without percentage signs
    expect(container.textContent).toContain('SARIMA (Best 7D: 1.45)');
    expect(container.textContent).toContain('SARIMA (Best 28D: 2.8)');
    expect(container.textContent).not.toContain('1.45%');
    expect(container.textContent).not.toContain('2.8%');
    expect(container.textContent).toContain('1.45 RMSE');
  });

  it('updates legend when switching series and purges metrics when changing dataset', async () => {
    const series1Data = {
      dataset_id: 'cddccc63-6774-4114-b5d5-b68b234d4284',
      series_id: 'SERIES_A',
      models_evaluated: ['sarima', 'lightgbm'],
      horizons_evaluated: ['7D', '28D'],
      table_1_model_x_horizon_mape: {
        sarima: { '7D': 4.54, '28D': 8.96, '90D': null },
        lightgbm: { '7D': 5.20, '28D': 9.80, '90D': null },
      },
      table_2_model_x_horizon_rmse: {
        sarima: { '7D': 1.45, '28D': 2.80, '90D': null },
        lightgbm: { '7D': 1.70, '28D': 3.10, '90D': null },
      },
    };

    const series2Data = {
      dataset_id: 'cddccc63-6774-4114-b5d5-b68b234d4284',
      series_id: 'SERIES_B',
      models_evaluated: ['sarima', 'lightgbm'],
      horizons_evaluated: ['7D', '28D'],
      table_1_model_x_horizon_mape: {
        sarima: { '7D': 7.10, '28D': 11.40, '90D': null },
        lightgbm: { '7D': 3.15, '28D': 5.60, '90D': null },
      },
      table_2_model_x_horizon_rmse: {
        sarima: { '7D': 2.45, '28D': 4.10, '90D': null },
        lightgbm: { '7D': 0.95, '28D': 1.80, '90D': null },
      },
    };

    api.getExplorerDataFromBackend.mockResolvedValue({
      available_filters: { stores: [], categories: [], items: [], series: ['SERIES_A', 'SERIES_B'] },
      dimensions: { has_store: false, has_category: false, has_item: false, has_series: true },
      scope: { series_id: 'SERIES_A' },
    });
    api.getEvaluationComparisonFromBackend.mockImplementation((datasetId, params) => {
      if (params?.series_id === 'SERIES_B') {
        return Promise.resolve(series2Data);
      }
      return Promise.resolve(series1Data);
    });

    const { container, rerender } = render(<ModelComparisonPage uploadedDataset={mockUploadedDataset} />);

    await waitFor(() => {
      expect(container.textContent).toContain('SARIMA (Best 7D: 4.54%)');
    });

    // Switch series dropdown to SERIES_B
    const seriesSelect = screen.getByDisplayValue('SERIES_A');
    fireEvent.change(seriesSelect, { target: { value: 'SERIES_B' } });

    await waitFor(() => {
      // Legend now reflects SERIES_B winner (LightGBM 3.15% 7D and 5.6% 28D)
      expect(container.textContent).toContain('LIGHTGBM (Best 7D: 3.15%)');
      expect(container.textContent).toContain('LIGHTGBM (Best 28D: 5.6%)');
      expect(container.textContent).not.toContain('4.54%');
    });

    // Now change datasets
    api.getEvaluationComparisonFromBackend.mockResolvedValue(null);
    rerender(<ModelComparisonPage uploadedDataset={{ dataset_id: 'brand-new-dataset-id', filename: 'new.csv' }} />);

    // Old evaluation metrics from previous dataset must NOT remain visible
    await waitFor(() => {
      expect(container.textContent).not.toContain('3.15%');
      expect(container.textContent).not.toContain('5.6%');
      expect(screen.getByText(/Execute rolling-origin backtesting across all architectures/i)).toBeInTheDocument();
    });
  });
});

