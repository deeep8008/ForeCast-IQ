import React from 'react';
import { describe, it, expect, vi } from 'vitest';
import { render, screen, fireEvent, waitFor } from '@testing-library/react';
import App from '../App';
import UploadDatasetPage from '../pages/UploadDatasetPage';
import { parseCSV, analyzeDataset, detectColumnMappings, DEMO_DATASETS } from '../utils/datasetAnalyzer';

// Mock the backend API service for frontend unit/integration testing
vi.mock('../services/api', () => ({
  uploadDatasetToBackend: vi.fn(async (fileOrBlob, filename) => {
    let text = '';
    if (fileOrBlob && typeof fileOrBlob.text === 'function') {
      text = await fileOrBlob.text();
    } else {
      text = DEMO_DATASETS.universalRetail.csv;
    }
    const parsed = parseCSV(text);
    const initialMap = detectColumnMappings(parsed.headers);
    const analysis = analyzeDataset(filename || 'dataset.csv', parsed, initialMap);
    return {
      dataset_id: 'mock-dataset-uuid-1234',
      ...analysis
    };
  }),
  remapDatasetInBackend: vi.fn(async (datasetId, mapping) => {
    const parsed = parseCSV(DEMO_DATASETS.universalRetail.csv);
    const analysis = analyzeDataset('dataset.csv', parsed, mapping);
    return {
      dataset_id: datasetId,
      ...analysis
    };
  })
}));

describe('Universal Dataset Upload & Analysis Engine', () => {
  it('parses compliant CSV and detects mandatory date, series_id, and target columns', () => {
    const rawCSV = `date,series_id,target,store_id,price
2024-01-01,STORE_1_ITEM_A,50,STORE_1,2.99
2024-01-02,STORE_1_ITEM_A,55,STORE_1,2.99`;

    const parsed = parseCSV(rawCSV);
    expect(parsed.headers).toEqual(['date', 'series_id', 'target', 'store_id', 'price']);
    expect(parsed.rows.length).toBe(2);

    const mapping = detectColumnMappings(parsed.headers);
    expect(mapping.date).toBe('date');
    expect(mapping.series_id).toBe('series_id');
    expect(mapping.target).toBe('target');

    const analysis = analyzeDataset('test.csv', parsed, mapping);
    expect(analysis.quality.overallStatus).toBe('FORECAST READY');
    expect(analysis.profile.rowsCount).toBe(2);
    expect(analysis.profile.uniqueSeriesCount).toBe(1);
  });

  it('validates required fields and reports NEEDS ATTENTION if mandatory columns are missing', () => {
    const missingTargetCSV = `date,series_id,store_id
2024-01-01,SERIES_1,STORE_1`;

    const parsed = parseCSV(missingTargetCSV);
    const mapping = detectColumnMappings(parsed.headers);
    expect(mapping.target).toBe(''); // Target missing!

    const analysis = analyzeDataset('missing_target.csv', parsed, mapping);
    expect(analysis.quality.overallStatus).toBe('NEEDS ATTENTION');
    expect(analysis.quality.statusIssues.some(msg => msg.includes('target'))).toBe(true);
    expect(analysis.readiness.checklist[0].passed).toBe(false);
  });

  it('handles invalid CSV state with unparseable dates and invalid target numbers', () => {
    const invalidCSV = `date,series_id,target
NOT_A_DATE,SERIES_1,100
2024-01-02,SERIES_1,NOT_A_NUMBER
2024-01-03,SERIES_1,-15`;

    const parsed = parseCSV(invalidCSV);
    const mapping = detectColumnMappings(parsed.headers);
    const analysis = analyzeDataset('invalid.csv', parsed, mapping);

    expect(analysis.quality.invalidDatesCount).toBe(1);
    expect(analysis.quality.invalidTargetCount).toBe(1);
    expect(analysis.quality.negativeTargetCount).toBe(1);
    expect(analysis.quality.overallStatus).toBe('NEEDS ATTENTION');
  });

  it('supports CSV with only date and target without requiring series_id', () => {
    const univariateCSV = `date,target
2024-01-01,100
2024-01-02,120
2024-01-03,115`;
    const parsed = parseCSV(univariateCSV);
    const mapping = detectColumnMappings(parsed.headers);
    expect(mapping.date).toBe('date');
    expect(mapping.target).toBe('target');
    expect(mapping.series_id).toBe('');

    // analyzeDataset allows single-series without series_id
    const analysis = analyzeDataset('univariate.csv', parsed, mapping);
    expect(analysis.profile.rowsCount).toBe(3);
  });
});

