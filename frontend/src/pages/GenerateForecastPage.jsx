import React, { useState, useEffect } from 'react';
import { 
  Check, 
  Sparkles, 
  RotateCcw,
  Database,
  Upload,
  Loader2,
  Calendar,
  Layers,
  ShoppingBag,
  Store as StoreIcon
} from 'lucide-react';
import ForecastChart from '../components/ForecastChart';
import { MODELS, HORIZONS } from '../data/mockData';
import { 
  generateForecastInBackend, 
  getExplorerDataFromBackend, 
  getEvaluationComparisonFromBackend 
} from '../services/api';

// The 6 verified core model architectures supported across backend and UI
const CORE_MODELS = [
  MODELS.find(m => m.id === 'arima') || { 
    id: 'arima', 
    name: 'ARIMA', 
    type: 'Statistical Baseline', 
    framework: 'Statsmodels', 
    tag: 'Baseline', 
    description: 'Interpretable classical auto-regressive moving average capturing linear trend and autocorrelation.' 
  },
  MODELS.find(m => m.id === 'sarima') || { 
    id: 'sarima', 
    name: 'SARIMA', 
    type: 'Seasonal Statistical Baseline', 
    framework: 'Statsmodels', 
    tag: 'Seasonal', 
    description: 'Seasonal autoregressive moving-average model that captures recurring weekly and multi-period cycles.' 
  },
  MODELS.find(m => m.id === 'prophet') || { 
    id: 'prophet', 
    name: 'Prophet', 
    type: 'Additive Trend & Seasonality', 
    framework: 'Prophet', 
    tag: 'Calendar-Aware', 
    description: 'Decomposable time-series model incorporating holiday effects, trend changes, and weekday seasonality.' 
  },
  MODELS.find(m => m.id === 'lightgbm') || { 
    id: 'lightgbm', 
    name: 'LightGBM', 
    type: 'Gradient Boosted Decision Trees', 
    framework: 'LightGBM + Scikit-learn', 
    tag: 'Tabular ML', 
    description: 'High-speed gradient boosting using engineered lag, rolling statistics, calendar, and price features.' 
  },
  MODELS.find(m => m.id === 'deepar') || { 
    id: 'deepar', 
    name: 'DeepAR', 
    type: 'Autoregressive Recurrent Neural Net', 
    framework: 'Darts + PyTorch', 
    tag: 'Deep Learning', 
    description: 'Probabilistic RNN forecasting that learns non-linear cross-series dynamics across related products.' 
  },
  MODELS.find(m => m.id === 'tft') || { 
    id: 'tft', 
    name: 'Temporal Fusion Transformer (TFT)', 
    type: 'Multi-Horizon Attention Architecture', 
    framework: 'Darts + PyTorch', 
    tag: 'Deep Learning', 
    description: 'State-of-the-art transformer with specialized gating and multi-horizon self-attention across covariates.' 
  },
];

