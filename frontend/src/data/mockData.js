// Realistic M5 dataset structures and multi-horizon forecasting benchmarks
// Designed for the ForecastIQ enterprise analytics interface

export const STORES = [
  { id: 'CA_1', name: 'California 1 (Los Angeles)', state: 'CA' },
  { id: 'CA_2', name: 'California 2 (San Diego)', state: 'CA' },
  { id: 'CA_3', name: 'California 3 (San Francisco)', state: 'CA' },
  { id: 'TX_1', name: 'Texas 1 (Dallas)', state: 'TX' },
  { id: 'TX_2', name: 'Texas 2 (Houston)', state: 'TX' },
  { id: 'TX_3', name: 'Texas 3 (Austin)', state: 'TX' },
  { id: 'WI_1', name: 'Wisconsin 1 (Milwaukee)', state: 'WI' },
  { id: 'WI_2', name: 'Wisconsin 2 (Green Bay)', state: 'WI' },
  { id: 'WI_3', name: 'Wisconsin 3 (Madison)', state: 'WI' }
];

export const CATEGORIES = [
  { id: 'FOODS', name: 'Foods & Perishables', departments: ['FOODS_1', 'FOODS_2', 'FOODS_3'] },
  { id: 'HOBBIES', name: 'Hobbies & Crafts', departments: ['HOBBIES_1', 'HOBBIES_2'] },
  { id: 'HOUSEHOLD', name: 'Household Goods', departments: ['HOUSEHOLD_1', 'HOUSEHOLD_2'] }
];

export const PRODUCTS = [
  {
    id: 'FOODS_3_090',
    name: 'Fresh Bakery Bagels 6pk',
    category: 'FOODS',
    department: 'FOODS_3',
    currentPrice: 1.58,
    avgDaily: 114,
    description: 'High-velocity staple food series with strong weekly seasonality'
  },
  {
    id: 'FOODS_1_001',
    name: 'Organic Lowfat Whole Milk 1 Gal',
    category: 'FOODS',
    department: 'FOODS_1',
    currentPrice: 2.24,
    avgDaily: 28,
    description: 'Perishable dairy item sensitive to SNAP calendar distribution days'
  },
  {
    id: 'HOBBIES_1_004',
    name: 'Classic Acrylic Paint Set 12pc',
    category: 'HOBBIES',
    department: 'HOBBIES_1',
    currentPrice: 4.64,
    avgDaily: 12,
    description: 'Medium intermittent demand hobby series with weekend shopping peaks'
  },
  {
    id: 'HOUSEHOLD_1_005',
    name: 'Ultra Clean Paper Towels 8pk',
    category: 'HOUSEHOLD',
    department: 'HOUSEHOLD_1',
    currentPrice: 6.98,
    avgDaily: 22,
    description: 'Consumable household staple with regular bulk replenishment cycles'
  },
  {
    id: 'FOODS_2_220',
    name: 'Snack Assortment Crunch Box',
    category: 'FOODS',
    department: 'FOODS_2',
    currentPrice: 3.49,
    avgDaily: 45,
    description: 'Event-sensitive grocery product with spikes during sporting weekends'
  }
];

export const MODELS = [
  {
    id: 'auto',
    name: 'Automatic Model Selection',
    type: 'Ensemble & Auto-Routing',
    framework: 'Cross-validated benchmark',
    tag: 'Recommended',
    description: 'Evaluates backtested error across horizons to select optimal model per store-product.'
  },
  {
    id: 'arima',
    name: 'ARIMA',
    type: 'Statistical Baseline',
    framework: 'Statsmodels',
    tag: 'Baseline',
    description: 'Interpretable classical auto-regressive moving average capturing linear trend and autocorrelation.'
  },
  {
    id: 'sarima',
    name: 'SARIMA',
    type: 'Seasonal Statistical Baseline',
    framework: 'Statsmodels',
    tag: 'Seasonal',
    description: 'Seasonal autoregressive moving-average model that captures recurring weekly and multi-period cycles.'
  },
  {
    id: 'prophet',
    name: 'Prophet',
    type: 'Additive Trend & Seasonality',
    framework: 'Prophet',
    tag: 'Calendar-Aware',
    description: 'Decomposable time-series model incorporating holiday effects, trend changes, and weekday seasonality.'
  },
  {
    id: 'lightgbm',
    name: 'LightGBM',
    type: 'Gradient Boosted Decision Trees',
    framework: 'LightGBM + Scikit-learn',
    tag: 'Tabular ML',
    description: 'High-speed gradient boosting using engineered lag, rolling statistics, calendar, and price features.'
  },
  {
    id: 'deepar',
    name: 'DeepAR',
    type: 'Autoregressive Recurrent Neural Net',
    framework: 'Darts + PyTorch',
    tag: 'Deep Learning',
    description: 'Probabilistic RNN forecasting that learns non-linear cross-series dynamics across related products.'
  },
  {
    id: 'tft',
    name: 'Temporal Fusion Transformer (TFT)',
    type: 'Multi-Horizon Attention Architecture',
    framework: 'Darts + PyTorch',
    tag: 'Deep Learning',
    description: 'State-of-the-art transformer with specialized gating and multi-horizon self-attention across covariates.'
  },
  {
    id: 'automatic',
    name: 'Automatic Multi-Model Orchestrator',
    type: 'Unified Ensemble Orchestration',
    framework: 'ForecastIQ Engine',
    tag: 'All Models',
    description: 'Executes forecasts across all 6 architectures (ARIMA, SARIMA, Prophet, LightGBM, DeepAR, TFT) in parallel for cross-model multi-horizon comparison.'
  }
];

