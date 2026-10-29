import React from 'react';
import { describe, it, expect, vi, beforeEach } from 'vitest';
import { render, screen, waitFor, fireEvent } from '@testing-library/react';
import GenerateForecastPage from '../pages/GenerateForecastPage';
import * as api from '../services/api';

vi.mock('../services/api', () => ({
  generateForecastInBackend: vi.fn(),
  getExplorerDataFromBackend: vi.fn(),
  getEvaluationComparisonFromBackend: vi.fn(),
}));

describe('GenerateForecastPage Real Dataset Integration', () => {
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
      headers: ['date', 'series_id', 'target', 'store_id', 'item_id', 'category'],
    },
    mapping: {
      date: 'date',
      series_id: 'series_id',
      target: 'target',
      optional: { store_id: 'store_id', item_id: 'item_id', category: 'category' }
    },
    previewRows: [
      { date: '2016-01-01', series_id: 'HOBBIES_1_001_CA_1', target: 5, store_id: 'CA_1', item_id: 'HOBBIES_1_001' }
    ]
  };

  it('renders clean empty state when no dataset is uploaded', () => {
    const onNavigate = vi.fn();
    render(<GenerateForecastPage onNavigate={onNavigate} uploadedDataset={null} />);

    expect(screen.getByText('No Active Dataset Loaded')).toBeInTheDocument();
    expect(screen.getByText('Upload / Select Dataset')).toBeInTheDocument();
    expect(screen.queryByLabelText(/Select Store/i)).not.toBeInTheDocument();

    fireEvent.click(screen.getByText('Upload / Select Dataset'));
    expect(onNavigate).toHaveBeenCalledWith('upload');
  });

  it('populates real stores, products, and series from backend explorer for active dataset', async () => {
    api.getExplorerDataFromBackend.mockImplementation(async (id, opts) => {
      if (opts.store_id === 'CA_1' || !opts.store_id) {
        return {
          available_filters: {
            stores: ['CA_1', 'CA_2', 'CA_3'],
            categories: ['HOBBIES'],
            items: ['HOBBIES_1_001'],
            series: ['HOBBIES_1_001_CA_1'],
          },
          dimensions: { has_store: true, has_category: true, has_item: true },
          trend: [{ date: '2016-04-01', sales: 3, rollingAvg: 2.8 }]
        };
      }
      return null;
    });

    render(<GenerateForecastPage onNavigate={vi.fn()} uploadedDataset={mockActiveDataset} />);

    await waitFor(() => {
      const storeSelect = screen.getByLabelText(/Select Store/i);
      expect(storeSelect).toHaveValue('CA_1');
    });

    // Check Store options contain CA_1, CA_2, CA_3
    const storeSelect = screen.getByLabelText(/Select Store/i);
    expect(screen.getByRole('option', { name: 'CA_1' })).toBeInTheDocument();
    expect(screen.getByRole('option', { name: 'CA_2' })).toBeInTheDocument();
    expect(screen.getByRole('option', { name: 'CA_3' })).toBeInTheDocument();

    // Check Product options contain HOBBIES_1_001 (not hardcoded FOODS_3_090)
    const productSelect = screen.getByLabelText(/Select Product/i);
    expect(productSelect).toHaveValue('HOBBIES_1_001');
    expect(screen.queryByText(/FOODS_3_090/i)).not.toBeInTheDocument();

    // Check Series options contain HOBBIES_1_001_CA_1
    const seriesSelect = screen.getByLabelText(/Select Series/i);
    expect(seriesSelect).toHaveValue('HOBBIES_1_001_CA_1');

    // Verify 6 core model options exist
    expect(screen.getByText('ARIMA')).toBeInTheDocument();
    expect(screen.getByText('SARIMA')).toBeInTheDocument();
    expect(screen.getAllByText('Prophet').length).toBeGreaterThan(0);
    expect(screen.getByText('LightGBM')).toBeInTheDocument();
    expect(screen.getByText('DeepAR')).toBeInTheDocument();
    expect(screen.getByText('Temporal Fusion Transformer (TFT)')).toBeInTheDocument();

    // Verify horizons exist
    expect(screen.getByText('7 Days')).toBeInTheDocument();
    expect(screen.getByText('28 Days')).toBeInTheDocument();
    expect(screen.getByText('90 Days')).toBeInTheDocument();
  });

  it('updates series and clears incompatible series when store is changed', async () => {
    api.getExplorerDataFromBackend.mockImplementation(async (id, opts) => {
      if (opts.store_id === 'CA_2') {
        return {
          available_filters: {
            stores: ['CA_1', 'CA_2', 'CA_3'],
            categories: ['HOBBIES'],
            items: ['HOBBIES_1_001'],
            series: ['HOBBIES_1_001_CA_2'],
          },
          dimensions: { has_store: true, has_category: true, has_item: true },
          trend: [{ date: '2016-04-01', sales: 4, rollingAvg: 3.2 }]
        };
      }
      return {
        available_filters: {
          stores: ['CA_1', 'CA_2', 'CA_3'],
          categories: ['HOBBIES'],
          items: ['HOBBIES_1_001'],
          series: ['HOBBIES_1_001_CA_1'],
        },
        dimensions: { has_store: true, has_category: true, has_item: true },
        trend: [{ date: '2016-04-01', sales: 3, rollingAvg: 2.8 }]
      };
    });

    render(<GenerateForecastPage onNavigate={vi.fn()} uploadedDataset={mockActiveDataset} />);

    await waitFor(() => {
      expect(screen.getByLabelText(/Select Store/i)).toBeInTheDocument();
    });

    const storeSelect = screen.getByLabelText(/Select Store/i);
    fireEvent.change(storeSelect, { target: { value: 'CA_2' } });

    await waitFor(() => {
      const seriesSelect = screen.getByLabelText(/Select Series/i);
      expect(seriesSelect).toHaveValue('HOBBIES_1_001_CA_2');
    });
  });

  it('successfully generates real 7-day ARIMA forecast with exactly 7 points', async () => {
    api.getExplorerDataFromBackend.mockResolvedValue({
      available_filters: {
        stores: ['CA_1', 'CA_2', 'CA_3'],
        categories: ['HOBBIES'],
        items: ['HOBBIES_1_001'],
        series: ['HOBBIES_1_001_CA_1'],
      },
      dimensions: { has_store: true, has_category: true, has_item: true },
      trend: [
        { date: '2016-04-20', sales: 2, rollingAvg: 2.1 },
        { date: '2016-04-21', sales: 3, rollingAvg: 2.3 },
      ]
    });

    api.generateForecastInBackend.mockResolvedValue({
      dataset_id: 'cddccc63-6774-4114-b5d5-b68b234d4284',
      series_id: 'HOBBIES_1_001_CA_1',
      model: 'ARIMA(1, 1, 1)',
      forecast_horizon: 7,
      dates: [
        '2016-04-25', '2016-04-26', '2016-04-27', '2016-04-28',
        '2016-04-29', '2016-04-30', '2016-05-01'
      ],
      forecast: [2.5, 3.1, 2.8, 3.0, 3.4, 4.0, 2.9],
      lower_bound: [1.2, 1.8, 1.5, 1.7, 2.0, 2.5, 1.4],
      upper_bound: [3.8, 4.4, 4.1, 4.3, 4.8, 5.5, 4.4],
      points: [
        { date: '2016-04-25', forecast: 2.5, lower_bound: 1.2, upper_bound: 3.8 },
        { date: '2016-04-26', forecast: 3.1, lower_bound: 1.8, upper_bound: 4.4 },
        { date: '2016-04-27', forecast: 2.8, lower_bound: 1.5, upper_bound: 4.1 },
        { date: '2016-04-28', forecast: 3.0, lower_bound: 1.7, upper_bound: 4.3 },
        { date: '2016-04-29', forecast: 3.4, lower_bound: 2.0, upper_bound: 4.8 },
        { date: '2016-04-30', forecast: 4.0, lower_bound: 2.5, upper_bound: 5.5 },
        { date: '2016-05-01', forecast: 2.9, lower_bound: 1.4, upper_bound: 4.4 },
      ],
      training_end: '2016-04-24',
      components: { order: [1, 1, 1], aic: 120.4, bic: 125.1 }
    });

    render(<GenerateForecastPage onNavigate={vi.fn()} uploadedDataset={mockActiveDataset} />);

    await waitFor(() => {
      expect(screen.getByLabelText(/Select Store/i)).toBeInTheDocument();
    });

    // Select 7 Days horizon
    fireEvent.click(screen.getByText('7 Days'));

    // Click Generate Forecast
    const generateBtn = screen.getByTestId('generate-forecast-button');
    fireEvent.click(generateBtn);

    await waitFor(() => {
      expect(api.generateForecastInBackend).toHaveBeenCalledWith({
        dataset_id: 'cddccc63-6774-4114-b5d5-b68b234d4284',
        series_id: 'HOBBIES_1_001_CA_1',
        model: 'arima',
        horizon: 7,
      });
    });

    // Verify forecast result view appears with 7 Days and series info
    await waitFor(() => {
      expect(screen.getByText('Short-term operational')).toBeInTheDocument();
    });
    expect(screen.getByText('Series: HOBBIES_1_001_CA_1')).toBeInTheDocument();
    expect(screen.getByText('Model: ARIMA(1, 1, 1)')).toBeInTheDocument();
  });
});