export default function GenerateForecastPage({ onNavigate, uploadedDataset = null }) {
  // Available filter options derived from active dataset
  const [availableStores, setAvailableStores] = useState([]);
  const [availableCategories, setAvailableCategories] = useState([]);
  const [availableItems, setAvailableItems] = useState([]);
  const [availableSeries, setAvailableSeries] = useState([]);

  // Selected scope state
  const [selectedStore, setSelectedStore] = useState('');
  const [selectedCategory, setSelectedCategory] = useState('');
  const [selectedItem, setSelectedItem] = useState('');
  const [selectedSeries, setSelectedSeries] = useState('');

  // UI status state
  const [isLoadingFilters, setIsLoadingFilters] = useState(false);
  const [filterError, setFilterError] = useState(null);
  const [historicalTrend, setHistoricalTrend] = useState([]);

  // Forecast configuration state
  const [horizonDays, setHorizonDays] = useState(28);
  const [modelId, setModelId] = useState(() => {
    if (typeof window !== 'undefined') {
      const saved = localStorage.getItem('forecastiq_selected_model');
      if (saved && CORE_MODELS.some(m => m.id === saved)) {
        return saved;
      }
    }
    return 'arima';
  });

  const handleSelectModel = (id) => {
    setModelId(id);
    if (typeof window !== 'undefined') {
      localStorage.setItem('forecastiq_selected_model', id);
    }
  };
  const [recommendedModel, setRecommendedModel] = useState(null);
  const [recommendationReason, setRecommendationReason] = useState(null);
  const [forecastError, setForecastError] = useState(null);

  // Generation execution state
  const [isGenerating, setIsGenerating] = useState(false);
  const [generationStep, setGenerationStep] = useState(0);
  const [forecastResult, setForecastResult] = useState(null);

  const stepsList = [
    `Loading real series ${selectedSeries || 'data'} from active dataset...`,
    'Engineering temporal features (lags, rolling statistics, calendar & prices)...',
    `Fitting ${modelId.toUpperCase()} architecture for ${horizonDays}-day horizon...`,
    'Calculating out-of-sample points and 95% confidence intervals...'
  ];

  // ---------------------------------------------------------------------------
  // Load available filters on dataset mount or dataset switch
  // ---------------------------------------------------------------------------
  useEffect(() => {
    if (!uploadedDataset?.dataset_id) {
      setAvailableStores([]);
      setAvailableCategories([]);
      setAvailableItems([]);
      setAvailableSeries([]);
      setSelectedStore('');
      setSelectedCategory('');
      setSelectedItem('');
      setSelectedSeries('');
      setHistoricalTrend([]);
      setForecastResult(null);
      return;
    }

    let isMounted = true;
    setIsLoadingFilters(true);
    setFilterError(null);

    getExplorerDataFromBackend(uploadedDataset.dataset_id, {})
      .then((data) => {
        if (!isMounted) return;

        if (!data || !data.available_filters) {
          // Graceful fallback from uploaded dataset metadata if explorer is empty
          const sqSeries = uploadedDataset.seriesQuality?.series_profiles?.map(s => s.series_id) || [];
          const prSeries = [...new Set(
            (uploadedDataset.previewRows || []).map(r => r.series_id || r[uploadedDataset.mapping?.series_id]).filter(Boolean)
          )];
          const fallback = sqSeries.length > 0 ? sqSeries : prSeries;
          const resolvedFallback = fallback.length > 0 ? fallback : ['default_series'];
          setAvailableSeries(resolvedFallback);
          setSelectedSeries(resolvedFallback[0]);
          setIsLoadingFilters(false);
          return;
        }

        const af = data.available_filters;
        const stores = af.stores || [];
        const cats = af.categories || [];
        const items = af.items || [];
        const series = af.series || [];

        setAvailableStores(stores);
        setAvailableCategories(cats);

        const initialStore = stores.length > 0 ? stores[0] : '';
        setSelectedStore(initialStore);

        if (initialStore) {
          // Cascade to get store-specific items & series
          return getExplorerDataFromBackend(uploadedDataset.dataset_id, { store_id: initialStore })
            .then((storeData) => {
              if (!isMounted) return;
              const storeAf = storeData?.available_filters || af;
              const storeItems = storeAf.items || items;
              const rawStoreSeries = storeAf.series || series || [];
              const storeSeries = rawStoreSeries.length > 0 ? rawStoreSeries : ['default_series'];

              setAvailableItems(storeItems);
              setAvailableSeries(storeSeries);

              const initialItem = storeItems.length > 0 ? storeItems[0] : '';
              const initialSeries = storeSeries[0];
              setSelectedItem(initialItem);
              setSelectedSeries(initialSeries);

              if (storeData?.trend) {
                setHistoricalTrend(storeData.trend);
              }
              setIsLoadingFilters(false);
            });
        } else {
          setAvailableItems(items);
          const resolvedSeries = series.length > 0 ? series : ['default_series'];
          setAvailableSeries(resolvedSeries);
          setSelectedItem(items.length > 0 ? items[0] : '');
          setSelectedSeries(resolvedSeries[0]);
          if (data.trend) {
            setHistoricalTrend(data.trend);
          }
          setIsLoadingFilters(false);
        }
      })
      .catch((err) => {
        if (!isMounted) return;
        setFilterError(err.message || 'Failed to discover dataset series.');
        setIsLoadingFilters(false);
      });

    return () => {
      isMounted = false;
    };
  }, [uploadedDataset?.dataset_id]);

  // Query empirical evaluation results to automatically recommend the winning model
  useEffect(() => {
    let isCancelled = false;
    if (!uploadedDataset?.dataset_id) {
      setRecommendedModel(null);
      setRecommendationReason(null);
      return;
    }

    try {
      const p = getEvaluationComparisonFromBackend?.(uploadedDataset.dataset_id, {
        series_id: selectedSeries || undefined,
        store_id: selectedStore || undefined,
      });
      if (p && typeof p.then === 'function') {
        p.then((evalData) => {
          if (isCancelled || !evalData) return;
          const hKey = `${horizonDays}D`;
          const bestObj = evalData.best_per_horizon?.[hKey];
          if (bestObj && bestObj.best_model) {
            const winModel = bestObj.best_model.toLowerCase();
            setRecommendedModel(winModel);
            setRecommendationReason(
              `Recommended from Step 2 Backtesting: ${winModel.toUpperCase()} achieved lowest ${hKey} error (${bestObj.mape}% MAPE, ${bestObj.rmse} RMSE).`
            );
          } else if (evalData.best_model_overall?.model) {
            const overallModel = evalData.best_model_overall.model.toLowerCase();
            setRecommendedModel(overallModel);
            setRecommendationReason(
              `Recommended from Step 2 Backtesting: ${overallModel.toUpperCase()} achieved best overall error (${evalData.best_model_overall.overall_mape}% MAPE across evaluated horizons).`
            );
          } else {
            setRecommendedModel(null);
            setRecommendationReason(null);
          }
        }).catch(() => {
          if (!isCancelled) {
            setRecommendedModel(null);
            setRecommendationReason(null);
          }
        });
      }
    } catch {
      // Ignore evaluation recommendation errors if offline or unmocked
    }

    return () => {
      isCancelled = true;
    };
  }, [uploadedDataset?.dataset_id, selectedSeries, horizonDays, selectedStore]);

  // ---------------------------------------------------------------------------
  // Cascading handler: Store change clears incompatible series
  // ---------------------------------------------------------------------------
  const handleStoreChange = async (newStore) => {
    setSelectedStore(newStore);
    if (!uploadedDataset?.dataset_id) return;

    setIsLoadingFilters(true);
    try {
      const data = await getExplorerDataFromBackend(uploadedDataset.dataset_id, {
        store_id: newStore || undefined,
      });

      if (data?.available_filters) {
        const newItems = data.available_filters.items || [];
        const newSeries = data.available_filters.series || [];
        setAvailableItems(newItems);
        setAvailableSeries(newSeries);

        // Reset to first compatible item & series
        const nextItem = newItems.includes(selectedItem) ? selectedItem : (newItems[0] || '');
        const nextSeries = newSeries.includes(selectedSeries) ? selectedSeries : (newSeries[0] || '');
        setSelectedItem(nextItem);
        setSelectedSeries(nextSeries);

        if (data.trend) {
          setHistoricalTrend(data.trend);
        }
      }
    } catch (err) {
      setFilterError(err.message || 'Failed to update store selection.');
    } finally {
      setIsLoadingFilters(false);
    }
  };

  // ---------------------------------------------------------------------------
  // Cascading handler: Product / Item change updates matching series
  // ---------------------------------------------------------------------------
  const handleItemChange = async (newItem) => {
    setSelectedItem(newItem);
    if (!uploadedDataset?.dataset_id) return;

    setIsLoadingFilters(true);
    try {
      const data = await getExplorerDataFromBackend(uploadedDataset.dataset_id, {
        store_id: selectedStore || undefined,
        item_id: newItem || undefined,
      });

      if (data?.available_filters) {
        const newSeries = data.available_filters.series || [];
        setAvailableSeries(newSeries);
        const nextSeries = newSeries.includes(selectedSeries) ? selectedSeries : (newSeries[0] || '');
        setSelectedSeries(nextSeries);

        if (data.trend) {
          setHistoricalTrend(data.trend);
        }
      }
    } catch (err) {
      setFilterError(err.message || 'Failed to update product selection.');
    } finally {
      setIsLoadingFilters(false);
    }
  };

  // ---------------------------------------------------------------------------
  // Handler: Series selection change
  // ---------------------------------------------------------------------------
  const handleSeriesChange = async (newSeries) => {
    setSelectedSeries(newSeries);
    if (!uploadedDataset?.dataset_id || !newSeries) return;

    try {
      const data = await getExplorerDataFromBackend(uploadedDataset.dataset_id, {
        series_id: newSeries,
      });
      if (data?.trend) {
        setHistoricalTrend(data.trend);
      }
    } catch {
      // Non-blocking background trend refresh
    }
  };

  // ---------------------------------------------------------------------------
  // Execution: Start authentic backend forecasting
  // ---------------------------------------------------------------------------
  const handleStartForecast = async () => {
    if (!uploadedDataset?.dataset_id) {
      setForecastError('No active dataset found. Please upload a dataset first.');
      return;
    }

    const targetSeries = selectedSeries || (availableSeries.length > 0 ? availableSeries[0] : 'default_series');
    if (!selectedSeries && targetSeries) {
      setSelectedSeries(targetSeries);
    }

    setForecastError(null);
    setIsGenerating(true);
    setGenerationStep(0);
    setForecastResult(null);

    try {
      setGenerationStep(1);
      await new Promise(r => setTimeout(r, 200));

      setGenerationStep(2);
      const realRes = await generateForecastInBackend({
        dataset_id: uploadedDataset.dataset_id,
        series_id: targetSeries,
        model: modelId,
        horizon: horizonDays,
      });

      setGenerationStep(3);
      await new Promise(r => setTimeout(r, 200));

      // Format real backend forecast points for ForecastChart
      const formattedForecast = (realRes.points || []).map((pt, idx) => ({
        date: pt.date,
        forecast: pt.forecast,
        lower: pt.lower_bound != null ? pt.lower_bound : null,
        upper: pt.upper_bound != null ? pt.upper_bound : null,
        dayIndex: idx + 1,
      }));

      const totalForecast = Math.round((realRes.forecast || []).reduce((a, b) => a + b, 0));
      const avgDaily = Math.round(totalForecast / horizonDays);

      let peakDay = { date: realRes.dates?.[0] || '', units: realRes.forecast?.[0] || 0 };
      let troughDay = { date: realRes.dates?.[0] || '', units: realRes.forecast?.[0] || 0 };
      if (realRes.points && realRes.points.length > 0) {
        const sorted = [...realRes.points].sort((a, b) => b.forecast - a.forecast);
        peakDay = { date: sorted[0].date, units: sorted[0].forecast };
        troughDay = { date: sorted[sorted.length - 1].date, units: sorted[sorted.length - 1].forecast };
      }

      // Query evaluation benchmark if available
      let mapeVal = 'Unavailable (Not evaluated)';
      let rmseVal = 'Unavailable (Not evaluated)';
      try {
        const evalData = await getEvaluationComparisonFromBackend(uploadedDataset.dataset_id, {
          series_id: selectedSeries,
          store_id: selectedStore || undefined,
        });
        const hKey = `${horizonDays}D`;
        const mKey = modelId.toLowerCase();
        if (evalData?.table_1_model_x_horizon_mape?.[mKey]?.[hKey] != null) {
          mapeVal = `${evalData.table_1_model_x_horizon_mape[mKey][hKey]}%`;
        }
        if (evalData?.table_2_model_x_horizon_rmse?.[mKey]?.[hKey] != null) {
          rmseVal = `${evalData.table_2_model_x_horizon_rmse[mKey][hKey]}`;
        }
      } catch {
        // Evaluation not run yet or unavailable
      }

      const activeModelMeta = CORE_MODELS.find(m => m.id === modelId) || {
        name: realRes.model,
        type: 'Time-Series Model',
        framework: 'ForecastIQ Engine',
      };

      // Ensure historical trend is present for chart visualization
      let chartHistory = historicalTrend;
      if (!chartHistory || chartHistory.length === 0) {
        try {
          const exp = await getExplorerDataFromBackend(uploadedDataset.dataset_id, {
            series_id: selectedSeries,
          });
          if (exp?.trend) {
            chartHistory = exp.trend;
            setHistoricalTrend(exp.trend);
          }
        } catch {
          // ignore
        }
      }

      setForecastResult({
        store: { 
          id: selectedStore || selectedSeries, 
          name: selectedStore ? `Store ${selectedStore}` : selectedSeries 
        },
        product: { 
          id: selectedItem || selectedSeries, 
          name: selectedItem || selectedSeries, 
          category: selectedCategory || 'Active Series' 
        },
        series_id: selectedSeries,
        model: {
          id: modelId,
          name: realRes.model || activeModelMeta.name,
          type: activeModelMeta.type,
          framework: activeModelMeta.framework,
        },
        horizonDays: horizonDays,
        mape: mapeVal,
        rmse: rmseVal,
        history: chartHistory || [],
        forecast: formattedForecast,
        todayDate: realRes.training_end || new Date().toISOString().split('T')[0],
        summary: {
          totalDemand: totalForecast.toLocaleString(),
          avgDailyDemand: avgDaily,
          highestDay: peakDay,
          lowestDay: troughDay,
        },
        isRealBackend: true,
        components: realRes.components,
      });
      setIsGenerating(false);
    } catch (err) {
      setIsGenerating(false);
      setForecastError(err.message || 'Forecast generation failed on backend.');
    }
  };

  // ---------------------------------------------------------------------------
  // Horizon switching in the result view: re-forecasts with real backend
  // ---------------------------------------------------------------------------
  const handleHorizonSwitch = async (newDays) => {
    setHorizonDays(newDays);
    if (!uploadedDataset?.dataset_id || !selectedSeries) return;

    setIsGenerating(true);
    setForecastError(null);
    try {
      const realRes = await generateForecastInBackend({
        dataset_id: uploadedDataset.dataset_id,
        series_id: selectedSeries,
        model: modelId,
        horizon: newDays,
      });

      const formattedForecast = (realRes.points || []).map((pt, idx) => ({
        date: pt.date,
        forecast: pt.forecast,
        lower: pt.lower_bound != null ? pt.lower_bound : null,
        upper: pt.upper_bound != null ? pt.upper_bound : null,
        dayIndex: idx + 1,
      }));

      const totalForecast = Math.round((realRes.forecast || []).reduce((a, b) => a + b, 0));
      const avgDaily = Math.round(totalForecast / newDays);

      let peakDay = { date: realRes.dates?.[0] || '', units: realRes.forecast?.[0] || 0 };
      let troughDay = { date: realRes.dates?.[0] || '', units: realRes.forecast?.[0] || 0 };
      if (realRes.points && realRes.points.length > 0) {
        const sorted = [...realRes.points].sort((a, b) => b.forecast - a.forecast);
        peakDay = { date: sorted[0].date, units: sorted[0].forecast };
        troughDay = { date: sorted[sorted.length - 1].date, units: sorted[sorted.length - 1].forecast };
      }

      // Query evaluation benchmark for the switched horizon
      let mapeVal = 'Unavailable (Not evaluated)';
      let rmseVal = 'Unavailable (Not evaluated)';
      try {
        const evalData = await getEvaluationComparisonFromBackend(uploadedDataset.dataset_id, {
          series_id: selectedSeries,
          store_id: selectedStore || undefined,
        });
        const hKey = `${newDays}D`;
        const mKey = modelId.toLowerCase();
        if (evalData?.table_1_model_x_horizon_mape?.[mKey]?.[hKey] != null) {
          mapeVal = `${evalData.table_1_model_x_horizon_mape[mKey][hKey]}%`;
        }
        if (evalData?.table_2_model_x_horizon_rmse?.[mKey]?.[hKey] != null) {
          rmseVal = `${evalData.table_2_model_x_horizon_rmse[mKey][hKey]}`;
        }
      } catch {
        // Evaluation not run yet or unavailable
      }

      setForecastResult(prev => ({
        ...prev,
        horizonDays: newDays,
        mape: mapeVal,
        rmse: rmseVal,
        forecast: formattedForecast,
        summary: {
          totalDemand: totalForecast.toLocaleString(),
          avgDailyDemand: avgDaily,
          highestDay: peakDay,
          lowestDay: troughDay,
        }
      }));
    } catch (err) {
      setForecastError(err.message || 'Forecast generation failed for selected horizon.');
    } finally {
      setIsGenerating(false);
    }
  };

  // ---------------------------------------------------------------------------
  // Empty State: No active dataset uploaded
  // ---------------------------------------------------------------------------
  if (!uploadedDataset?.dataset_id) {
    return (
      <div className="space-y-8 max-w-7xl mx-auto pb-12">
        <div>
          <div className="text-xs font-semibold uppercase tracking-wider text-[#8E83A3]">
            Inference Engine
          </div>
          <h1 className="text-3xl font-bold font-heading text-[#1F1B2C]">
            Generate a Forecast
          </h1>
          <p className="text-sm text-[#5F5670] mt-1 max-w-2xl">
            Configure multi-horizon forecasts with real time-series models across stores, products, and temporal horizons.
          </p>
        </div>

        <div className="p-12 rounded-3xl bg-white border border-[#E5D9F2] shadow-xs text-center max-w-xl mx-auto space-y-6 my-8">
          <div className="w-16 h-16 mx-auto rounded-3xl bg-[#F5EFFF] border border-[#CDC1FF] flex items-center justify-center text-[#A294F9]">
            <Database className="w-8 h-8" />
          </div>
          <div>
            <h3 className="text-xl font-bold font-heading text-[#1F1B2C]">
              No Active Dataset Loaded
            </h3>
            <p className="text-xs text-[#5F5670] mt-1.5 max-w-md mx-auto leading-relaxed">
              Please upload or convert a time-series dataset first. Once ingested and mapped, real series from your dataset will be loaded here for multi-horizon model forecasting.
            </p>
          </div>
          <button
            onClick={() => onNavigate && onNavigate('upload')}
            className="px-6 py-3 rounded-2xl bg-[#A294F9] text-white font-bold text-xs hover:bg-[#9181f7] shadow-sm hover:shadow transition-all inline-flex items-center gap-2"
          >
            <Upload className="w-4 h-4" />
            <span>Upload / Select Dataset</span>
          </button>
        </div>
      </div>
    );
  }

  return (
    <div className="space-y-8 max-w-7xl mx-auto pb-12">
      {/* Header */}
      <div>
        <div className="text-xs font-semibold uppercase tracking-wider text-[#8E83A3]">
          Inference Engine
        </div>
        <h1 className="text-3xl font-bold font-heading text-[#1F1B2C]">
          Generate a Forecast
        </h1>
        <p className="text-sm text-[#5F5670] mt-1 max-w-2xl">
          Choose what you want to forecast across store tiers, products, multi-step planning horizons, and model architectures.
        </p>
      </div>

      {/* Uploaded Dataset Context Banner */}
      <div className="p-4 rounded-2xl bg-white border border-[#CDC1FF] shadow-xs flex flex-col sm:flex-row sm:items-center justify-between gap-3">
        <div className="flex items-center gap-3">
          <span className="w-2.5 h-2.5 rounded-full bg-emerald-500 shrink-0 animate-pulse"></span>
          <div>
            <div className="text-xs font-bold text-[#1F1B2C]">
              Active Custom Dataset: <span className="text-[#A294F9]">{uploadedDataset.profile?.filename || uploadedDataset.filename}</span>
            </div>
            <div className="text-[11px] text-[#5F5670]">
              Universal mapped: date (<span className="font-mono">{uploadedDataset.mapping?.date}</span>), series_id (<span className="font-mono">{uploadedDataset.mapping?.series_id}</span>), target (<span className="font-mono">{uploadedDataset.mapping?.target}</span>) • {uploadedDataset.profile?.rowsCount ? uploadedDataset.profile.rowsCount.toLocaleString() : uploadedDataset.previewRows?.length || 0} rows • {uploadedDataset.profile?.uniqueSeriesCount || availableSeries.length} series
            </div>
          </div>
        </div>
        <button
          onClick={() => onNavigate('upload')}
          className="text-xs font-semibold text-[#A294F9] hover:text-[#9181f7] underline shrink-0"
        >
          Review Mapping
        </button>
      </div>

      {/* Error message banners */}
      {(forecastError || filterError) && (
        <div className="p-4 rounded-2xl bg-red-50 border border-red-200 text-red-800 text-xs font-semibold flex items-center justify-between">
          <span>{forecastError || filterError}</span>
          <button 
            onClick={() => { setForecastError(null); setFilterError(null); }} 
            className="text-red-600 hover:text-red-900 ml-4 font-bold"
          >
            Dismiss
          </button>
        </div>
      )}

      {/* Main Configuration Steps Container */}
      {!forecastResult && !isGenerating && (
        <div className="space-y-6">
          <div className="p-6 lg:p-8 rounded-3xl bg-white border border-[#E5D9F2] shadow-xs space-y-8">
            {/* Step 1 & Step 2 Row */}
            <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
              {/* Step 1: Select Store */}
              <div className="space-y-2.5">
                <div className="flex items-center justify-between">
                  <div className="flex items-center gap-2">
                    <span className="w-5 h-5 rounded-full bg-[#A294F9] text-white text-[11px] font-bold flex items-center justify-center">
                      1
                    </span>
                    <label htmlFor="store-select" className="text-sm font-bold font-heading text-[#1F1B2C]">
                      Select Store
                    </label>
                  </div>
                  {isLoadingFilters && (
                    <span className="text-[10px] text-[#8E83A3] flex items-center gap-1">
                      <Loader2 className="w-3 h-3 animate-spin text-[#A294F9]" /> Updating
                    </span>
                  )}
                </div>

                <select
                  id="store-select"
                  aria-label="Select Store"
                  value={selectedStore}
                  onChange={(e) => handleStoreChange(e.target.value)}
                  disabled={isLoadingFilters}
                  className="w-full bg-[#F5EFFF] border border-[#CDC1FF] rounded-2xl px-4 py-3 text-sm font-semibold text-[#1F1B2C] outline-none hover:border-[#A294F9] transition-colors disabled:opacity-60"
                >
                  {availableStores.length > 0 ? (
                    availableStores.map((s) => (
                      <option key={s} value={s}>
                        {s}
                      </option>
                    ))
                  ) : (
                    <option value="">Default / Dataset Global Scope</option>
                  )}
                </select>
                <div className="text-[11px] text-[#8E83A3]">
                  Selected store scopes product hierarchy and historical trend telemetry.
                </div>
              </div>

              {/* Step 2: Select Product / Series */}
              <div className="space-y-2.5">
                <div className="flex items-center justify-between">
                  <div className="flex items-center gap-2">
                    <span className="w-5 h-5 rounded-full bg-[#A294F9] text-white text-[11px] font-bold flex items-center justify-center">
                      2
                    </span>
                    <label htmlFor="product-select" className="text-sm font-bold font-heading text-[#1F1B2C]">
                      Select Product & Series
                    </label>
                  </div>
                </div>

                <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
                  {/* Product / Item select */}
                  <div>
                    <label htmlFor="product-select" className="block text-[10px] font-bold text-[#8E83A3] uppercase tracking-wider mb-1">
                      Product
                    </label>
                    <select
                      id="product-select"
                      aria-label="Select Product"
                      value={selectedItem}
                      onChange={(e) => handleItemChange(e.target.value)}
                      disabled={isLoadingFilters}
                      className="w-full bg-[#F5EFFF] border border-[#CDC1FF] rounded-2xl px-3.5 py-2.5 text-xs font-semibold text-[#1F1B2C] outline-none hover:border-[#A294F9] transition-colors disabled:opacity-60"
                    >
                      {availableItems.length > 0 ? (
                        availableItems.map((item) => (
                          <option key={item} value={item}>
                            {item}
                          </option>
                        ))
                      ) : (
                        <option value={selectedSeries || ''}>{selectedSeries || 'Single Series'}</option>
                      )}
                    </select>
                  </div>

                  {/* Series ID select */}
                  <div>
                    <label htmlFor="series-select" className="block text-[10px] font-bold text-[#8E83A3] uppercase tracking-wider mb-1">
                      Target Series
                    </label>
                    <select
                      id="series-select"
                      aria-label="Select Series"
                      value={selectedSeries}
                      onChange={(e) => handleSeriesChange(e.target.value)}
                      disabled={isLoadingFilters}
                      className="w-full bg-[#F5EFFF] border border-[#CDC1FF] rounded-2xl px-3.5 py-2.5 text-xs font-semibold text-[#1F1B2C] outline-none hover:border-[#A294F9] transition-colors disabled:opacity-60"
                    >
                      {availableSeries.length > 0 ? (
                        availableSeries.map((s) => (
                          <option key={s} value={s}>
                            {s}
                          </option>
                        ))
                      ) : (
                        <option value="">No series found</option>
                      )}
                    </select>
                  </div>
                </div>

                <div className="text-[11px] text-[#8E83A3]">
                  Active target series feeding out-of-sample models.
                </div>
              </div>
            </div>

            {/* Step 3: Select Forecast Horizon */}
            <div className="space-y-3">
              <div className="flex items-center gap-2">
                <span className="w-5 h-5 rounded-full bg-[#A294F9] text-white text-[11px] font-bold flex items-center justify-center">
                  3
                </span>
                <label className="text-sm font-bold font-heading text-[#1F1B2C]">
                  Select Forecast Horizon
                </label>
              </div>

              <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
                {HORIZONS.map((h) => {
                  const isSelected = horizonDays === h.days;
                  return (
                    <div
                      key={h.id}
                      onClick={() => setHorizonDays(h.days)}
                      className={`
                        p-5 rounded-2xl border cursor-pointer transition-all relative
                        ${isSelected 
                          ? 'bg-[#F5EFFF] border-[#A294F9] shadow-sm ring-1 ring-[#A294F9]' 
                          : 'bg-white border-[#E5D9F2] hover:border-[#CDC1FF]'
                        }
                      `}
                    >
                      <div className="flex items-center justify-between">
                        <span className={`text-xs font-semibold px-2.5 py-0.5 rounded-full ${
                          isSelected ? 'bg-[#A294F9] text-white' : 'bg-[#E5D9F2]/70 text-[#5F5670]'
                        }`}>
                          {h.term}
                        </span>
                        {isSelected && (
                          <div className="w-5 h-5 rounded-full bg-[#A294F9] text-white flex items-center justify-center">
                            <Check className="w-3.5 h-3.5" />
                          </div>
                        )}
                      </div>

                      <div className="text-2xl font-extrabold font-heading text-[#1F1B2C] mt-3">
                        {h.label}
                      </div>

                      <p className="text-xs text-[#5F5670] mt-1.5 leading-relaxed">
                        {h.focus}
                      </p>
                    </div>
                  );
                })}
              </div>
            </div>

            {/* Step 4: Select Model (6 Core Architectures) */}
            <div className="space-y-3">
              <div className="flex items-center justify-between">
                <div className="flex items-center gap-2">
                  <span className="w-5 h-5 rounded-full bg-[#A294F9] text-white text-[11px] font-bold flex items-center justify-center">
                    4
                  </span>
                  <label className="text-sm font-bold font-heading text-[#1F1B2C]">
                    Select Model
                  </label>
                </div>
                {recommendedModel && (
                  <button
                    type="button"
                    onClick={() => handleSelectModel(recommendedModel)}
                    className="text-[11px] font-bold px-2.5 py-1 rounded-full bg-emerald-100 text-emerald-800 hover:bg-emerald-200 transition-colors flex items-center gap-1.5"
                    data-testid="use-recommended-model-btn"
                  >
                    <span>★ Use Recommended: {recommendedModel.toUpperCase()}</span>
                  </button>
                )}
              </div>

              {recommendationReason && (
                <div className="p-3 rounded-xl bg-emerald-50/70 border border-emerald-200 text-emerald-900 text-[11px] flex items-center gap-2">
                  <Check className="w-4 h-4 text-emerald-600 shrink-0" />
                  <span>{recommendationReason}</span>
                </div>
              )}

              <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-3.5">
                {CORE_MODELS.map((m) => {
                  const isSelected = modelId === m.id;
                  const isRecommended = recommendedModel === m.id;
                  return (
                    <div
                      key={m.id}
                      onClick={() => handleSelectModel(m.id)}
                      className={`
                        p-4 rounded-2xl border cursor-pointer transition-all flex flex-col justify-between relative
                        ${isSelected 
                          ? 'bg-[#F5EFFF] border-[#A294F9] shadow-sm ring-1 ring-[#A294F9]' 
                          : isRecommended
                            ? 'bg-emerald-50/40 border-emerald-300 hover:border-emerald-400'
                            : 'bg-white border-[#E5D9F2] hover:border-[#CDC1FF]'
                        }
                      `}
                    >
                      <div>
                        <div className="flex items-center justify-between mb-1.5">
                          <span className="text-[10px] uppercase font-bold tracking-wider text-[#8E83A3]">
                            {m.type}
                          </span>
                          <div className="flex items-center gap-1.5">
                            {isRecommended && (
                              <span className="text-[9px] font-extrabold uppercase px-1.5 py-0.5 rounded bg-emerald-200 text-emerald-900 tracking-wider">
                                Best Model
                              </span>
                            )}
                            {isSelected && (
                              <span className="w-4 h-4 rounded-full bg-[#A294F9] text-white flex items-center justify-center">
                                <Check className="w-2.5 h-2.5" />
                              </span>
                            )}
                          </div>
                        </div>

                        <div className="text-sm font-bold font-heading text-[#1F1B2C]">
                          {m.name}
                        </div>

                        <p className="text-[11px] text-[#5F5670] mt-1 line-clamp-2 leading-relaxed">
                          {m.description}
                        </p>
                      </div>

                      <div className="mt-3 pt-2 border-t border-[#E5D9F2]/70 flex items-center justify-between text-[10px] text-[#8E83A3]">
                        <span>{m.framework}</span>
                        <span className="font-semibold text-[#A294F9]">{m.tag}</span>
                      </div>
                    </div>
                  );
                })}
              </div>
            </div>

            {/* Primary Action Button */}
            <div className="pt-4 flex items-center justify-end">
              <button
                id="generate-forecast-button"
                data-testid="generate-forecast-button"
                onClick={handleStartForecast}
                disabled={isLoadingFilters || !selectedSeries}
                className="w-full sm:w-auto px-8 py-3.5 rounded-2xl bg-[#A294F9] text-white font-bold text-sm hover:bg-[#9181f7] shadow-sm hover:shadow transition-all flex items-center justify-center gap-2 disabled:opacity-50 disabled:cursor-not-allowed"
              >
                <Sparkles className="w-4 h-4" />
                <span>Generate Forecast</span>
              </button>
            </div>
          </div>
        </div>
      )}

      {/* Progress State */}
      {isGenerating && (
        <div className="p-12 rounded-3xl bg-white border border-[#E5D9F2] shadow-xs text-center max-w-xl mx-auto space-y-6 my-8">
          <div className="w-16 h-16 mx-auto rounded-3xl bg-[#F5EFFF] border border-[#CDC1FF] flex items-center justify-center text-[#A294F9]">
            <Sparkles className="w-8 h-8 animate-pulse" />
          </div>

          <div>
            <h3 className="text-xl font-bold font-heading text-[#1F1B2C]">
              Generating Forecast...
            </h3>
            <p className="text-xs text-[#5F5670] mt-1">
              Executing pipeline for {selectedStore || 'Store'} • {selectedItem || selectedSeries} across {horizonDays} days with {modelId.toUpperCase()}.
            </p>
          </div>

          <div className="space-y-2.5 text-left max-w-md mx-auto">
            {stepsList.map((stepText, idx) => {
              const isDone = generationStep > idx;
              const isCurrent = generationStep === idx;
              return (
                <div
                  key={idx}
                  className={`flex items-center gap-3 p-3 rounded-xl border text-xs transition-all ${
                    isDone 
                      ? 'bg-[#F5EFFF] border-[#CDC1FF] text-[#1F1B2C] font-medium' 
                      : isCurrent 
                        ? 'bg-white border-[#A294F9] text-[#A294F9] font-bold shadow-xs' 
                        : 'bg-gray-50 border-gray-100 text-[#8E83A3]'
                  }`}
                >
                  <div className={`w-4 h-4 rounded-full flex items-center justify-center shrink-0 ${
                    isDone ? 'bg-[#A294F9] text-white' : isCurrent ? 'border-2 border-[#A294F9]' : 'border border-gray-300'
                  }`}>
                    {isDone && <Check className="w-2.5 h-2.5" />}
                  </div>
                  <span>{stepText}</span>
                </div>
              );
            })}
          </div>
        </div>
      )}

      {/* FORECAST RESULTS VIEW */}
      {forecastResult && !isGenerating && (
        <div className="space-y-6">
          {/* Header Summary / Configuration Badges */}
          <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4 p-5 rounded-2xl bg-white border border-[#E5D9F2] shadow-xs">
            <div className="flex flex-wrap items-center gap-2 text-xs">
              <span className="font-semibold text-[#1F1B2C]">Active Run:</span>
              <span className="px-2.5 py-1 rounded-lg bg-[#F5EFFF] text-[#1F1B2C] border border-[#CDC1FF] font-medium">
                {`Store: ${forecastResult.store.name}`}
              </span>
              <span className="px-2.5 py-1 rounded-lg bg-[#F5EFFF] text-[#1F1B2C] border border-[#CDC1FF] font-medium">
                {`Product: ${forecastResult.product.id}`}
              </span>
              <span className="px-2.5 py-1 rounded-lg bg-[#F5EFFF] text-[#1F1B2C] border border-[#CDC1FF] font-medium font-mono text-[11px]">
                {`Series: ${forecastResult.series_id}`}
              </span>
              <span className="px-2.5 py-1 rounded-lg bg-[#E5D9F2] text-[#1F1B2C] border border-[#CDC1FF] font-semibold">
                {`Model: ${forecastResult.model.name}`}
              </span>
            </div>

            <button
              onClick={() => {
                setForecastResult(null);
              }}
              className="inline-flex items-center gap-1.5 text-xs font-semibold text-[#5F5670] hover:text-[#1F1B2C] px-3 py-1.5 rounded-xl border border-[#E5D9F2] bg-[#F5EFFF] transition-colors"
            >
              <RotateCcw className="w-3.5 h-3.5" />
              <span>Modify Selection</span>
            </button>
          </div>

          {/* Top 4 Summary Cards */}
          <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4">
            <div className="p-5 rounded-2xl bg-white border border-[#E5D9F2] shadow-xs space-y-1">
              <div className="text-[11px] font-semibold uppercase tracking-wider text-[#8E83A3]">
                Forecast Horizon
              </div>
              <div className="text-2xl font-bold font-heading text-[#1F1B2C]">
                {`${forecastResult.horizonDays} Days`}
              </div>
              <div className="text-xs text-[#5F5670]">
                {forecastResult.horizonDays === 7 ? 'Short-term operational' : forecastResult.horizonDays === 28 ? 'Medium-term tactical' : 'Long-term strategic'}
              </div>
            </div>

            <div className="p-5 rounded-2xl bg-white border border-[#E5D9F2] shadow-xs space-y-1">
              <div className="text-[11px] font-semibold uppercase tracking-wider text-[#8E83A3]">
                Total Forecasted Demand
              </div>
              <div className="text-2xl font-bold font-heading text-[#A294F9]">
                {forecastResult.summary.totalDemand} <span className="text-xs font-normal text-[#5F5670]">units</span>
              </div>
              <div className="text-xs text-[#5F5670]">
                Avg {forecastResult.summary.avgDailyDemand} units/day
              </div>
            </div>

            <div className="p-5 rounded-2xl bg-white border border-[#E5D9F2] shadow-xs space-y-1">
              <div className="text-[11px] font-semibold uppercase tracking-wider text-[#8E83A3]">
                Backtested MAPE
              </div>
              <div className={`font-bold font-heading ${forecastResult.mape.includes('%') ? 'text-2xl text-emerald-600' : 'text-sm text-[#8E83A3] mt-1'}`}>
                {forecastResult.mape}
              </div>
              <div className="text-xs text-[#5F5670]">
                Mean Absolute Percentage Error
              </div>
            </div>

            <div className="p-5 rounded-2xl bg-white border border-[#E5D9F2] shadow-xs space-y-1">
              <div className="text-[11px] font-semibold uppercase tracking-wider text-[#8E83A3]">
                Backtested RMSE
              </div>
              <div className={`font-bold font-heading ${!forecastResult.rmse.includes('Unavailable') && forecastResult.rmse !== '—' ? 'text-2xl text-[#1F1B2C]' : 'text-sm text-[#8E83A3] mt-1'}`}>
                {forecastResult.rmse} {!forecastResult.rmse.includes('Unavailable') && forecastResult.rmse !== '—' && <span className="text-xs font-normal text-[#5F5670]">units</span>}
              </div>
              <div className="text-xs text-[#5F5670]">
                Root Mean Squared Error
              </div>
            </div>
          </div>

          {/* Main Chart Card with Real Horizon Switching */}
          <div className="p-6 lg:p-8 rounded-3xl bg-white border border-[#E5D9F2] shadow-xs space-y-4">
            <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4">
              <div>
                <h3 className="text-xl font-bold font-heading text-[#1F1B2C]">
                  Actual vs Forecast
                </h3>
                <p className="text-xs text-[#5F5670]">
                  Multi-horizon predictions with 95% confidence intervals from {forecastResult.model.name}. Switch horizons seamlessly below.
                </p>
              </div>
            </div>

            <ForecastChart
              history={forecastResult.history}
              forecast={forecastResult.forecast}
              todayDate={forecastResult.todayDate}
              horizonDays={forecastResult.horizonDays}
              onHorizonChange={handleHorizonSwitch}
              showHorizonSwitch={true}
              storeName={forecastResult.store.name}
              productName={forecastResult.product.name}
            />

            {/* Forecast Summary Details Grid */}
            <div className="pt-4 border-t border-[#F5EFFF] grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4 text-xs">
              <div className="p-3.5 rounded-xl bg-[#F5EFFF]/60 border border-[#E5D9F2]">
                <div className="text-[#8E83A3]">Total Demand</div>
                <div className="font-bold text-sm text-[#1F1B2C] mt-0.5">
                  {forecastResult.summary.totalDemand} units
                </div>
              </div>

              <div className="p-3.5 rounded-xl bg-[#F5EFFF]/60 border border-[#E5D9F2]">
                <div className="text-[#8E83A3]">Average Daily Demand</div>
                <div className="font-bold text-sm text-[#1F1B2C] mt-0.5">
                  {forecastResult.summary.avgDailyDemand} units / day
                </div>
              </div>

              <div className="p-3.5 rounded-xl bg-[#F5EFFF]/60 border border-[#E5D9F2]">
                <div className="text-[#8E83A3]">Peak Forecast Day</div>
                <div className="font-bold text-sm text-[#1F1B2C] mt-0.5">
                  {forecastResult.summary.highestDay.units} units ({forecastResult.summary.highestDay.date})
                </div>
              </div>

              <div className="p-3.5 rounded-xl bg-[#F5EFFF]/60 border border-[#E5D9F2]">
                <div className="text-[#8E83A3]">Trough Forecast Day</div>
                <div className="font-bold text-sm text-[#1F1B2C] mt-0.5">
                  {forecastResult.summary.lowestDay.units} units ({forecastResult.summary.lowestDay.date})
                </div>
              </div>
            </div>
          </div>

          {/* Action Links: Step 4 -> Step 5 */}
          <div className="flex flex-col sm:flex-row items-center justify-between gap-4 p-5 rounded-2xl bg-white border border-[#E5D9F2] shadow-xs">
            <div>
              <div className="text-xs font-bold text-[#1F1B2C]">
                Step 4 Completed: Forecast Generated
              </div>
              <div className="text-xs text-[#5F5670] mt-0.5">
                Proceed to business decision support, inventory replenishment policies, and accuracy drift monitoring.
              </div>
            </div>
            <div className="flex items-center gap-3 shrink-0">
              <button
                onClick={() => onNavigate('insights')}
                className="px-5 py-2.5 rounded-xl bg-[#A294F9] text-white hover:bg-[#9181f7] text-xs font-semibold transition-colors shadow-xs flex items-center gap-1.5"
                data-testid="continue-to-insights-btn"
              >
                <span>Proceed to Business Insights (Step 5) →</span>
              </button>
              <button
                onClick={() => onNavigate('comparison')}
                className="px-4 py-2.5 rounded-xl bg-[#F5EFFF] text-[#1F1B2C] hover:bg-[#E5D9F2] border border-[#CDC1FF] text-xs font-semibold transition-colors"
                data-testid="continue-to-comparison-btn"
              >
                ← Back to Model Comparison (Step 3)
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
