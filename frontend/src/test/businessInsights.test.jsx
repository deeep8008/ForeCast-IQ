import React from 'react';
import { describe, it, expect, vi, beforeEach } from 'vitest';
import { render, screen, waitFor } from '@testing-library/react';
import BusinessInsightsPage from '../pages/BusinessInsightsPage';
import ModelComparisonPage from '../pages/ModelComparisonPage';
import * as api from '../services/api';

vi.mock('../services/api', () => ({
  getInsightsFromBackend: vi.fn().mockResolvedValue(null),
  generateInsightsInBackend: vi.fn().mockResolvedValue(null),
  getMonitoringFromBackend: vi.fn().mockResolvedValue(null),
  getEvaluationComparisonFromBackend: vi.fn().mockResolvedValue(null),
  runBacktestInBackend: vi.fn().mockResolvedValue(null),
  getExplorerDataFromBackend: vi.fn().mockResolvedValue(null),
}));

describe('Business Insights & Monitoring UI Engine', () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  const mockUploadedDataset = {
    dataset_id: 'test-dataset-insights-123',
    column_mapping: { series_id: 'series_id', target: 'target', date: 'date' },
    preview: {
      rows: [
        { series_id: 'SERIES_A', date: '2024-01-01', target: 100 },
        { series_id: 'SERIES_B', date: '2024-01-01', target: 200 }
      ]
    }
  };

  const sampleInsightsResponse = {
    dataset_id: 'test-dataset-insights-123',
    series_id: 'SERIES_A',
    model: 'LightGBM',
    horizon: 28,
    demand_outlook: {
      recent_average_demand: 100.0,
      forecast_average_demand: 125.0,
      expected_change_pct: 25.0,
      expected_peak: { value: 140.0, date: '2024-02-15', day_index: 15 },
      expected_low: { value: 110.0, date: '2024-02-02', day_index: 2 },
      forecast_period: '2024-02-01 to 2024-02-28',
      demand_direction: 'INCREASING',
      variability: 0.12,
      uncertainty_level: 'LOW'
    },
    inventory_recommendation: {
      category: 'inventory',
      recommendation: 'CONSIDER STOCKING UP / INCREASING REPLENISHMENT',
      priority: 'HIGH',
      reason: 'Forecast demand is projected to be 25.0% above the recent baseline. Consider reviewing safety stock replenishment.',
      evidence: { recent_average: 100.0, forecast_average: 125.0, expected_change_pct: 25.0, horizon: 28 },
      planning_period: '2024-02-01 to 2024-02-28',
      uncertainty: 'LOW',
      horizon: 28
    },
    staffing_recommendation: {
      category: 'staffing',
      recommendation: 'INCREASE STAFFING / RESOURCE AVAILABILITY',
      priority: 'HIGH',
      reason: 'Demand is projected to remain above baseline (+25.0%). Consider increasing fulfillment capacity coinciding with peak on 2024-02-15.',
      evidence: { recent_average: 100.0, forecast_average: 125.0, horizon: 28 },
      planning_period: '2024-02-01 to 2024-02-28',
      uncertainty: 'LOW',
      horizon: 28
    },
    procurement_recommendation: {
      category: 'procurement',
      recommendation: 'REVIEW PROCUREMENT PLANNING',
      priority: 'HIGH',
      reason: 'Elevated velocity indicates increased replenishment requirements. Review vendor lead times.',
      evidence: { recent_average: 100.0, forecast_average: 125.0, horizon: 28 },
      planning_period: '2024-02-01 to 2024-02-28',
      uncertainty: 'LOW',
      horizon: 28
    },
    demand_planning: {
      action: 'EXPAND CAPACITY / ACCELERATE INVENTORY INFLOW',
      explanation: 'Both recent baseline (100.0) and forward forecast (125.0) indicate expanding velocity (+25.0%).',
      planning_focus: 'Ensure order replenishment buffers are scheduled.'
    },
    horizon_insights: {
      '7D': 'Near-term operational demand projected at average 120.0 units/day.',
      '28D': 'Tactical monthly demand projects 125.0 units/day average.',
      '90D': 'Quarterly strategic trajectory provides run-rate visibility.'
    },
    optional_feature_context: {
      price: {
        available: true,
        recent_avg_price: 3.49,
        insight: 'Historical unit price averaged $3.49. Higher demand is observed alongside promotional price adjustments.'
      }
    }
  };

  it('renders clean empty state for uploaded dataset before computing insights', async () => {
    api.getMonitoringFromBackend.mockResolvedValueOnce({
      dataset_id: 'test-dataset-insights-123',
      status: 'HEALTHY',
      is_alert: false,
      models_tracked: ['LightGBM']
    });
    api.getInsightsFromBackend.mockResolvedValueOnce(null);

    render(
      <BusinessInsightsPage 
        onNavigate={() => {}} 
        uploadedDataset={mockUploadedDataset} 
      />
    );

    expect(screen.getByText(/No Business Insights Computed Yet/i)).toBeInTheDocument();
    expect(screen.getAllByText(/Compute Evidence Insights/i).length).toBeGreaterThan(0);
  });

  it('renders complete business insight cards and monitoring banner when insights data is loaded', async () => {
    api.getMonitoringFromBackend.mockImplementation(async () => ({
      dataset_id: 'test-dataset-insights-123',
      status: 'ACCURACY DRIFT',
      recent_mape: 18.5,
      baseline_mape: 12.0,
      mape_drift_pct: 54.2,
      retraining_alert: 'Model performance has degraded beyond configured error thresholds. Review or retrain the model.',
      is_alert: true,
      models_tracked: ['LightGBM', 'DeepAR']
    }));
    api.getInsightsFromBackend.mockImplementation(async () => sampleInsightsResponse);

    render(
      <BusinessInsightsPage 
        onNavigate={() => {}} 
        uploadedDataset={mockUploadedDataset} 
      />
    );

    // Wait for cached insights to load into DOM
    await waitFor(() => {
      expect(screen.getByText(/1. Demand Outlook/i)).toBeInTheDocument();
    });

    // Check Monitoring Alert
    expect(screen.getByText(/Model Health Status: ACCURACY DRIFT/i)).toBeInTheDocument();
    expect(screen.getByText(/Model performance has degraded beyond configured error thresholds/i)).toBeInTheDocument();

    // Check Inventory card
    expect(screen.getByText(/2. Inventory Recommendation/i)).toBeInTheDocument();
    expect(screen.getByText(/CONSIDER STOCKING UP \/ INCREASING REPLENISHMENT/i)).toBeInTheDocument();

    // Check Staffing card
    expect(screen.getByText(/3. Staffing & Resource Planning/i)).toBeInTheDocument();
    expect(screen.getByText(/INCREASE STAFFING \/ RESOURCE AVAILABILITY/i)).toBeInTheDocument();

    // Check Procurement card
    expect(screen.getByText(/4. Procurement & Vendor Planning/i)).toBeInTheDocument();
    expect(screen.getByText(/REVIEW PROCUREMENT PLANNING/i)).toBeInTheDocument();

    // Check Strategic Planning card
    expect(screen.getByText(/5. Strategic Demand Planning/i)).toBeInTheDocument();

    // Check Optional Feature Context (Price)
    expect(screen.getByText(/6. External Feature Context/i)).toBeInTheDocument();
    expect(screen.getByText(/observed alongside/i)).toBeInTheDocument();
  });

  it('handles empty evaluation state in Model Comparison page cleanly when uploaded dataset is present', () => {
    api.getEvaluationComparisonFromBackend.mockResolvedValueOnce(null);

    render(
      <ModelComparisonPage 
        _onNavigate={() => {}} 
        uploadedDataset={mockUploadedDataset} 
      />
    );

    expect(screen.getByText(/No Backtesting Results Computed for This Dataset Yet/i)).toBeInTheDocument();
    expect(screen.getAllByText(/Run Backtesting Evaluation/i).length).toBeGreaterThan(0);
  });

  it('renders Strategic Demand Planning card non-empty even with minimal backend data and handles unavailable price & holiday', async () => {
    const minimalInsights = {
      ...sampleInsightsResponse,
      demand_planning: {
        state: 'STABLE DEMAND',
        action: 'MAINTAIN STEADY ALLOCATION / STABLE VELOCITY',
        explanation: 'Forecast average (1.8) projects stable velocity vs baseline.',
        planning_focus: 'Standard replenishment buffers apply.'
      },
      optional_feature_context: {
        price: {
          available: false,
          recent_avg_price: null,
          insight: 'Historical unit price unavailable (no valid non-zero price records found for this scope).'
        },
        holiday: {
          available: false,
          events_detected: 0,
          insight: 'No calendar holiday events recorded in historical period.'
        }
      }
    };

    api.getMonitoringFromBackend.mockResolvedValueOnce({
      dataset_id: 'test-dataset-insights-123',
      status: 'HEALTHY',
      is_alert: false,
      models_tracked: ['SARIMA']
    });
    api.getInsightsFromBackend.mockImplementation(async () => minimalInsights);

    render(
      <BusinessInsightsPage 
        onNavigate={() => {}} 
        uploadedDataset={mockUploadedDataset} 
      />
    );

    await waitFor(() => {
      expect(screen.getByText(/5. Strategic Demand Planning/i)).toBeInTheDocument();
    });

    // Strategic Demand Planning card is NOT blank
    expect(screen.getByText(/MAINTAIN STEADY ALLOCATION \/ STABLE VELOCITY/i)).toBeInTheDocument();
    expect(screen.getByText(/Forecast average \(1.8\) projects stable velocity vs baseline./i)).toBeInTheDocument();

    // Price is marked Unavailable and does NOT display $0.0
    expect(screen.getAllByText(/Unavailable/i).length).toBeGreaterThan(0);
    expect(screen.getByText(/no valid non-zero price records found/i)).toBeInTheDocument();
    expect(screen.queryByText(/\$0\.0/i)).not.toBeInTheDocument();

    // Holiday is marked Unavailable without claiming detected events
    expect(screen.getByText(/No calendar holiday events recorded/i)).toBeInTheDocument();
  });

  it('renders holiday summary with "and N more" and complete event_names tags for >5 unique event types', async () => {
    const eventNames = [
      'Halloween', 'VeteransDay', 'Thanksgiving', 'Chanukah End', 'Christmas',
      'NewYear', 'OrthodoxChristmas', 'MartinLutherKingDay', 'SuperBowl', 'LentStart'
    ];
    const holidayInsights = {
      ...sampleInsightsResponse,
      optional_feature_context: {
        holiday: {
          available: true,
          event_records: 16,
          events_detected: 16,
          event_names: eventNames,
          insight: '16 unique calendar event type(s) recorded across 16 observation(s) in the historical period (e.g. Halloween, VeteransDay, Thanksgiving, Chanukah End, Christmas, and 11 more). Demand movements near these dates are noted; no causal relationship is implied.'
        }
      }
    };

    api.getMonitoringFromBackend.mockResolvedValueOnce({
      dataset_id: 'test-dataset-insights-123',
      status: 'HEALTHY',
      is_alert: false,
      models_tracked: ['SARIMA']
    });
    api.getInsightsFromBackend.mockImplementation(async () => holidayInsights);

    render(
      <BusinessInsightsPage 
        onNavigate={() => {}} 
        uploadedDataset={mockUploadedDataset} 
      />
    );

    await waitFor(() => {
      expect(screen.getByText(/6. External Feature Context/i)).toBeInTheDocument();
    });

    // Check summary text with "and 11 more"
    expect(screen.getByText(/16 unique calendar event type\(s\) recorded across 16 observation\(s\)/i)).toBeInTheDocument();
    expect(screen.getByText(/and 11 more/i)).toBeInTheDocument();

    // Check that all 10 event-name tags are individually rendered as tags in the UI
    eventNames.forEach((name) => {
      expect(screen.getByText(name)).toBeInTheDocument();
    });
  });

  it('renders horizon cards with strict window dates and prevents 90D peak from leaking into 28D card', async () => {
    // 90-day forecast scenario where peak is on 2026-01-24 (day 80)
    // 7D card peak is on 2025-10-30, 28D card peak is on 2025-11-15
    const horizonInsights90D = {
      ...sampleInsightsResponse,
      horizon: 90,
      demand_outlook: {
        ...sampleInsightsResponse.demand_outlook,
        expected_peak: { value: 25.22, date: '2026-01-24', day_index: 89 },
        forecast_period: '2025-10-28 to 2026-01-25',
      },
      horizon_insights: {
        '7D': 'Near-term operational demand is projected at an average of 4.2 units/day, with estimated peak of 6.5 units on 2025-10-30 (window: 2025-10-28 to 2025-11-03).',
        '28D': 'Tactical monthly demand projects 5.1 units/day average, with estimated peak of 8.4 units on 2025-11-15 (window: 2025-10-28 to 2025-11-24).',
        '90D': 'Quarterly strategic trajectory projects 6.0 units/day average, with estimated peak of 25.22 units on 2026-01-24 (window: 2025-10-28 to 2026-01-25).',
      },
    };

    api.getMonitoringFromBackend.mockResolvedValueOnce({
      dataset_id: 'test-dataset-insights-123',
      status: 'HEALTHY',
      is_alert: false,
      models_tracked: ['LightGBM'],
    });
    api.getInsightsFromBackend.mockImplementation(async () => horizonInsights90D);

    render(
      <BusinessInsightsPage 
        onNavigate={() => {}} 
        uploadedDataset={mockUploadedDataset} 
      />
    );

    await waitFor(() => {
      expect(screen.getByText(/7-Day Operational Focus/i)).toBeInTheDocument();
      expect(screen.getByText(/28-Day Tactical Rebalance/i)).toBeInTheDocument();
      expect(screen.getByText(/90-Day Strategic Buffer/i)).toBeInTheDocument();
    });

    // 7D card verification: displays its own peak and date, never 2026-01-24
    const card7D = screen.getByText(/Near-term operational demand is projected at an average of 4.2 units\/day/i);
    expect(card7D).toBeInTheDocument();
    expect(card7D.textContent).toContain('peak of 6.5 units on 2025-10-30');
    expect(card7D.textContent).not.toContain('2026-01-24');
    expect(card7D.textContent).not.toContain('25.22');

    // 28D card verification: displays its own peak and date (2025-11-15), NOT 2026-01-24 or 25.22
    const card28D = screen.getByText(/Tactical monthly demand projects 5.1 units\/day average/i);
    expect(card28D).toBeInTheDocument();
    expect(card28D.textContent).toContain('peak of 8.4 units on 2025-11-15');
    expect(card28D.textContent).toContain('window: 2025-10-28 to 2025-11-24');
    expect(card28D.textContent).not.toContain('2026-01-24');
    expect(card28D.textContent).not.toContain('25.22');

    // 90D card verification: contains 25.22 on 2026-01-24
    const card90D = screen.getByText(/Quarterly strategic trajectory projects 6.0 units\/day average/i);
    expect(card90D).toBeInTheDocument();
    expect(card90D.textContent).toContain('peak of 25.22 units on 2026-01-24');
  });

  it('renders Not Evaluated status badges when horizon is unavailable or not evaluated', async () => {
    const partialInsights = {
      ...sampleInsightsResponse,
      horizon: 7,
      horizon_insights: {
        '7D': 'Near-term operational demand is projected at an average of 4.2 units/day, with estimated peak of 6.5 units on 2025-10-30 (window: 2025-10-28 to 2025-11-03).',
        '28D': 'Not evaluated for 7-day horizon. Switch horizon to 28 Days to generate tactical monthly insights.',
        '90D': 'Not evaluated (Current forecast is for 7 days; 90-day horizon requires 90D selection and sufficient history).',
      },
    };

    api.getMonitoringFromBackend.mockResolvedValueOnce({
      dataset_id: 'test-dataset-insights-123',
      status: 'HEALTHY',
      is_alert: false,
      models_tracked: ['LightGBM'],
    });
    api.getInsightsFromBackend.mockImplementation(async () => partialInsights);

    render(
      <BusinessInsightsPage 
        onNavigate={() => {}} 
        uploadedDataset={mockUploadedDataset} 
      />
    );

    await waitFor(() => {
      expect(screen.getByText(/7-Day Operational Focus/i)).toBeInTheDocument();
    });

    // 28D and 90D must show Not Evaluated
    const notEvaluatedBadges = screen.getAllByText(/Not Evaluated/i);
    expect(notEvaluatedBadges.length).toBeGreaterThanOrEqual(2);
  });

  it('displays accurate series-specific planning window and prevents cross-series leakage', async () => {
    // When STORE_A_SKU_001 is selected (historical cutoff 2025-11-06), 7D window is 2025-11-07 to 2025-11-13
    const storeAInsights = {
      ...sampleInsightsResponse,
      series_id: 'STORE_A_SKU_001',
      store_id: 'STORE_A',
      horizon: 28,
      scope: {
        dataset_id: 'test-dataset-insights-123',
        store_id: 'STORE_A',
        category: 'Beverages',
        series_id: 'STORE_A_SKU_001',
        model: 'automatic',
        horizon: 28,
      },
      demand_outlook: {
        ...sampleInsightsResponse.demand_outlook,
        forecast_period: '2025-11-07 to 2025-12-04',
        expected_peak: { value: 18.5, date: '2025-11-10', day_index: 4 },
        expected_low: { value: 12.0, date: '2025-11-08', day_index: 2 },
      },
      inventory_recommendation: {
        ...sampleInsightsResponse.inventory_recommendation,
        planning_period: '2025-11-07 to 2025-12-04',
        horizon: 28,
      },
    };

    api.getExplorerDataFromBackend.mockResolvedValueOnce({
      dataset_id: 'test-dataset-insights-123',
      available_filters: {
        stores: ['STORE_A', 'STORE_B'],
        categories: ['Beverages'],
        items: ['SKU_001'],
        series: ['STORE_A_SKU_001', 'STORE_B_SKU_002'],
      },
      dimensions: { has_store: true, has_category: true, has_item: true, has_series: true },
      scope: {
        store_id: 'STORE_A',
        category: 'Beverages',
        item_id: 'SKU_001',
        series_id: 'STORE_A_SKU_001',
      },
    });

    api.getMonitoringFromBackend.mockResolvedValueOnce({
      dataset_id: 'test-dataset-insights-123',
      status: 'HEALTHY',
      is_alert: false,
      models_tracked: ['ARIMA'],
    });
    api.getInsightsFromBackend.mockResolvedValue(storeAInsights);

    render(
      <BusinessInsightsPage 
        onNavigate={() => {}} 
        uploadedDataset={mockUploadedDataset} 
      />
    );

    await waitFor(() => {
      expect(screen.getByText(/Demand Outlook/i)).toBeInTheDocument();
    });

    // Check forecast period in Demand Outlook and recommendation cards
    const periodMatches = screen.getAllByText(/2025-11-07 to 2025-12-04/i);
    expect(periodMatches.length).toBeGreaterThanOrEqual(1);
    // Peak date must be inside the window
    expect(screen.getByText(/18.5 units \(2025-11-10\)/i)).toBeInTheDocument();
    // Trough date must be inside the window
    expect(screen.getByText(/12 units \(2025-11-08\)/i)).toBeInTheDocument();
  });

  it('passes scope parameters to getMonitoringFromBackend and displays honest INSUFFICIENT DATA state', async () => {
    api.getMonitoringFromBackend.mockResolvedValueOnce({
      dataset_id: 'test-dataset-insights-123',
      status: 'INSUFFICIENT DATA',
      is_alert: false,
      models_tracked: ['LightGBM'],
      mape_drift_pct: null,
      details: [{ message: 'Only 1 evaluation fold available for this scope.' }]
    });

    render(
      <BusinessInsightsPage 
        onNavigate={() => {}} 
        uploadedDataset={mockUploadedDataset} 
      />
    );

    await waitFor(() => {
      expect(api.getMonitoringFromBackend).toHaveBeenCalledWith(
        'test-dataset-insights-123',
        expect.objectContaining({
          model: 'automatic',
          horizon: 28,
        }),
        expect.any(Object)
      );
    });

    await waitFor(() => {
      const banner = screen.getByTestId('model-health-banner');
      expect(banner).toBeInTheDocument();
      expect(banner).toHaveTextContent(/Model Health Status:\s*INSUFFICIENT DATA/i);
      expect(banner).toHaveTextContent(/No empirical multi-fold drift calculated/i);
    });
  });

  it('renders ACCURACY DRIFT alert and explanation when multi-fold error degradation occurs', async () => {
    api.getMonitoringFromBackend.mockResolvedValueOnce({
      dataset_id: 'test-dataset-insights-123',
      status: 'ACCURACY DRIFT',
      is_alert: true,
      models_tracked: ['ARIMA'],
      mape_drift_pct: 35.5,
      retraining_alert: 'Prediction error increased by 35.5% from baseline fold 1 to fold 2.'
    });

    render(
      <BusinessInsightsPage 
        onNavigate={() => {}} 
        uploadedDataset={mockUploadedDataset} 
      />
    );

    await waitFor(() => {
      const banner = screen.getByTestId('model-health-banner');
      expect(banner).toBeInTheDocument();
      expect(banner).toHaveTextContent(/Model Health Status:\s*ACCURACY DRIFT/i);
      expect(banner).toHaveTextContent(/Accuracy Drift:\s*\+35\.5%/i);
      expect(banner).toHaveTextContent(/Prediction error increased by 35\.5%/i);
    });
  });
});



