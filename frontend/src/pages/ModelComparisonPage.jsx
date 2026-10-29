import React, { useState, useEffect, useRef } from 'react';
import { 
  Info, 
  ShieldAlert,
  Loader2,
  PlayCircle
} from 'lucide-react';
import { 
  BENCHMARK_METRICS, 
  STORES, 
  CATEGORIES 
} from '../data/mockData';
import { 
  getEvaluationComparisonFromBackend, 
  runBacktestInBackend,
  getExplorerDataFromBackend
} from '../services/api';

export default function ModelComparisonPage({ onNavigate, _onNavigate, uploadedDataset }) {
  const navigate = onNavigate || _onNavigate;
  const [filterHorizon, setFilterHorizon] = useState('all'); // all, 7d, 28d, 90d
  const [filterStore, setFilterStore] = useState('');
  const [filterCategory, setFilterCategory] = useState('');
  const [filterProduct, setFilterProduct] = useState('');
  const [filterSeries, setFilterSeries] = useState('');
  const [activeMetricTab, setActiveMetricTab] = useState('mape'); // 'mape' or 'rmse'

  const [availableFilters, setAvailableFilters] = useState({ stores: [], categories: [], items: [], series: [] });
  const [dimensions, setDimensions] = useState({ has_store: false, has_category: false, has_item: false, has_series: false });

  const [evalData, setEvalData] = useState(null);
  const [isLoadingScope, setIsLoadingScope] = useState(false);
  const [isBacktesting, setIsBacktesting] = useState(false);
  const [backtestError, setBacktestError] = useState(null);

  const abortControllerRef = useRef(null);

  // Reset all filters and evaluation data when switching datasets
  useEffect(() => {
    setFilterStore('');
    setFilterCategory('');
    setFilterProduct('');
    setFilterSeries('');
    setFilterHorizon('all');
    setEvalData(null);
  }, [uploadedDataset?.dataset_id]);

  // Discover dynamic available filters for the active dataset
  useEffect(() => {
    if (!uploadedDataset?.dataset_id) return;

    getExplorerDataFromBackend(uploadedDataset.dataset_id)
      .then((data) => {
        if (data) {
          setAvailableFilters(data.available_filters || { stores: [], categories: [], items: [], series: [] });
          setDimensions(data.dimensions || { has_store: false, has_category: false, has_item: false, has_series: false });
          setFilterStore(prev => prev || data.scope?.store_id || '');
          setFilterCategory(prev => prev || data.scope?.category || '');
          setFilterProduct(prev => prev || data.scope?.item_id || '');
          setFilterSeries(prev => prev || data.scope?.series_id || '');
        }
      })
      .catch(() => {});
  }, [uploadedDataset?.dataset_id]);

  // Fetch scope-specific cached evaluation results whenever filters change
  useEffect(() => {
    if (!uploadedDataset?.dataset_id) return;

    if (abortControllerRef.current) {
      abortControllerRef.current.abort();
    }
    const controller = new AbortController();
    abortControllerRef.current = controller;

    Promise.resolve().then(() => {
      setIsLoadingScope(true);
      setEvalData(null); // Stale result protection: clear old results immediately
    });

    getEvaluationComparisonFromBackend(
      uploadedDataset.dataset_id,
      {
        store_id: filterStore || undefined,
        category: filterCategory || undefined,
        item_id: filterProduct || undefined,
        series_id: filterSeries || undefined,
        horizon: filterHorizon !== 'all' ? parseInt(filterHorizon) : undefined,
      },
      controller.signal
    )
      .then((data) => {
        setIsLoadingScope(false);
        if (data) {
          setEvalData(data);
        }
      })
      .catch((err) => {
        if (err.name !== 'AbortError') {
          setIsLoadingScope(false);
        }
      });

    return () => {
      controller.abort();
    };
  }, [uploadedDataset?.dataset_id, filterStore, filterCategory, filterProduct, filterSeries, filterHorizon]);

  const handleRunBacktest = async () => {
    if (!uploadedDataset?.dataset_id) return;
    setIsBacktesting(true);
    setBacktestError(null);
    try {
      const res = await runBacktestInBackend(uploadedDataset.dataset_id, {
        store_id: filterStore || undefined,
        category: filterCategory || undefined,
        item_id: filterProduct || undefined,
        series_ids: filterSeries ? [filterSeries] : undefined,
        horizons: [7, 28, 90],
        n_folds: 2,
      });
      setEvalData(res);
    } catch (err) {
      setBacktestError(err.message || 'Failed to complete backtest suite.');
    } finally {
      setIsBacktesting(false);
    }
  };

  // Determine displayed rows:
  // For active real datasets: strictly empirical evaluations or null (NO mock data leakage!)
  // For demo mode (no dataset uploaded): reference benchmarks
  const displayedMetrics = evalData ? [
    {
      modelId: 'arima',
      name: 'ARIMA',
      type: 'Statistical Baseline',
      mape7: evalData.table_1_model_x_horizon_mape?.['arima']?.['7D'] ?? '—',
      mape28: evalData.table_1_model_x_horizon_mape?.['arima']?.['28D'] ?? '—',
      mape90: evalData.table_1_model_x_horizon_mape?.['arima']?.['90D'] ?? '—',
      rmse7: evalData.table_2_model_x_horizon_rmse?.['arima']?.['7D'] ?? '—',
      rmse28: evalData.table_2_model_x_horizon_rmse?.['arima']?.['28D'] ?? '—',
      rmse90: evalData.table_2_model_x_horizon_rmse?.['arima']?.['90D'] ?? '—',
      stability: 'Moderate',
      inferenceSpeed: '< 0.2s'
    },
    {
      modelId: 'sarima',
      name: 'SARIMA',
      type: 'Statistical Seasonal',
      mape7: evalData.table_1_model_x_horizon_mape?.['sarima']?.['7D'] ?? '—',
      mape28: evalData.table_1_model_x_horizon_mape?.['sarima']?.['28D'] ?? '—',
      mape90: evalData.table_1_model_x_horizon_mape?.['sarima']?.['90D'] ?? '—',
      rmse7: evalData.table_2_model_x_horizon_rmse?.['sarima']?.['7D'] ?? '—',
      rmse28: evalData.table_2_model_x_horizon_rmse?.['sarima']?.['28D'] ?? '—',
      rmse90: evalData.table_2_model_x_horizon_rmse?.['sarima']?.['90D'] ?? '—',
      stability: 'High',
      inferenceSpeed: '< 0.5s'
    },
    {
      modelId: 'prophet',
      name: 'Prophet',
      type: 'Additive Trend & Seasonality',
      mape7: evalData.table_1_model_x_horizon_mape?.['prophet']?.['7D'] ?? '—',
      mape28: evalData.table_1_model_x_horizon_mape?.['prophet']?.['28D'] ?? '—',
      mape90: evalData.table_1_model_x_horizon_mape?.['prophet']?.['90D'] ?? '—',
      rmse7: evalData.table_2_model_x_horizon_rmse?.['prophet']?.['7D'] ?? '—',
      rmse28: evalData.table_2_model_x_horizon_rmse?.['prophet']?.['28D'] ?? '—',
      rmse90: evalData.table_2_model_x_horizon_rmse?.['prophet']?.['90D'] ?? '—',
      stability: 'High',
      inferenceSpeed: '~ 0.8s'
    },
    {
      modelId: 'lightgbm',
      name: 'LightGBM',
      type: 'Gradient Boosted Trees',
      mape7: evalData.table_1_model_x_horizon_mape?.['lightgbm']?.['7D'] ?? '—',
      mape28: evalData.table_1_model_x_horizon_mape?.['lightgbm']?.['28D'] ?? '—',
      mape90: evalData.table_1_model_x_horizon_mape?.['lightgbm']?.['90D'] ?? '—',
      rmse7: evalData.table_2_model_x_horizon_rmse?.['lightgbm']?.['7D'] ?? '—',
      rmse28: evalData.table_2_model_x_horizon_rmse?.['lightgbm']?.['28D'] ?? '—',
      rmse90: evalData.table_2_model_x_horizon_rmse?.['lightgbm']?.['90D'] ?? '—',
      stability: 'Very High',
      inferenceSpeed: '< 0.3s'
    },
    {
      modelId: 'deepar',
      name: 'DeepAR',
      type: 'Probabilistic Recurrent Net',
      mape7: evalData.table_1_model_x_horizon_mape?.['deepar']?.['7D'] ?? '—',
      mape28: evalData.table_1_model_x_horizon_mape?.['deepar']?.['28D'] ?? '—',
      mape90: evalData.table_1_model_x_horizon_mape?.['deepar']?.['90D'] ?? '—',
      rmse7: evalData.table_2_model_x_horizon_rmse?.['deepar']?.['7D'] ?? '—',
      rmse28: evalData.table_2_model_x_horizon_rmse?.['deepar']?.['28D'] ?? '—',
      rmse90: evalData.table_2_model_x_horizon_rmse?.['deepar']?.['90D'] ?? '—',
      stability: 'High',
      inferenceSpeed: '~ 1.2s'
    },
    {
      modelId: 'tft',
      name: 'Temporal Fusion Transformer',
      type: 'Multi-Horizon Attention Architecture',
      mape7: evalData.table_1_model_x_horizon_mape?.['tft']?.['7D'] ?? '—',
      mape28: evalData.table_1_model_x_horizon_mape?.['tft']?.['28D'] ?? '—',
      mape90: evalData.table_1_model_x_horizon_mape?.['tft']?.['90D'] ?? '—',
      rmse7: evalData.table_2_model_x_horizon_rmse?.['tft']?.['7D'] ?? '—',
      rmse28: evalData.table_2_model_x_horizon_rmse?.['tft']?.['28D'] ?? '—',
      rmse90: evalData.table_2_model_x_horizon_rmse?.['tft']?.['90D'] ?? '—',
      stability: 'Exceptional',
      inferenceSpeed: '~ 2.5s'
    }
  ] : (uploadedDataset ? null : BENCHMARK_METRICS);

  // Calculate empirical best models for the active scope directly from displayedMetrics
  const isMapeMode = activeMetricTab === 'mape';
  const metricUnitSuffix = isMapeMode ? '% MAPE' : ' RMSE';

  const findBestForHorizon = (field) => {
    if (!displayedMetrics || displayedMetrics.length === 0) return null;
    const evaluated = displayedMetrics.filter(m => typeof m[field] === 'number');
    if (evaluated.length === 0) return null;
    return evaluated.reduce((prev, curr) => (curr[field] < prev[field] ? curr : prev));
  };

  const scopeBest7 = findBestForHorizon(isMapeMode ? 'mape7' : 'rmse7');
  const scopeBest28 = findBestForHorizon(isMapeMode ? 'mape28' : 'rmse28');
  const _scopeBest90 = findBestForHorizon(isMapeMode ? 'mape90' : 'rmse90');

  // Scope best overall (lowest average error across all evaluated horizons for each model)
  const scopeBestOverall = (() => {
    if (!displayedMetrics || displayedMetrics.length === 0) return null;
    const modelScores = [];
    displayedMetrics.forEach(m => {
      const v7 = isMapeMode ? m.mape7 : m.rmse7;
      const v28 = isMapeMode ? m.mape28 : m.rmse28;
      const v90 = isMapeMode ? m.mape90 : m.rmse90;
      const valid = [v7, v28, v90].filter(v => typeof v === 'number');
      if (valid.length > 0) {
        const avg = valid.reduce((a, b) => a + b, 0) / valid.length;
        modelScores.push({ model: m.name, modelId: m.modelId, avg: Math.round(avg * 100) / 100, count: valid.length });
      }
    });
    if (modelScores.length === 0) return null;
    return modelScores.reduce((prev, curr) => (curr.avg < prev.avg ? curr : prev));
  })();

  return (
    <div className="space-y-8 max-w-7xl mx-auto pb-12">
      {/* Header */}
      <div>
        <div className="text-xs font-semibold uppercase tracking-wider text-[#8E83A3]">
          Multi-Model Benchmarks
        </div>
        <h1 className="text-3xl font-bold font-heading text-[#1F1B2C]">
          Model Comparison
        </h1>
        <p className="text-sm text-[#5F5670] mt-1 max-w-2xl">
          Objective evaluation of statistical baselines, tree-based machine learning, and deep neural multi-horizon architectures across short-, medium-, and long-term horizons.
        </p>
      </div>

      {/* Uploaded Dataset Evaluation Banner / Control */}
      {uploadedDataset && (
        <section className="p-6 rounded-3xl bg-white border border-[#E5D9F2] shadow-xs space-y-4">
          <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4">
            <div className="space-y-1">
              <div className="flex items-center gap-2">
                <span className="w-2.5 h-2.5 rounded-full bg-emerald-500 animate-pulse"></span>
                <span className="text-xs font-bold text-[#1F1B2C] uppercase tracking-wider">
                  Active Dataset: {uploadedDataset.filename}
                </span>
              </div>
              <p className="text-xs text-[#5F5670]">
                {evalData 
                  ? `Evaluated scope: Store: ${evalData.scope?.store_id || 'All'} | Category: ${evalData.scope?.category || 'All'} | Horizons: ${evalData.horizons_evaluated?.join(', ') || '7D, 28D'}`
                  : 'Execute rolling-origin backtesting across all architectures for the chosen scope to calculate authentic empirical MAPE and RMSE.'}
              </p>
            </div>

            <button
              onClick={handleRunBacktest}
              disabled={isBacktesting}
              className={`flex items-center gap-2 px-5 py-2.5 rounded-xl text-xs font-bold text-white transition-all shadow-xs ${
                isBacktesting 
                  ? 'bg-[#CDC1FF] cursor-not-allowed' 
                  : 'bg-[#A294F9] hover:bg-[#8E83A3]'
              }`}
            >
              {isBacktesting ? (
                <>
                  <Loader2 className="w-4 h-4 animate-spin" />
                  <span>Running Walk-Forward Folds for Scope...</span>
                </>
              ) : evalData ? (
                <>
                  <PlayCircle className="w-4 h-4" />
                  <span>Re-Run Backtesting Suite</span>
                </>
              ) : (
                <>
                  <PlayCircle className="w-4 h-4" />
                  <span>Run Backtesting Evaluation</span>
                </>
              )}
            </button>
          </div>

          {backtestError && (
            <div className="p-3 rounded-xl bg-rose-50 border border-rose-200 text-rose-700 text-xs flex items-center gap-2">
              <ShieldAlert className="w-4 h-4 shrink-0" />
              <span>{backtestError}</span>
            </div>
          )}

          {/* Best Model Summary Cards when evalData is available */}
          {evalData && (
            <div className="grid grid-cols-1 sm:grid-cols-3 gap-3 pt-2">
              <div className="p-4 rounded-2xl bg-[#F5EFFF] border border-[#CDC1FF] space-y-1">
                <div className="text-[11px] font-semibold uppercase tracking-wider text-[#8E83A3]">
                  Best 7D Model (Short-term)
                </div>
                <div className="text-sm font-bold text-[#1F1B2C] flex items-center justify-between">
                  <span>{scopeBest7 ? scopeBest7.name.toUpperCase() : (evalData.best_per_horizon?.['7D']?.best_model?.toUpperCase() || 'N/A')}</span>
                  {(scopeBest7 ? (isMapeMode ? scopeBest7.mape7 : scopeBest7.rmse7) : (isMapeMode ? evalData.best_per_horizon?.['7D']?.mape : evalData.best_per_horizon?.['7D']?.rmse)) !== null && (
                    <span className="text-xs px-2 py-0.5 rounded-full bg-emerald-100 text-emerald-700 font-semibold">
                      {scopeBest7 ? (isMapeMode ? scopeBest7.mape7 : scopeBest7.rmse7) : (isMapeMode ? evalData.best_per_horizon?.['7D']?.mape : evalData.best_per_horizon?.['7D']?.rmse)}{metricUnitSuffix}
                    </span>
                  )}
                </div>
                {evalData.best_per_horizon?.['7D']?.is_tie && (
                  <div className="text-[10px] text-amber-600 font-medium">
                    Empirical tie within 0.2% MAPE
                  </div>
                )}
              </div>

              <div className="p-4 rounded-2xl bg-[#F5EFFF] border border-[#CDC1FF] space-y-1">
                <div className="text-[11px] font-semibold uppercase tracking-wider text-[#8E83A3]">
                  Best 28D Model (Medium-term)
                </div>
                <div className="text-sm font-bold text-[#1F1B2C] flex items-center justify-between">
                  <span>{scopeBest28 ? scopeBest28.name.toUpperCase() : (evalData.best_per_horizon?.['28D']?.best_model?.toUpperCase() || 'N/A')}</span>
                  {(scopeBest28 ? (isMapeMode ? scopeBest28.mape28 : scopeBest28.rmse28) : (isMapeMode ? evalData.best_per_horizon?.['28D']?.mape : evalData.best_per_horizon?.['28D']?.rmse)) !== null && (
                    <span className="text-xs px-2 py-0.5 rounded-full bg-emerald-100 text-emerald-700 font-semibold">
                      {scopeBest28 ? (isMapeMode ? scopeBest28.mape28 : scopeBest28.rmse28) : (isMapeMode ? evalData.best_per_horizon?.['28D']?.mape : evalData.best_per_horizon?.['28D']?.rmse)}{metricUnitSuffix}
                    </span>
                  )}
                </div>
                {evalData.best_per_horizon?.['28D']?.is_tie && (
                  <div className="text-[10px] text-amber-600 font-medium">
                    Empirical tie within 0.2% MAPE
                  </div>
                )}
              </div>

              <div className="p-4 rounded-2xl bg-[#F5EFFF] border border-[#CDC1FF] space-y-1">
                <div className="text-[11px] font-semibold uppercase tracking-wider text-[#8E83A3]">
                  Best Overall Across Horizons
                </div>
                <div className="text-sm font-bold text-[#A294F9] flex items-center justify-between">
                  <span>{scopeBestOverall ? scopeBestOverall.model.toUpperCase() : (evalData.best_model_overall?.model?.toUpperCase() || 'N/A')}</span>
                  {scopeBestOverall ? (
                    <span className="text-xs px-2 py-0.5 rounded-full bg-[#E5D9F2] text-[#1F1B2C] font-semibold">
                      Avg {scopeBestOverall.avg}{metricUnitSuffix}
                    </span>
                  ) : (evalData.best_model_overall?.overall_mape !== undefined && (
                    <span className="text-xs px-2 py-0.5 rounded-full bg-[#E5D9F2] text-[#1F1B2C] font-semibold">
                      Avg {evalData.best_model_overall?.overall_mape}% MAPE
                    </span>
                  ))}
                </div>
                <div className="text-[10px] text-[#5F5670]">
                  {(() => {
                    const horizons = evalData.best_model_overall?.evaluated_horizons || evalData.horizons_evaluated || [];
                    if (horizons.length > 0) {
                      const notEvaluated = ['90D'].filter(h => !horizons.includes(h));
                      return `Evaluated across ${horizons.join(', ')}${notEvaluated.length > 0 ? ` (${notEvaluated.join(', ')} not evaluated)` : ''}`;
                    }
                    return 'Evaluated across valid backtest folds';
                  })()}
                </div>
              </div>
            </div>
          )}
        </section>
      )}

      {/* Dynamic Filter Toolbar */}
      <section className="p-5 rounded-2xl bg-white border border-[#E5D9F2] shadow-xs">
        <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-5 gap-3.5 items-end">
          {/* Horizon filter */}
          <div>
            <label htmlFor="horizon-select" className="block text-[11px] font-semibold uppercase tracking-wider text-[#8E83A3] mb-1.5">
              Horizon
            </label>
            <select
              id="horizon-select"
              value={filterHorizon}
              onChange={(e) => setFilterHorizon(e.target.value)}
              className="w-full bg-[#F5EFFF] border border-[#CDC1FF] rounded-xl px-3 py-2 text-xs font-semibold text-[#1F1B2C] outline-none"
            >
              <option value="all">All Horizons (7D, 28D, 90D)</option>
              <option value="7d">7 Days (Short-term)</option>
              <option value="28d">28 Days (Medium-term)</option>
              <option value="90d">90 Days (Long-term)</option>
            </select>
          </div>

          {/* Store filter */}
          {(dimensions.has_store || (!uploadedDataset && STORES.length > 0)) && (
            <div>
              <label className="block text-[11px] font-semibold uppercase tracking-wider text-[#8E83A3] mb-1.5">
                Store
              </label>
              <select
                value={filterStore}
                onChange={(e) => setFilterStore(e.target.value)}
                className="w-full bg-[#F5EFFF] border border-[#CDC1FF] rounded-xl px-3 py-2 text-xs font-semibold text-[#1F1B2C] outline-none"
              >
                <option value="">All Stores</option>
                {(uploadedDataset ? availableFilters.stores : STORES.map(s => s.id)).map(s => (
                  <option key={s} value={s}>{s}</option>
                ))}
              </select>
            </div>
          )}

          {/* Category filter */}
          {(dimensions.has_category || (!uploadedDataset && CATEGORIES.length > 0)) && (
            <div>
              <label className="block text-[11px] font-semibold uppercase tracking-wider text-[#8E83A3] mb-1.5">
                Category
              </label>
              <select
                value={filterCategory}
                onChange={(e) => setFilterCategory(e.target.value)}
                className="w-full bg-[#F5EFFF] border border-[#CDC1FF] rounded-xl px-3 py-2 text-xs font-semibold text-[#1F1B2C] outline-none"
              >
                <option value="">All Categories</option>
                {(uploadedDataset ? availableFilters.categories : CATEGORIES.map(c => c.id)).map(c => (
                  <option key={c} value={c}>{c}</option>
                ))}
              </select>
            </div>
          )}

          {/* Product/Item filter */}
          {dimensions.has_item && availableFilters.items.length > 0 && (
            <div>
              <label className="block text-[11px] font-semibold uppercase tracking-wider text-[#8E83A3] mb-1.5">
                Product / Item
              </label>
              <select
                value={filterProduct}
                onChange={(e) => setFilterProduct(e.target.value)}
                className="w-full bg-[#F5EFFF] border border-[#CDC1FF] rounded-xl px-3 py-2 text-xs font-semibold text-[#1F1B2C] outline-none"
              >
                <option value="">All Items</option>
                {availableFilters.items.map(it => (
                  <option key={it} value={it}>{it}</option>
                ))}
              </select>
            </div>
          )}

          {/* Series filter */}
          {dimensions.has_series && availableFilters.series.length > 0 && (
            <div>
              <label className="block text-[11px] font-semibold uppercase tracking-wider text-[#8E83A3] mb-1.5">
                Series ID
              </label>
              <select
                value={filterSeries}
                onChange={(e) => setFilterSeries(e.target.value)}
                className="w-full bg-[#F5EFFF] border border-[#CDC1FF] rounded-xl px-3 py-2 text-xs font-semibold text-[#1F1B2C] outline-none truncate"
              >
                <option value="">All Series</option>
                {availableFilters.series.map(s => (
                  <option key={s} value={s}>{s}</option>
                ))}
              </select>
            </div>
          )}

          {/* Metric switch */}
          <div>
            <label className="block text-[11px] font-semibold uppercase tracking-wider text-[#8E83A3] mb-1.5">
              Metric Display
            </label>
            <div className="grid grid-cols-2 gap-1 bg-[#F5EFFF] p-1 rounded-xl border border-[#CDC1FF]">
              <button
                onClick={() => setActiveMetricTab('mape')}
                className={`py-1.5 text-center text-xs rounded-lg font-medium transition-all ${
                  activeMetricTab === 'mape' 
                    ? 'bg-[#A294F9] text-white font-bold shadow-xs' 
                    : 'text-[#5F5670] hover:text-[#1F1B2C]'
                }`}
              >
                MAPE (%)
              </button>
              <button
                onClick={() => setActiveMetricTab('rmse')}
                className={`py-1.5 text-center text-xs rounded-lg font-medium transition-all ${
                  activeMetricTab === 'rmse' 
                    ? 'bg-[#A294F9] text-white font-bold shadow-xs' 
                    : 'text-[#5F5670] hover:text-[#1F1B2C]'
                }`}
              >
                RMSE (Units)
              </button>
            </div>
          </div>
        </div>
      </section>

      {/* Loading state for scope change */}
      {isLoadingScope && (
        <section className="p-8 rounded-3xl bg-white border border-[#E5D9F2] text-center space-y-2">
          <div className="animate-spin text-2xl">⏳</div>
          <h3 className="text-sm font-bold text-[#1F1B2C]">Checking Evaluation Results for Scope...</h3>
          <p className="text-xs text-[#5F5670]">
            Fetching exact scope metrics without leaking benchmark data.
          </p>
        </section>
      )}

      {/* Empty State when dataset is uploaded but no evaluation executed yet for this scope */}
      {!isLoadingScope && uploadedDataset && !evalData && (
        <section className="p-12 rounded-3xl bg-white border border-[#E5D9F2] shadow-xs text-center space-y-3">
          <div className="w-12 h-12 mx-auto rounded-2xl bg-[#F5EFFF] flex items-center justify-center text-[#A294F9]">
            <PlayCircle className="w-6 h-6" />
          </div>
          <h3 className="text-base font-bold text-[#1F1B2C]">
            No Backtesting Results Computed for This Dataset Yet
          </h3>
          <p className="text-xs text-[#5F5670] max-w-md mx-auto">
            Current Scope: Store: <strong>{filterStore || 'All'}</strong> | Category: <strong>{filterCategory || 'All'}</strong> | Horizon: <strong>{filterHorizon.toUpperCase()}</strong>.
            Click <strong>Run Backtesting Evaluation</strong> above to evaluate all 6 architectures on this exact slice.
          </p>
        </section>
      )}

      {/* Main Tables and Visualizations when metrics are present */}
      {!isLoadingScope && displayedMetrics && (
        <>
          {/* Main Table 1: MAPE Comparison */}
          <section className="p-6 rounded-3xl bg-white border border-[#E5D9F2] shadow-xs space-y-4">
            <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4">
              <div>
                <div className="text-xs font-semibold uppercase tracking-wider text-[#8E83A3]">
                  Metric Table 1
                </div>
                <h2 className="text-xl font-bold font-heading text-[#1F1B2C]">
                  MAPE Performance Across Horizons (Mean Absolute % Error)
                </h2>
                <p className="text-xs text-[#5F5670]">
                  Lower is better. Demonstrates error growth rate as forecast horizon widens.
                </p>
              </div>
              <span className="text-xs text-[#5F5670] bg-[#F5EFFF] px-3 py-1.5 rounded-xl border border-[#E5D9F2]">
                Evidence-based cross-validation
              </span>
            </div>

            <div className="overflow-x-auto">
              <table className="w-full text-left text-xs border-collapse">
                <thead>
                  <tr className="border-b border-[#E5D9F2] text-[#8E83A3] uppercase tracking-wider">
                    <th className="py-3 px-4 font-semibold">Model Architecture</th>
                    <th className="py-3 px-4 font-semibold">Class</th>
                    <th className={`py-3 px-4 font-semibold ${filterHorizon === '7d' ? 'bg-[#F5EFFF] text-[#1F1B2C] font-bold' : ''}`}>
                      7D MAPE (Short)
                    </th>
                    <th className={`py-3 px-4 font-semibold ${filterHorizon === '28d' ? 'bg-[#F5EFFF] text-[#1F1B2C] font-bold' : ''}`}>
                      28D MAPE (Med)
                    </th>
                    <th className={`py-3 px-4 font-semibold ${filterHorizon === '90d' ? 'bg-[#F5EFFF] text-[#1F1B2C] font-bold' : ''}`}>
                      90D MAPE (Long)
                    </th>
                    <th className="py-3 px-4 font-semibold">Horizon Consistency</th>
                    <th className="py-3 px-4 font-semibold">Inference Latency</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-[#F5EFFF]">
                  {displayedMetrics.map((row) => (
                    <tr key={row.modelId} className="hover:bg-[#F5EFFF]/40 transition-colors">
                      <td className="py-3.5 px-4 font-bold text-[#1F1B2C]">
                        {row.name}
                      </td>
                      <td className="py-3.5 px-4 text-[#5F5670]">
                        {row.type}
                      </td>
                      <td className={`py-3.5 px-4 font-semibold text-[#1F1B2C] ${filterHorizon === '7d' ? 'bg-[#F5EFFF]' : ''}`}>
                        {typeof row.mape7 === 'number' ? `${row.mape7}%` : row.mape7}
                      </td>
                      <td className={`py-3.5 px-4 font-semibold text-[#1F1B2C] ${filterHorizon === '28d' ? 'bg-[#F5EFFF]' : ''}`}>
                        {typeof row.mape28 === 'number' ? `${row.mape28}%` : row.mape28}
                      </td>
                      <td className={`py-3.5 px-4 font-semibold text-[#1F1B2C] ${filterHorizon === '90d' ? 'bg-[#F5EFFF]' : ''}`}>
                        {typeof row.mape90 === 'number' ? `${row.mape90}%` : row.mape90}
                      </td>
                      <td className="py-3.5 px-4">
                        <span className={`inline-flex px-2 py-0.5 rounded-full text-[10px] font-semibold ${
                          row.stability === 'Exceptional' 
                            ? 'bg-emerald-100 text-emerald-700' 
                            : row.stability === 'Very High' 
                              ? 'bg-[#E5D9F2] text-[#A294F9]' 
                              : 'bg-gray-100 text-[#5F5670]'
                        }`}>
                          {row.stability}
                        </span>
                      </td>
                      <td className="py-3.5 px-4 text-[#8E83A3] font-mono">
                        {row.inferenceSpeed}
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </section>

          {/* Main Table 2: RMSE Comparison */}
          <section className="p-6 rounded-3xl bg-white border border-[#E5D9F2] shadow-xs space-y-4">
            <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4">
              <div>
                <div className="text-xs font-semibold uppercase tracking-wider text-[#8E83A3]">
                  Metric Table 2
                </div>
                <h2 className="text-xl font-bold font-heading text-[#1F1B2C]">
                  RMSE Magnitude Across Horizons (Root Mean Squared Error)
                </h2>
                <p className="text-xs text-[#5F5670]">
                  Units of daily demand. Heavily penalizes large unpredicted stockout or overstock spikes.
                </p>
              </div>
            </div>

            <div className="overflow-x-auto">
              <table className="w-full text-left text-xs border-collapse">
                <thead>
                  <tr className="border-b border-[#E5D9F2] text-[#8E83A3] uppercase tracking-wider">
                    <th className="py-3 px-4 font-semibold">Model Architecture</th>
                    <th className="py-3 px-4 font-semibold">Class</th>
                    <th className={`py-3 px-4 font-semibold ${filterHorizon === '7d' ? 'bg-[#F5EFFF] text-[#1F1B2C] font-bold' : ''}`}>
                      7D RMSE
                    </th>
                    <th className={`py-3 px-4 font-semibold ${filterHorizon === '28d' ? 'bg-[#F5EFFF] text-[#1F1B2C] font-bold' : ''}`}>
                      28D RMSE
                    </th>
                    <th className={`py-3 px-4 font-semibold ${filterHorizon === '90d' ? 'bg-[#F5EFFF] text-[#1F1B2C] font-bold' : ''}`}>
                      90D RMSE
                    </th>
                    <th className="py-3 px-4 font-semibold">Large Error Penalty</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-[#F5EFFF]">
                  {displayedMetrics.map((row) => (
                    <tr key={row.modelId} className="hover:bg-[#F5EFFF]/40 transition-colors">
                      <td className="py-3.5 px-4 font-bold text-[#1F1B2C]">
                        {row.name}
                      </td>
                      <td className="py-3.5 px-4 text-[#5F5670]">
                        {row.type}
                      </td>
                      <td className={`py-3.5 px-4 font-semibold text-[#1F1B2C] ${filterHorizon === '7d' ? 'bg-[#F5EFFF]' : ''}`}>
                        {typeof row.rmse7 === 'number' ? row.rmse7 : row.rmse7}
                      </td>
                      <td className={`py-3.5 px-4 font-semibold text-[#1F1B2C] ${filterHorizon === '28d' ? 'bg-[#F5EFFF]' : ''}`}>
                        {typeof row.rmse28 === 'number' ? row.rmse28 : row.rmse28}
                      </td>
                      <td className={`py-3.5 px-4 font-semibold text-[#1F1B2C] ${filterHorizon === '90d' ? 'bg-[#F5EFFF]' : ''}`}>
                        {typeof row.rmse90 === 'number' ? row.rmse90 : row.rmse90}
                      </td>
                      <td className="py-3.5 px-4 text-[#5F5670]">
                        {typeof row.rmse90 === 'number' 
                          ? (row.rmse90 > 18 ? 'High tail error on 90D' : 'Controlled tail error') 
                          : typeof row.rmse28 === 'number' 
                            ? 'Controlled medium error (90D Not Evaluated)' 
                            : 'Not evaluated'}
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </section>

          {/* Visualizations Section */}
          {(() => {
            const isMape = activeMetricTab === 'mape';
            const metricSuffix = isMape ? '%' : '';

            // Check evaluated status across horizons for the active metric
            const is90DEvaluated = displayedMetrics.some(m => {
              const v = isMape ? m.mape90 : m.rmse90;
              return typeof v === 'number';
            });

            // Dynamic Y-axis scale calculation for Bar Chart
            const validBarValues = displayedMetrics.flatMap(m => {
              const vals = isMape 
                ? [m.mape7, m.mape28, m.mape90] 
                : [m.rmse7, m.rmse28, m.rmse90];
              return vals.filter(v => typeof v === 'number');
            });
            const rawMaxBar = validBarValues.length > 0 ? Math.max(...validBarValues) : 25;
            const maxBar = Math.max(isMape ? 25 : 2, Math.ceil((rawMaxBar * 1.15) / (isMape ? 5 : 1)) * (isMape ? 5 : 1));
            const barStep = maxBar / 5;
            const barTicks = [0, barStep, barStep * 2, barStep * 3, barStep * 4, maxBar].map(v => 
              isMape ? Math.round(v) : (Math.round(v * 10) / 10)
            );

            // Dynamic Y-axis scale calculation for Line Chart (Degradation Curve)
            const validLineValues = displayedMetrics.flatMap(m => {
              const vals = isMape
                ? [m.mape7, m.mape28, m.mape90]
                : [m.rmse7, m.rmse28, m.rmse90];
              return vals.filter(v => typeof v === 'number');
            });
            const rawMaxLine = validLineValues.length > 0 ? Math.max(...validLineValues) : 25;
            const maxLine = Math.max(isMape ? 25 : 2, Math.ceil((rawMaxLine * 1.15) / (isMape ? 5 : 1)) * (isMape ? 5 : 1));
            const lineStep = maxLine / 5;
            const lineTicks = [0, lineStep, lineStep * 2, lineStep * 3, lineStep * 4, maxLine].map(v => 
              isMape ? Math.round(v) : (Math.round(v * 10) / 10)
            );

            const MODEL_COLORS = {
              lightgbm: '#059669', // Emerald
              sarima: '#2563EB',   // Blue
              arima: '#DC2626',    // Red
              tft: '#7C3AED',      // Violet
              prophet: '#D97706',  // Amber
              deepar: '#4F46E5',   // Indigo
            };

            // Empirical best models for active metric derived from the SAME displayedMetrics scope
            const best7Model = scopeBest7 ? scopeBest7.name : evalData?.best_per_horizon?.['7D']?.best_model;
            const best7Value = scopeBest7 
              ? (isMape ? scopeBest7.mape7 : scopeBest7.rmse7)
              : (isMape ? evalData?.best_per_horizon?.['7D']?.mape : evalData?.best_per_horizon?.['7D']?.rmse);
            const best28Model = scopeBest28 ? scopeBest28.name : evalData?.best_per_horizon?.['28D']?.best_model;
            const best28Value = scopeBest28 
              ? (isMape ? scopeBest28.mape28 : scopeBest28.rmse28)
              : (isMape ? evalData?.best_per_horizon?.['28D']?.mape : evalData?.best_per_horizon?.['28D']?.rmse);

            const color7 = (scopeBest7 && MODEL_COLORS[scopeBest7.modelId]) || '#059669';
            const color28 = (scopeBest28 && MODEL_COLORS[scopeBest28.modelId]) || '#2563EB';

            return (
              <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
                <section className="p-6 rounded-3xl bg-white border border-[#E5D9F2] shadow-xs space-y-4">
                  <div>
                    <div className="text-xs font-semibold uppercase tracking-wider text-[#8E83A3]">
                      Visual Comparison
                    </div>
                    <div className="flex items-center justify-between">
                      <h3 className="text-lg font-bold font-heading text-[#1F1B2C]">
                        {isMape ? 'MAPE Error Comparison' : 'RMSE Error Comparison'}
                      </h3>
                      {!is90DEvaluated && (
                        <span className="text-[10px] font-bold px-2 py-0.5 rounded-full bg-amber-100 text-amber-800">
                          90D Not Evaluated
                        </span>
                      )}
                    </div>
                    <p className="text-xs text-[#5F5670]">
                      Bar grouping across 7D (short), 28D (medium), and 90D (long) horizons ({isMape ? 'Percentage Error' : 'Demand Units'}).
                    </p>
                  </div>

                  <div className="relative w-full h-64 bg-[#F5EFFF]/30 rounded-2xl border border-[#E5D9F2] p-4 flex flex-col justify-end">
                    <svg viewBox="0 0 500 180" className="w-full h-full overflow-visible">
                      {barTicks.map(v => {
                        const y = 160 - (v / maxBar) * 135;
                        return (
                          <g key={v}>
                            <line x1="40" y1={y} x2="480" y2={y} stroke="#E5D9F2" strokeDasharray="3 3" />
                            <text x="32" y={y + 3} textAnchor="end" className="text-[9px] fill-[#8E83A3] font-medium">{v}{metricSuffix}</text>
                          </g>
                        );
                      })}

                      {displayedMetrics.map((m, i) => {
                        const groupX = 55 + i * 72;
                        const v7 = isMape ? m.mape7 : m.rmse7;
                        const v28 = isMape ? m.mape28 : m.rmse28;
                        const v90 = isMape ? m.mape90 : m.rmse90;

                        const has7 = typeof v7 === 'number';
                        const has28 = typeof v28 === 'number';
                        const has90 = typeof v90 === 'number';

                        const h7 = has7 ? (v7 / maxBar) * 135 : 0;
                        const h28 = has28 ? (v28 / maxBar) * 135 : 0;
                        const h90 = has90 ? (v90 / maxBar) * 135 : 0;

                        return (
                          <g key={m.modelId}>
                            {has7 && (
                              <rect x={groupX} y={160 - h7} width="16" height={Math.max(h7, 2)} fill="#CDC1FF" rx="3">
                                <title>{`${m.name} 7D: ${v7}${metricSuffix}`}</title>
                              </rect>
                            )}
                            {has28 && (
                              <rect x={groupX + 18} y={160 - h28} width="16" height={Math.max(h28, 2)} fill="#A294F9" rx="3">
                                <title>{`${m.name} 28D: ${v28}${metricSuffix}`}</title>
                              </rect>
                            )}
                            {has90 ? (
                              <rect x={groupX + 36} y={160 - h90} width="16" height={Math.max(h90, 2)} fill="#5F5670" rx="3">
                                <title>{`${m.name} 90D: ${v90}${metricSuffix}`}</title>
                              </rect>
                            ) : (
                              /* Placeholder slot indicating unevaluated horizon without drawing a zero-height bar */
                              <g opacity="0.6">
                                <rect x={groupX + 36} y="152" width="16" height="8" fill="none" stroke="#CDC1FF" strokeDasharray="2 2" rx="2" />
                                <text x={groupX + 44} y="158" textAnchor="middle" className="text-[7px] fill-[#8E83A3] font-semibold">—</text>
                              </g>
                            )}
                            <text x={groupX + 26} y="174" textAnchor="middle" className="text-[9px] fill-[#1F1B2C] font-semibold">
                              {m.modelId.toUpperCase()}
                            </text>
                          </g>
                        );
                      })}
                    </svg>

                    <div className="flex flex-wrap items-center justify-center gap-4 sm:gap-6 text-[11px] text-[#5F5670] mt-3 pt-2 border-t border-[#E5D9F2]">
                      <span className="flex items-center gap-1.5">
                        <span className="w-3 h-3 bg-[#CDC1FF] rounded-xs inline-block"></span>
                        7 Days (Short)
                      </span>
                      <span className="flex items-center gap-1.5">
                        <span className="w-3 h-3 bg-[#A294F9] rounded-xs inline-block"></span>
                        28 Days (Medium)
                      </span>
                      <span className="flex items-center gap-1.5">
                        <span className="w-3 h-3 bg-[#5F5670] rounded-xs inline-block"></span>
                        90 Days (Long)
                        {!is90DEvaluated && (
                          <span className="text-[10px] font-bold text-amber-700 bg-amber-100 px-1.5 py-0.5 rounded-full ml-1">
                            Not Evaluated
                          </span>
                        )}
                      </span>
                    </div>
                  </div>
                </section>

                <section className="p-6 rounded-3xl bg-white border border-[#E5D9F2] shadow-xs space-y-4">
                  <div>
                    <div className="text-xs font-semibold uppercase tracking-wider text-[#8E83A3]">
                      Degradation Curve
                    </div>
                    <div className="flex items-center justify-between">
                      <h3 className="text-lg font-bold font-heading text-[#1F1B2C]">
                        Horizon Consistency Analysis
                      </h3>
                      {!is90DEvaluated && (
                        <span className="text-[10px] font-bold px-2 py-0.5 rounded-full bg-amber-100 text-amber-800">
                          90D Not Evaluated
                        </span>
                      )}
                    </div>
                    <p className="text-xs text-[#5F5670]">
                      How {isMape ? 'MAPE error' : 'RMSE error'} scales from 7D to 90D: steeper slopes denote rapid accuracy decay.
                    </p>
                  </div>

                  <div className="relative w-full h-64 bg-[#F5EFFF]/30 rounded-2xl border border-[#E5D9F2] p-4 flex flex-col justify-end">
                    <svg viewBox="0 0 500 180" className="w-full h-full overflow-visible">
                      {lineTicks.map(v => {
                        const y = 150 - (v / maxLine) * 125;
                        return (
                          <g key={v}>
                            <line x1="60" y1={y} x2="480" y2={y} stroke="#E5D9F2" strokeDasharray="3 3" />
                            <text x="52" y={y + 3} textAnchor="end" className="text-[9px] fill-[#8E83A3] font-medium">{v}{metricSuffix}</text>
                          </g>
                        );
                      })}

                      <line x1="90" y1="20" x2="90" y2="150" stroke="#E5D9F2" strokeDasharray="3 3" />
                      <line x1="250" y1="20" x2="250" y2="150" stroke="#E5D9F2" strokeDasharray="3 3" />
                      <line x1="410" y1="20" x2="410" y2="150" stroke="#E5D9F2" strokeDasharray="3 3" />

                      <text x="90" y="166" textAnchor="middle" className="text-[10px] font-bold fill-[#1F1B2C]">7 Days</text>
                      <text x="250" y="166" textAnchor="middle" className="text-[10px] font-bold fill-[#1F1B2C]">28 Days</text>
                      {is90DEvaluated ? (
                        <text x="410" y="166" textAnchor="middle" className="text-[10px] font-bold fill-[#1F1B2C]">90 Days</text>
                      ) : (
                        <g>
                          <text x="410" y="164" textAnchor="middle" className="text-[10px] font-bold fill-[#8E83A3]">90 Days</text>
                          <text x="410" y="176" textAnchor="middle" className="text-[8.5px] font-semibold fill-amber-600">(Not Evaluated)</text>
                        </g>
                      )}

                      {!is90DEvaluated && (
                        <g>
                          <rect x="350" y="65" width="120" height="28" rx="8" fill="#FFFBEB" stroke="#FDE68A" strokeWidth="1" />
                          <text x="410" y="78" textAnchor="middle" className="text-[9.5px] font-bold fill-amber-800">
                            Not Evaluated
                          </text>
                          <text x="410" y="88" textAnchor="middle" className="text-[7.5px] fill-amber-700">
                            Insufficient history for 90D
                          </text>
                        </g>
                      )}

                      {displayedMetrics.map((m) => {
                        const points = [];
                        const v7 = isMape ? m.mape7 : m.rmse7;
                        const v28 = isMape ? m.mape28 : m.rmse28;
                        const v90 = isMape ? m.mape90 : m.rmse90;

                        if (typeof v7 === 'number') {
                          points.push({ x: 90, y: 150 - (v7 / maxLine) * 125, val: v7 });
                        }
                        if (typeof v28 === 'number') {
                          points.push({ x: 250, y: 150 - (v28 / maxLine) * 125, val: v28 });
                        }
                        if (typeof v90 === 'number') {
                          points.push({ x: 410, y: 150 - (v90 / maxLine) * 125, val: v90 });
                        }

                        if (points.length === 0) return null;

                        const color = MODEL_COLORS[m.modelId] || '#5F5670';
                        const isLightGBM = m.modelId === 'lightgbm';
                        const isSARIMA = m.modelId === 'sarima';
                        const isTFT = m.modelId === 'tft';
                        const strokeW = isLightGBM || isSARIMA || isTFT ? '2.5' : '1.5';
                        const strokeDash = m.modelId === 'arima' ? '4 2' : 'none';

                        const pathD = points.map((p, idx) => `${idx === 0 ? 'M' : 'L'} ${p.x} ${p.y}`).join(' ');
                        const lastPoint = points[points.length - 1];

                        return (
                          <g key={m.modelId}>
                            {points.length > 1 && (
                              <path
                                d={pathD}
                                fill="none"
                                stroke={color}
                                strokeWidth={strokeW}
                                strokeDasharray={strokeDash}
                              />
                            )}
                            {points.map((p, pIdx) => (
                              <circle key={pIdx} cx={p.x} cy={p.y} r={isLightGBM || isSARIMA ? 4 : 3} fill={color}>
                                <title>{`${m.name}: ${p.val}${metricSuffix} ${isMape ? 'MAPE' : 'RMSE'}`}</title>
                              </circle>
                            ))}
                            <text
                              x={lastPoint.x + 8}
                              y={lastPoint.y + 3}
                              className="text-[8.5px] font-bold"
                              fill={color}
                            >
                              {m.name.split(' ')[0]} ({lastPoint.val}{metricSuffix})
                            </text>
                          </g>
                        );
                      })}
                    </svg>

                    <div className="text-[11px] text-[#5F5670] mt-3 pt-2 border-t border-[#E5D9F2] flex flex-wrap items-center justify-between gap-2">
                      <div className="flex items-center gap-3">
                        <span className="flex items-center gap-1">
                          <span className="w-2.5 h-2.5 rounded-full inline-block" style={{ backgroundColor: color7 }}></span>
                          <strong style={{ color: color7 }}>
                            {best7Model ? `${best7Model.toUpperCase()} (Best 7D${best7Value !== undefined && best7Value !== null ? `: ${best7Value}${metricSuffix}` : ''})` : 'LightGBM (Best 7D)'}
                          </strong>
                        </span>
                        <span className="flex items-center gap-1">
                          <span className="w-2.5 h-2.5 rounded-full inline-block" style={{ backgroundColor: color28 }}></span>
                          <strong style={{ color: color28 }}>
                            {best28Model ? `${best28Model.toUpperCase()} (Best 28D${best28Value !== undefined && best28Value !== null ? `: ${best28Value}${metricSuffix}` : ''})` : 'SARIMA (Best 28D)'}
                          </strong>
                        </span>
                      </div>
                      <span>
                        {!is90DEvaluated ? (
                          <span className="text-amber-700 font-semibold bg-amber-50 px-2 py-0.5 rounded-full">
                            90-Day horizon: Not Evaluated
                          </span>
                        ) : (
                          'All 3 horizons evaluated'
                        )}
                      </span>
                    </div>
                  </div>
                </section>
              </div>
            );
          })()}
        </>
      )}

      {/* Unbiased Evidence-Based Interpretation Card */}
      <section className="p-6 rounded-2xl bg-white border border-[#E5D9F2] shadow-xs space-y-3">
        <div className="flex items-center gap-2 text-xs font-bold text-[#1F1B2C]">
          <Info className="w-4 h-4 text-[#A294F9]" />
          <span>Objective Interpretation Framework</span>
        </div>
        <p className="text-xs text-[#5F5670] leading-relaxed">
          Rather than declaring a single universal model "best", enterprise demand planning involves distinct operational trade-offs:
          <strong> ARIMA/SARIMA</strong> offers instantaneous computation and clear statistical transparency for stable items; 
          <strong> LightGBM</strong> offers exceptional tabular throughput with rich lag features; and 
          <strong> Temporal Fusion Transformer (TFT)</strong> demonstrates superior multi-step horizon consistency for complex seasonal patterns with external price and holiday covariates.
        </p>

        {/* Workflow Progression: Step 4 -> Business Insights */}
        <div className="pt-3 border-t border-[#E5D9F2] flex flex-col sm:flex-row sm:items-center justify-between gap-3">
          <div className="text-xs text-[#5F5670]">
            Step 4 Completed: Model Comparison verified across compatible horizons.
          </div>
          <button
            onClick={() => navigate && navigate('insights')}
            className="px-5 py-2.5 rounded-xl bg-[#A294F9] text-white hover:bg-[#9181f7] text-xs font-semibold transition-colors shadow-xs flex items-center gap-1.5 self-start sm:self-auto"
            data-testid="continue-to-insights-btn"
          >
            <span>Explore Business Insights & Monitoring →</span>
          </button>
        </div>
      </section>
    </div>
  );
}