export const HORIZONS = [
  { id: '7d', days: 7, label: '7 Days', term: 'Short-term', focus: 'Daily operational inventory & replenishment' },
  { id: '28d', days: 28, label: '28 Days', term: 'Medium-term', focus: 'Store staffing, shift planning & monthly allocation' },
  { id: '90d', days: 90, label: '90 Days', term: 'Long-term', focus: 'Strategic supplier contracts, capacity & lead times' }
];

// Helper to generate realistic daily time series
export function generateTimeSeries(storeId = 'CA_1', productId = 'FOODS_3_090', modelId = 'tft', horizonDays = 28) {
  const product = PRODUCTS.find(p => p.id === productId) || PRODUCTS[0];
  const baseAvg = product.avgDaily;
  
  const historyDays = 90;
  const history = [];
  const forecast = [];
  
  const today = new Date('2016-04-24'); // M5 validation cutoff date
  
  // Generate historical data
  for (let i = historyDays; i >= 1; i--) {
    const d = new Date(today);
    d.setDate(today.getDate() - i);
    const dayOfWeek = d.getDay(); // 0 is Sun, 6 is Sat
    const weekendMultiplier = (dayOfWeek === 0 || dayOfWeek === 6) ? 1.35 : 0.92;
    const monthlyWave = Math.sin((d.getDate() / 30) * Math.PI * 2) * 0.15;
    const randomNoise = (Math.sin(i * 1.7) * 0.2) + ((i % 7 === 0) ? 0.25 : -0.05);
    
    // Occasional event spike
    const isEvent = (i === 15 || i === 44 || i === 72);
    const eventBoost = isEvent ? 1.4 : 1.0;
    
    const sales = Math.max(0, Math.round(baseAvg * weekendMultiplier * (1 + monthlyWave) * (1 + randomNoise) * eventBoost));
    
    history.push({
      date: d.toISOString().split('T')[0],
      sales,
      isEvent,
      eventName: isEvent ? (i === 15 ? 'Easter' : i === 44 ? 'SNAP Distribution' : 'SuperBowl') : null
    });
  }

  // Model-specific variances
  const modelFactors = {
    arima: { bias: 1.02, ciWidth: 0.18, accuracyMape: 16.4, rmse: 14.8 },
    prophet: { bias: 0.99, ciWidth: 0.15, accuracyMape: 14.2, rmse: 12.9 },
    lightgbm: { bias: 1.01, ciWidth: 0.12, accuracyMape: 11.8, rmse: 10.4 },
    deepar: { bias: 0.98, ciWidth: 0.14, accuracyMape: 11.2, rmse: 9.8 },
    tft: { bias: 1.00, ciWidth: 0.11, accuracyMape: 9.6, rmse: 8.7 },
    auto: { bias: 1.00, ciWidth: 0.10, accuracyMape: 9.2, rmse: 8.3 }
  };
  const factor = modelFactors[modelId] || modelFactors.tft;

  // Horizon degradation factor: error grows as horizon lengthens
  const horizonDegradation = horizonDays === 7 ? 0.85 : horizonDays === 28 ? 1.0 : 1.35;
  const currentMape = (factor.accuracyMape * horizonDegradation).toFixed(1);
  const currentRmse = (factor.rmse * horizonDegradation).toFixed(1);

  // Generate future forecast
  let totalForecast = 0;
  for (let j = 0; j < horizonDays; j++) {
    const d = new Date(today);
    d.setDate(today.getDate() + j);
    const dayOfWeek = d.getDay();
    const weekendMultiplier = (dayOfWeek === 0 || dayOfWeek === 6) ? 1.32 : 0.93;
    const monthlyWave = Math.sin((d.getDate() / 30) * Math.PI * 2) * 0.12;
    
    // Future uncertainty widens with step j
    const stepUncertainty = 1 + (j / horizonDays) * 0.25;
    const projected = Math.round(baseAvg * factor.bias * weekendMultiplier * (1 + monthlyWave));
    const ciDelta = Math.round(projected * factor.ciWidth * stepUncertainty);
    
    totalForecast += projected;

    forecast.push({
      date: d.toISOString().split('T')[0],
      forecast: projected,
      lower: Math.max(0, projected - ciDelta),
      upper: projected + ciDelta,
      dayIndex: j + 1
    });
  }

  const avgDailyForecast = Math.round(totalForecast / horizonDays);
  const highestDay = forecast.reduce((max, cur) => cur.forecast > max.forecast ? cur : max, forecast[0]);
  const lowestDay = forecast.reduce((min, cur) => cur.forecast < min.forecast ? cur : min, forecast[0]);

  return {
    store: STORES.find(s => s.id === storeId) || STORES[0],
    product,
    model: MODELS.find(m => m.id === modelId) || MODELS[0],
    horizonDays,
    mape: currentMape,
    rmse: currentRmse,
    history,
    forecast,
    todayDate: today.toISOString().split('T')[0],
    summary: {
      totalDemand: totalForecast.toLocaleString(),
      avgDailyDemand: avgDailyForecast,
      highestDay: { date: highestDay.date, units: highestDay.forecast },
      lowestDay: { date: lowestDay.date, units: lowestDay.forecast }
    }
  };
}