describe('UploadDatasetPage UI Component', () => {
  it('renders Upload page with drop zone and universal schema notice', () => {
    render(<UploadDatasetPage onNavigate={vi.fn()} />);

    expect(screen.getByTestId('upload-dataset-page')).toBeInTheDocument();
    expect(screen.getByRole('heading', { level: 1, name: /Upload Dataset/i })).toBeInTheDocument();
    expect(screen.getByTestId('drop-zone')).toBeInTheDocument();
    expect(screen.getByText(/Universal Schema Specification/i)).toBeInTheDocument();
    expect(screen.getByTestId('load-demo-retail')).toBeInTheDocument();
  });

  it('navigates to Upload Dataset page via Sidebar navigation', async () => {
    render(<App />);

    const uploadNavBtn = screen.getByRole('button', { name: /Upload Dataset/i });
    expect(uploadNavBtn).toBeInTheDocument();

    fireEvent.click(uploadNavBtn);

    await waitFor(() => {
      expect(screen.getByTestId('upload-dataset-page')).toBeInTheDocument();
      expect(screen.getByRole('heading', { level: 1, name: /Upload Dataset/i })).toBeInTheDocument();
    });
  });

  it('loads demo retail dataset and displays Dataset Profile, Column Mapping, and Data Quality UI', async () => {
    const onDatasetReady = vi.fn();
    render(<UploadDatasetPage onNavigate={vi.fn()} onDatasetReady={onDatasetReady} />);

    const demoRetailBtn = screen.getByTestId('load-demo-retail');
    fireEvent.click(demoRetailBtn);

    // Expect analysis results to appear
    await waitFor(() => {
      expect(screen.getByTestId('analysis-results')).toBeInTheDocument();
    }, { timeout: 3000 });

    // Verify Dataset Profile UI
    expect(screen.getByTestId('dataset-profile-section')).toBeInTheDocument();
    expect(screen.getByTestId('dataset-status-badge')).toHaveTextContent(/FORECAST READY/i);
    expect(screen.getByTestId('profile-rows-count')).toHaveTextContent(/41/i);
    expect(screen.getByTestId('profile-series-count')).toHaveTextContent(/2/i);

    // Verify Column Mapping UI
    expect(screen.getByTestId('column-mapping-section')).toBeInTheDocument();
    expect(screen.getByTestId('map-date-select')).toHaveValue('date');
    expect(screen.getByTestId('map-series-select')).toHaveValue('series_id');
    expect(screen.getByTestId('map-target-select')).toHaveValue('target');

    // Verify Data Quality UI
    expect(screen.getByTestId('data-quality-section')).toBeInTheDocument();

    // Verify Forecast Readiness & Data Preview
    expect(screen.getByTestId('forecast-readiness-section')).toBeInTheDocument();
    expect(screen.getByTestId('data-preview-section')).toBeInTheDocument();

    // Verify callback
    expect(onDatasetReady).toHaveBeenCalled();
  });

  it('allows user to modify column mapping interactively', async () => {
    render(<UploadDatasetPage onNavigate={vi.fn()} />);

    fireEvent.click(screen.getByTestId('load-demo-retail'));

    await waitFor(() => {
      expect(screen.getByTestId('analysis-results')).toBeInTheDocument();
    }, { timeout: 3000 });

    const targetSelect = screen.getByTestId('map-target-select');
    expect(targetSelect).toHaveValue('target');

    // Change mapping to price
    fireEvent.change(targetSelect, { target: { value: 'price' } });
    await waitFor(() => {
      expect(targetSelect).toHaveValue('price');
    });
  });

  it('identifies quality issues and displays NEEDS ATTENTION badge on unverified audit CSV', async () => {
    render(<UploadDatasetPage onNavigate={vi.fn()} />);

    const demoAuditBtn = screen.getByTestId('load-demo-audit');
    fireEvent.click(demoAuditBtn);

    await waitFor(() => {
      expect(screen.getByTestId('analysis-results')).toBeInTheDocument();
    }, { timeout: 3000 });

    expect(screen.getByTestId('dataset-status-badge')).toHaveTextContent(/NEEDS ATTENTION/i);
    expect(screen.getByText(/unparseable date value/i)).toBeInTheDocument();
  });

  it('displays a clear error state when backend is unavailable and does not silently fall back', async () => {
    const { uploadDatasetToBackend } = await import('../services/api');
    uploadDatasetToBackend.mockRejectedValueOnce(
      new Error('Backend Service Unavailable: Could not connect to ForecastIQ backend at http://localhost:8000.')
    );

    render(<UploadDatasetPage onNavigate={vi.fn()} />);
    fireEvent.click(screen.getByTestId('load-demo-retail'));

    await waitFor(() => {
      expect(screen.getByTestId('upload-error-banner')).toBeInTheDocument();
      expect(screen.getByText(/Backend Service Unavailable/i)).toBeInTheDocument();
    });
  });
});