// Objective Model Comparison Benchmark Matrix across all 6 models
export const BENCHMARK_METRICS = [
  {
    modelId: 'arima',
    name: 'ARIMA',
    type: 'Statistical Autoregressive',
    mape7: 14.5,
    mape28: 17.1,
    mape90: 23.4,
    rmse7: 12.9,
    rmse28: 15.3,
    rmse90: 21.0,
    inferenceSpeed: '< 0.15s',
    stability: 'Moderate'
  },
  {
    modelId: 'sarima',
    name: 'SARIMA',
    type: 'Seasonal Statistical Baseline',
    mape7: 13.2,
    mape28: 15.8,
    mape90: 21.2,
    rmse7: 11.9,
    rmse28: 14.1,
    rmse90: 19.5,
    inferenceSpeed: '< 0.25s',
    stability: 'High'
  },
  {
    modelId: 'prophet',
    name: 'Prophet',
    type: 'Additive Trend + Seasonality',
    mape7: 12.1,
    mape28: 14.2,
    mape90: 17.8,
    rmse7: 11.2,
    rmse28: 12.9,
    rmse90: 16.4,
    inferenceSpeed: '1.2s',
    stability: 'High'
  },
  {
    modelId: 'lightgbm',
    name: 'LightGBM',
    type: 'Gradient Boosted Trees (ML)',
    mape7: 10.4,
    mape28: 11.8,
    mape90: 15.1,
    rmse7: 9.3,
    rmse28: 10.4,
    rmse90: 13.8,
    inferenceSpeed: '0.4s',
    stability: 'High'
  },
  {
    modelId: 'deepar',
    name: 'DeepAR',
    type: 'Autoregressive RNN (Deep Learning)',
    mape7: 9.8,
    mape28: 11.2,
    mape90: 13.9,
    rmse7: 8.9,
    rmse28: 9.8,
    rmse90: 12.5,
    inferenceSpeed: '2.5s',
    stability: 'Very High'
  },
  {
    modelId: 'tft',
    name: 'Temporal Fusion Transformer (TFT)',
    type: 'Multi-Horizon Attention (Deep Learning)',
    mape7: 8.7,
    mape28: 9.6,
    mape90: 11.9,
    rmse7: 7.9,
    rmse28: 8.7,
    rmse90: 10.8,
    inferenceSpeed: '3.8s',
    stability: 'Exceptional'
  }
];

// Backtesting rolling folds explanation & fold results
export const BACKTESTING_FOLDS = [
  { fold: 'Fold 1 (Days 1774–1801)', trainPeriod: 'Days 1–1773 (2.5 yrs)', testDays: 28, bestModel: 'TFT', avgMape: 9.4 },
  { fold: 'Fold 2 (Days 1802–1829)', trainPeriod: 'Days 1–1801 (2.6 yrs)', testDays: 28, bestModel: 'DeepAR', avgMape: 9.8 },
  { fold: 'Fold 3 (Days 1830–1857)', trainPeriod: 'Days 1–1829 (2.7 yrs)', testDays: 28, bestModel: 'TFT', avgMape: 9.3 },
  { fold: 'Fold 4 (Days 1858–1885)', trainPeriod: 'Days 1–1857 (2.8 yrs)', testDays: 28, bestModel: 'LightGBM', avgMape: 10.1 },
  { fold: 'Fold 5 (Days 1886–1913)', trainPeriod: 'Days 1–1885 (2.9 yrs)', testDays: 28, bestModel: 'TFT', avgMape: 9.5 }
];

// Plain-language forecast drivers ("What changed?")
export const FORECAST_DRIVERS = [
  {
    id: 'seasonal',
    title: 'Seasonal Pattern',
    badge: 'Recurring Cycle',
    description: 'Demand exhibits a steady 32% weekend uplift peaking on Saturdays and Sundays. The model maintains this rhythmic cycle into the upcoming forecast window.'
  },
  {
    id: 'calendar',
    title: 'Calendar / Holiday Event',
    badge: 'SNAP & Holidays',
    description: 'State food assistance (SNAP) distribution begins on Day 1 of next month in California, creating an expected 18% grocery category surge across CA_1.'
  },
  {
    id: 'price',
    title: 'Price Elasticity',
    badge: 'Price Stability',
    description: 'Selling price has remained stable at $1.58 for 8 consecutive weeks. Without promotional discounting, demand is driven primarily by natural organic consumption.'
  }
];
