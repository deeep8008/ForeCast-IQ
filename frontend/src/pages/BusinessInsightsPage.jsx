import React, { useState, useEffect, useRef } from 'react';
import { 
  Briefcase,
  Tag,
  Package, 
  Users, 
  TrendingUp, 
  Info, 
  ArrowRight, 
  Truck,
  Loader2,
  Sparkles,
  AlertCircle
} from 'lucide-react';
import { STORES, PRODUCTS } from '../data/mockData';
import { 
  getInsightsFromBackend, 
  generateInsightsInBackend, 
  getMonitoringFromBackend,
  getExplorerDataFromBackend
} from '../services/api';

export default function BusinessInsightsPage({ onNavigate, uploadedDataset }) {
  // Mock demo mode state
  const [activeStore, setActiveStore] = useState('CA_1');
  const [activeProduct, setActiveProduct] = useState('FOODS_3_090');

  // Real uploaded dataset dynamic filters and scope
  const [selectedStore, setSelectedStore] = useState('');
  const [selectedCategory, setSelectedCategory] = useState('');
  const [selectedItem, setSelectedItem] = useState('');
  const [selectedSeries, setSelectedSeries] = useState('');
  const [selectedModel, setSelectedModel] = useState('automatic');
  const [selectedHorizon, setSelectedHorizon] = useState(28);

  const [availableFilters, setAvailableFilters] = useState({ stores: [], categories: [], items: [], series: [] });
  const [dimensions, setDimensions] = useState({ has_store: false, has_category: false, has_item: false, has_series: false });

  const [insightsData, setInsightsData] = useState(null);
  const [monitoringData, setMonitoringData] = useState(null);
  const [isLoading, setIsLoading] = useState(false);
  const [errorMsg, setErrorMsg] = useState(null);

  const abortControllerRef = useRef(null);

  // Discover available filter options from the full dataset
  useEffect(() => {
    if (!uploadedDataset?.dataset_id) return;

    getExplorerDataFromBackend(uploadedDataset.dataset_id)
      .then((data) => {
        if (data) {
          setAvailableFilters(data.available_filters || { stores: [], categories: [], items: [], series: [] });
          setDimensions(data.dimensions || { has_store: false, has_category: false, has_item: false, has_series: false });
          setSelectedStore(prev => prev || data.scope?.store_id || '');
          setSelectedCategory(prev => prev || data.scope?.category || '');
          setSelectedItem(prev => prev || data.scope?.item_id || '');
          setSelectedSeries(prev => prev || data.scope?.series_id || '');
        }
      })
      .catch(() => {});
  }, [uploadedDataset?.dataset_id]);

  // Load cached insights and monitoring when dataset or scope selection changes
  useEffect(() => {
    if (!uploadedDataset?.dataset_id) return;

    // Abort previous in-flight request to prevent async race conditions
    if (abortControllerRef.current) {
      abortControllerRef.current.abort();
    }
    const controller = new AbortController();
    abortControllerRef.current = controller;

    // Reset old data to prevent stale asynchronous display while loading new scope
    Promise.resolve().then(() => {
      setInsightsData(null);
      setMonitoringData(null);
      setIsLoading(true);
      setErrorMsg(null);
    });

    // Fetch scope-specific monitoring status
    getMonitoringFromBackend(
      uploadedDataset.dataset_id,
      {
        series_id: selectedSeries || undefined,
        store_id: selectedStore || undefined,
        category: selectedCategory || undefined,
        item_id: selectedItem || undefined,
        model: selectedModel,
        horizon: selectedHorizon,
      },
      controller.signal
    )
      .then((m) => {
        if (m) {
          // Scope validation: ensure monitoring response matches current scope
          if (m.scope) {
            if (selectedStore && m.scope.store_id && String(m.scope.store_id) !== String(selectedStore)) return;
            if (selectedCategory && m.scope.category && String(m.scope.category) !== String(selectedCategory)) return;
            if (selectedItem && m.scope.item_id && String(m.scope.item_id) !== String(selectedItem)) return;
            if (selectedSeries && m.scope.series_id && String(m.scope.series_id) !== String(selectedSeries)) return;
            if (m.scope.horizon && m.scope.horizon !== selectedHorizon) return;
          }
          setMonitoringData(m);
        }
      })
      .catch((err) => {
        if (err.name !== 'AbortError') {
          // Keep null or unavailable
        }
      });

    getInsightsFromBackend(
      uploadedDataset.dataset_id,
      selectedSeries || null,
      {
        store_id: selectedStore || undefined,
        category: selectedCategory || undefined,
        item_id: selectedItem || undefined,
        model: selectedModel,
        horizon: selectedHorizon,
      },
      controller.signal
    )
      .then((data) => {
        setIsLoading(false);
        if (data) {
          // Scope validation: verify response scope matches currently active selection
          if (data.scope) {
            if (selectedStore && data.scope.store_id && String(data.scope.store_id) !== String(selectedStore)) return;
            if (selectedCategory && data.scope.category && String(data.scope.category) !== String(selectedCategory)) return;
            if (selectedItem && data.scope.item_id && String(data.scope.item_id) !== String(selectedItem)) return;
            if (selectedSeries && data.scope.series_id && String(data.scope.series_id) !== String(selectedSeries)) return;
            if (data.scope.horizon !== selectedHorizon) return;
          }
          setInsightsData(data);
        }
      })
      .catch((err) => {
        if (err.name !== 'AbortError') {
          setIsLoading(false);
        }
      });

    return () => {
      controller.abort();
    };
  }, [uploadedDataset?.dataset_id, selectedStore, selectedCategory, selectedItem, selectedSeries, selectedModel, selectedHorizon]);

  const handleGenerateInsights = async () => {
    if (!uploadedDataset?.dataset_id) return;

    if (abortControllerRef.current) {
      abortControllerRef.current.abort();
    }
    const controller = new AbortController();
    abortControllerRef.current = controller;

    setIsLoading(true);
    setErrorMsg(null);
    setInsightsData(null); // Clear stale results

    try {
      const res = await generateInsightsInBackend(
        uploadedDataset.dataset_id,
        selectedSeries || null,
        {
          store_id: selectedStore || undefined,
          category: selectedCategory || undefined,
          item_id: selectedItem || undefined,
          model: selectedModel,
          horizon: selectedHorizon,
        },
        controller.signal
      );

      // Verify scope match before rendering
      if (res && res.scope) {
        if (selectedStore && res.scope.store_id && String(res.scope.store_id) !== String(selectedStore)) {
          setErrorMsg('Received out-of-order response for previous store.');
          return;
        }
        if (selectedCategory && res.scope.category && String(res.scope.category) !== String(selectedCategory)) {
          setErrorMsg('Received out-of-order response for previous category.');
          return;
        }
        if (selectedSeries && res.scope.series_id && String(res.scope.series_id) !== String(selectedSeries)) {
          setErrorMsg('Received out-of-order response for previous series.');
          return;
        }
        if (res.scope.horizon !== selectedHorizon) {
          setErrorMsg('Received out-of-order response for previous horizon.');
          return;
        }
      }

      setInsightsData(res);
      // Refresh monitoring
      const m = await getMonitoringFromBackend(uploadedDataset.dataset_id);
      if (m) setMonitoringData(m);
    } catch (err) {
      if (err.name !== 'AbortError') {
        setErrorMsg(err.message || 'Failed to generate business insights.');
      }
    } finally {
      setIsLoading(false);
    }
  };

  const selectedProdObj = PRODUCTS.find((p) => p.id === activeProduct) || PRODUCTS[0];

  return (
    <div className="space-y-8 max-w-7xl mx-auto pb-12">
      {/* Header */}
      <div>
        <div className="text-xs font-semibold uppercase tracking-wider text-[#8E83A3]">
          Decision Support System
        </div>
        <h1 className="text-3xl font-bold font-heading text-[#1F1B2C]">
          Business Insights
        </h1>
        <p className="text-sm text-[#5F5670] mt-1 max-w-2xl">
          Translating multi-horizon mathematical predictions into actionable decision support for inventory replenishment, staffing schedules, and strategic supply buffer planning.
        </p>
      </div>

      {/* Advisory Notice Banner */}
      <div className="p-4 rounded-2xl bg-[#F5EFFF] border border-[#CDC1FF] flex items-start gap-3">
        <Info className="w-5 h-5 text-[#A294F9] shrink-0 mt-0.5" />
        <div className="text-xs text-[#5F5670] leading-relaxed">
          <strong className="text-[#1F1B2C]">Evidence-Based Advisory Decision Support:</strong> This module translates forecasted demand volumes into operational planning guidance. Recommendations are grounded in actual empirical calculations and do not claim unverified causal relationships.
        </div>
      </div>

      {/* Monitoring Alert Banner if active dataset has drift */}
      {monitoringData && (
        <section 
          data-testid="model-health-banner"
          className={`p-4 rounded-2xl border flex flex-col sm:flex-row sm:items-center justify-between gap-3 text-xs ${
            monitoringData.status === 'ACCURACY DRIFT'
              ? 'bg-rose-50 border-rose-200 text-rose-800'
              : monitoringData.status === 'WATCH'
                ? 'bg-amber-50 border-amber-200 text-amber-800'
                : monitoringData.status === 'HEALTHY'
                  ? 'bg-emerald-50 border-emerald-200 text-emerald-900'
                  : 'bg-[#F5EFFF] border-[#CDC1FF] text-[#5F5670]'
          }`}
        >
          <div className="flex items-center gap-2.5">
            <span className={`w-2.5 h-2.5 rounded-full shrink-0 ${
              monitoringData.status === 'ACCURACY DRIFT' ? 'bg-rose-500 animate-pulse' :
              monitoringData.status === 'WATCH' ? 'bg-amber-500' : 
              monitoringData.status === 'HEALTHY' ? 'bg-emerald-500' : 'bg-[#A294F9]'
            }`} />
            <div>
              <div className="flex flex-wrap items-center gap-1.5">
                <span className="font-bold uppercase tracking-wider text-[#1F1B2C]">
                  Model Health Status: {monitoringData.status}
                </span>
                {monitoringData.mape_drift_pct !== null && monitoringData.mape_drift_pct !== undefined ? (
                  <span 
                    className="font-medium opacity-85"
                    title="Accuracy Drift: relative percentage change in MAPE (forecast error) from the baseline backtest fold to the latest evaluation fold. A positive percentage indicates error growth (accuracy degradation)."
                  >
                    (Accuracy Drift: {monitoringData.mape_drift_pct > 0 ? `+${monitoringData.mape_drift_pct}%` : `${monitoringData.mape_drift_pct}%`})
                  </span>
                ) : (
                  <span className="font-medium text-[#8E83A3]">
                    (No empirical multi-fold drift calculated)
                  </span>
                )}
              </div>
              {monitoringData.retraining_alert ? (
                <p className="mt-0.5 font-medium">{monitoringData.retraining_alert}</p>
              ) : (
                <p className="mt-0.5 text-[11px] text-[#5F5670]">
                  {monitoringData.status === 'HEALTHY'
                    ? 'Empirical multi-fold backtesting indicates model accuracy is stable across evaluation origins.'
                    : (monitoringData.details?.[0]?.message || 'Grounded on chronological backtesting validation folds.')}
                </p>
              )}
            </div>
          </div>
          <span className="text-[11px] font-semibold uppercase px-2.5 py-1 rounded-full bg-white/70 border border-current shrink-0">
            {monitoringData.status}
          </span>
        </section>
      )}

      {/* Context Selector Bar */}
      {uploadedDataset ? (
        <section className="p-5 rounded-2xl bg-white border border-[#E5D9F2] shadow-xs flex flex-wrap items-center justify-between gap-4">
          <div className="flex flex-wrap items-center gap-3">
            {/* Store Selector */}
            {dimensions.has_store && availableFilters.stores.length > 0 && (
              <div className="flex items-center gap-2 bg-[#F5EFFF] px-3.5 py-2 rounded-xl border border-[#CDC1FF] text-xs">
                <span className="text-[#8E83A3] font-medium">Store:</span>
                <select
                  value={selectedStore}
                  onChange={(e) => {
                    const newStore = e.target.value;
                    setSelectedStore(newStore);
                    if (newStore && availableFilters.series.length > 0) {
                      const match = availableFilters.series.find(s => s.endsWith(newStore) || s.includes(newStore));
                      if (match) setSelectedSeries(match);
                    }
                  }}
                  className="bg-transparent font-semibold text-[#1F1B2C] outline-none cursor-pointer"
                >
                  <option value="">All Stores</option>
                  {availableFilters.stores.map((s) => (
                    <option key={s} value={s}>{s}</option>
                  ))}
                </select>
              </div>
            )}

            {/* Category Selector */}
            {dimensions.has_category && availableFilters.categories.length > 0 && (
              <div className="flex items-center gap-2 bg-[#F5EFFF] px-3.5 py-2 rounded-xl border border-[#CDC1FF] text-xs">
                <span className="text-[#8E83A3] font-medium">Category:</span>
                <select
                  value={selectedCategory}
                  onChange={(e) => setSelectedCategory(e.target.value)}
                  className="bg-transparent font-semibold text-[#1F1B2C] outline-none cursor-pointer"
                >
                  <option value="">All Categories</option>
                  {availableFilters.categories.map((c) => (
                    <option key={c} value={c}>{c}</option>
                  ))}
                </select>
              </div>
            )}

            {/* Product Selector */}
            {dimensions.has_item && availableFilters.items.length > 0 && (
              <div className="flex items-center gap-2 bg-[#F5EFFF] px-3.5 py-2 rounded-xl border border-[#CDC1FF] text-xs">
                <span className="text-[#8E83A3] font-medium">Product:</span>
                <select
                  value={selectedItem}
                  onChange={(e) => setSelectedItem(e.target.value)}
                  className="bg-transparent font-semibold text-[#1F1B2C] outline-none cursor-pointer"
                >
                  <option value="">All Products</option>
                  {availableFilters.items.map((it) => (
                    <option key={it} value={it}>{it}</option>
                  ))}
                </select>
              </div>
            )}

            {/* Series Selector */}
            {availableFilters.series.length > 0 && (
              <div className="flex items-center gap-2 bg-[#F5EFFF] px-3.5 py-2 rounded-xl border border-[#CDC1FF] text-xs max-w-xs">
                <span className="text-[#8E83A3] font-medium shrink-0">Series:</span>
                <select
                  value={selectedSeries}
                  onChange={(e) => setSelectedSeries(e.target.value)}
                  className="bg-transparent font-semibold text-[#1F1B2C] outline-none cursor-pointer truncate"
                >
                  <option value="">Select / All</option>
                  {availableFilters.series.map((s) => (
                    <option key={s} value={s}>{s}</option>
                  ))}
                </select>
              </div>
            )}

            {/* Model Selector */}
            <div className="flex items-center gap-2 bg-[#F5EFFF] px-3.5 py-2 rounded-xl border border-[#CDC1FF] text-xs">
              <span className="text-[#8E83A3] font-medium">Model:</span>
              <select
                value={selectedModel}
                onChange={(e) => setSelectedModel(e.target.value)}
                className="bg-transparent font-semibold text-[#1F1B2C] outline-none cursor-pointer"
              >
                <option value="automatic">Automatic Best Model</option>
                <option value="arima">ARIMA</option>
                <option value="sarima">SARIMA</option>
                <option value="prophet">Prophet</option>
                <option value="lightgbm">LightGBM</option>
                <option value="deepar">DeepAR</option>
                <option value="tft">Temporal Fusion Transformer</option>
              </select>
            </div>

            {/* Horizon Selector */}
            <div className="flex items-center gap-2 bg-[#F5EFFF] px-3.5 py-2 rounded-xl border border-[#CDC1FF] text-xs">
              <span className="text-[#8E83A3] font-medium">Horizon:</span>
              <select
                value={selectedHorizon}
                onChange={(e) => setSelectedHorizon(Number(e.target.value))}
                className="bg-transparent font-semibold text-[#1F1B2C] outline-none cursor-pointer"
              >
                <option value={7}>7 Days (Short-term)</option>
                <option value={28}>28 Days (Medium-term)</option>
                <option value={90}>90 Days (Long-term)</option>
              </select>
            </div>
          </div>

          <button
            onClick={handleGenerateInsights}
            disabled={isLoading}
            className={`flex items-center gap-2 px-4 py-2 rounded-xl text-xs font-bold text-white transition-all shadow-xs ${
              isLoading ? 'bg-[#CDC1FF] cursor-not-allowed' : 'bg-[#A294F9] hover:bg-[#8E83A3]'
            }`}
          >
            {isLoading ? (
              <>
                <Loader2 className="w-4 h-4 animate-spin" />
                <span>Computing Scope Insights...</span>
              </>
            ) : (
              <>
                <Sparkles className="w-4 h-4" />
                <span>Compute Evidence Insights</span>
              </>
            )}
          </button>
        </section>
      ) : (
        <section className="p-5 rounded-2xl bg-white border border-[#E5D9F2] shadow-xs flex flex-wrap items-center justify-between gap-4">
          <div className="flex flex-wrap items-center gap-3">
            <div className="flex items-center gap-2 bg-[#F5EFFF] px-3.5 py-2 rounded-xl border border-[#CDC1FF] text-xs">
              <span className="text-[#8E83A3] font-medium">Store Context:</span>
              <select
                value={activeStore}
                onChange={(e) => setActiveStore(e.target.value)}
                className="bg-transparent font-semibold text-[#1F1B2C] outline-none cursor-pointer"
              >
                {STORES.map((s) => (
                  <option key={s.id} value={s.id}>{s.name}</option>
                ))}
              </select>
            </div>

            <div className="flex items-center gap-2 bg-[#F5EFFF] px-3.5 py-2 rounded-xl border border-[#CDC1FF] text-xs">
              <span className="text-[#8E83A3] font-medium">Product Item:</span>
              <select
                value={activeProduct}
                onChange={(e) => setActiveProduct(e.target.value)}
                className="bg-transparent font-semibold text-[#1F1B2C] outline-none cursor-pointer"
              >
                {PRODUCTS.map((p) => (
                  <option key={p.id} value={p.id}>{p.id} — {p.name}</option>
                ))}
              </select>
            </div>
          </div>

          <button
            onClick={() => onNavigate('forecast')}
            className="text-xs font-semibold text-[#A294F9] hover:text-[#9181f7] flex items-center gap-1.5 transition-colors"
          >
            <span>Adjust Forecast Horizon in Engine</span>
            <ArrowRight className="w-3.5 h-3.5" />
          </button>
        </section>
      )}

      {errorMsg && (
        <div className="p-4 rounded-2xl bg-rose-50 border border-rose-200 text-rose-700 text-xs flex items-center gap-2">
          <AlertCircle className="w-4 h-4 shrink-0" />
          <span>{errorMsg}</span>
        </div>
      )}

      {/* Render Real Insights or Clean Empty State / Fallback */}
      {uploadedDataset && !insightsData && !isLoading ? (
        <div className="p-10 rounded-3xl bg-white border border-[#E5D9F2] text-center space-y-3">
          <div className="w-12 h-12 mx-auto rounded-2xl bg-[#F5EFFF] flex items-center justify-center text-[#A294F9]">
            <Sparkles className="w-6 h-6" />
          </div>
          <h3 className="text-base font-bold text-[#1F1B2C]">No Business Insights Computed Yet for Scope</h3>
          <p className="text-xs text-[#5F5670] max-w-md mx-auto">
            Current Scope: Store: <strong>{selectedStore || 'All'}</strong> | Category: <strong>{selectedCategory || 'All'}</strong> | Series: <strong>{selectedSeries || 'Default'}</strong> | Horizon: <strong>{selectedHorizon}D</strong>.
            Click <strong>Compute Evidence Insights</strong> above to derive verified inventory, staffing, and procurement recommendations.
          </p>
        </div>
      ) : insightsData ? (
        <div className="space-y-6">
          {/* Active Scope Confirmation Badge */}
          <div className="p-3.5 bg-[#F5EFFF] rounded-2xl border border-[#CDC1FF] flex flex-wrap items-center justify-between gap-3 text-xs">
            <div className="flex flex-wrap items-center gap-2">
              <span className="font-bold text-[#1F1B2C]">Verified Scope:</span>
              <span className="bg-white px-2 py-0.5 rounded-md border border-[#CDC1FF]">Store: <strong>{insightsData.store_id || insightsData.scope?.store_id || 'All'}</strong></span>
              <span className="bg-white px-2 py-0.5 rounded-md border border-[#CDC1FF]">Category: <strong>{insightsData.category || insightsData.scope?.category || 'All'}</strong></span>
              <span className="bg-white px-2 py-0.5 rounded-md border border-[#CDC1FF]">Series: <strong>{insightsData.series_id}</strong></span>
              <span className="bg-white px-2 py-0.5 rounded-md border border-[#CDC1FF]">Horizon: <strong>{insightsData.horizon}D</strong></span>
              <span className="bg-white px-2 py-0.5 rounded-md border border-[#CDC1FF]">Model: <strong>{insightsData.model}</strong></span>
            </div>
            <span className="text-emerald-700 font-semibold bg-emerald-100 px-2.5 py-1 rounded-full text-[10px] shrink-0">
              Scope Validated ✓
            </span>
          </div>

          {/* Top Grid: Demand Outlook + Inventory */}
          <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
            {/* 1. Demand Outlook */}
            <section className="p-6 rounded-3xl bg-white border border-[#E5D9F2] shadow-xs space-y-4">
              <div className="flex items-center justify-between">
                <div className="flex items-center gap-2.5">
                  <div className="p-2 rounded-xl bg-[#F5EFFF] text-[#A294F9]">
                    <TrendingUp className="w-4 h-4" />
                  </div>
                  <h2 className="text-lg font-bold font-heading text-[#1F1B2C]">
                    1. Demand Outlook
                  </h2>
                </div>
                <span className={`text-[11px] px-2.5 py-0.5 rounded-full font-semibold ${
                  insightsData.demand_outlook.demand_direction === 'INCREASING' ? 'bg-emerald-100 text-emerald-700' :
                  insightsData.demand_outlook.demand_direction === 'DECREASING' ? 'bg-rose-100 text-rose-700' :
                  insightsData.demand_outlook.demand_direction === 'HIGHLY UNCERTAIN' ? 'bg-amber-100 text-amber-700' :
                  'bg-[#E5D9F2] text-[#A294F9]'
                }`}>
                  {insightsData.demand_outlook.demand_direction}
                </span>
              </div>

              <p className="text-xs text-[#5F5670] leading-relaxed">
                Over the upcoming <strong>{insightsData.horizon}-day</strong> cycle ({insightsData.demand_outlook.forecast_period}), daily demand is projected at an average of <strong>{insightsData.demand_outlook.forecast_average_demand} units/day</strong>, representing a <strong>{insightsData.demand_outlook.expected_change_pct > 0 ? `+${insightsData.demand_outlook.expected_change_pct}%` : `${insightsData.demand_outlook.expected_change_pct}%`}</strong> deviation from the recent baseline.
              </p>

              <div className="space-y-2 pt-2 border-t border-[#F5EFFF] text-xs">
                <div className="flex items-center justify-between">
                  <span className="text-[#5F5670]">Recent Baseline Average:</span>
                  <span className="font-bold text-[#1F1B2C]">{insightsData.demand_outlook.recent_average_demand} units / day</span>
                </div>
                <div className="flex items-center justify-between">
                  <span className="text-[#5F5670]">Expected Peak:</span>
                  <span className="font-bold text-[#A294F9]">{insightsData.demand_outlook.expected_peak.value} units ({insightsData.demand_outlook.expected_peak.date})</span>
                </div>
                <div className="flex items-center justify-between">
                  <span className="text-[#5F5670]">Expected Trough:</span>
                  <span className="font-bold text-[#1F1B2C]">{insightsData.demand_outlook.expected_low.value} units ({insightsData.demand_outlook.expected_low.date})</span>
                </div>
                <div className="flex items-center justify-between">
                  <span className="text-[#5F5670]">Uncertainty Level:</span>
                  <span className={`font-semibold ${
                    insightsData.demand_outlook.uncertainty_level === 'LOW' ? 'text-emerald-600' :
                    insightsData.demand_outlook.uncertainty_level === 'HIGH' ? 'text-rose-600' :
                    'text-[#8E83A3]'
                  }`}>
                    {insightsData.demand_outlook.uncertainty_level}
                  </span>
                </div>
              </div>
            </section>

            {/* 2. Inventory Recommendation */}
            <section className="p-6 rounded-3xl bg-white border border-[#E5D9F2] shadow-xs space-y-4">
              <div className="flex items-center justify-between">
                <div className="flex items-center gap-2.5">
                  <div className="p-2 rounded-xl bg-[#F5EFFF] text-[#A294F9]">
                    <Package className="w-4 h-4" />
                  </div>
                  <h2 className="text-lg font-bold font-heading text-[#1F1B2C]">
                    2. Inventory Recommendation
                  </h2>
                </div>
                <span className={`text-[10px] uppercase font-bold px-2 py-0.5 rounded-full ${
                  insightsData.inventory_recommendation.priority === 'HIGH' ? 'bg-rose-100 text-rose-700' :
                  insightsData.inventory_recommendation.priority === 'MEDIUM' ? 'bg-amber-100 text-amber-700' :
                  'bg-gray-100 text-[#5F5670]'
                }`}>
                  Priority: {insightsData.inventory_recommendation.priority}
                </span>
              </div>

              <div className="p-3.5 rounded-2xl bg-[#F5EFFF] border border-[#CDC1FF] text-xs font-bold text-[#1F1B2C]">
                {insightsData.inventory_recommendation.recommendation}
              </div>

              <p className="text-xs text-[#5F5670] leading-relaxed">
                {insightsData.inventory_recommendation.reason}
              </p>

              <div className="pt-2 border-t border-[#F5EFFF] text-[11px] text-[#8E83A3] space-y-1">
                <div>Planning Horizon: <strong>{insightsData.inventory_recommendation.planning_period}</strong></div>
                <div>Confidence State: <strong>{insightsData.inventory_recommendation.uncertainty}</strong></div>
              </div>
            </section>
          </div>

          {/* Bottom Grid: Staffing + Procurement */}
          <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
            {/* 3. Staffing Recommendation */}
            <section className="p-6 rounded-3xl bg-white border border-[#E5D9F2] shadow-xs space-y-4">
              <div className="flex items-center justify-between">
                <div className="flex items-center gap-2.5">
                  <div className="p-2 rounded-xl bg-[#F5EFFF] text-[#A294F9]">
                    <Users className="w-4 h-4" />
                  </div>
                  <h2 className="text-lg font-bold font-heading text-[#1F1B2C]">
                    3. Staffing & Resource Planning
                  </h2>
                </div>
                <span className={`text-[10px] uppercase font-bold px-2 py-0.5 rounded-full ${
                  insightsData.staffing_recommendation.priority === 'HIGH' ? 'bg-rose-100 text-rose-700' :
                  insightsData.staffing_recommendation.priority === 'MEDIUM' ? 'bg-amber-100 text-amber-700' :
                  'bg-gray-100 text-[#5F5670]'
                }`}>
                  Priority: {insightsData.staffing_recommendation.priority}
                </span>
              </div>

              <div className="p-3.5 rounded-2xl bg-[#F5EFFF] border border-[#CDC1FF] text-xs font-bold text-[#1F1B2C]">
                {insightsData.staffing_recommendation.recommendation}
              </div>

              <p className="text-xs text-[#5F5670] leading-relaxed">
                {insightsData.staffing_recommendation.reason}
              </p>

              <div className="pt-2 border-t border-[#F5EFFF] text-[11px] text-[#8E83A3]">
                Planning Horizon: <strong>{insightsData.staffing_recommendation.planning_period}</strong>
              </div>
            </section>

            {/* 4. Strategic Procurement */}
            <section className="p-6 rounded-3xl bg-white border border-[#E5D9F2] shadow-xs space-y-4">
              <div className="flex items-center justify-between">
                <div className="flex items-center gap-2.5">
                  <div className="p-2 rounded-xl bg-[#F5EFFF] text-[#A294F9]">
                    <Truck className="w-4 h-4" />
                  </div>
                  <h2 className="text-lg font-bold font-heading text-[#1F1B2C]">
                    4. Procurement & Vendor Planning
                  </h2>
                </div>
                <span className={`text-[10px] uppercase font-bold px-2 py-0.5 rounded-full ${
                  insightsData.procurement_recommendation.priority === 'HIGH' ? 'bg-rose-100 text-rose-700' :
                  insightsData.procurement_recommendation.priority === 'MEDIUM' ? 'bg-amber-100 text-amber-700' :
                  'bg-gray-100 text-[#5F5670]'
                }`}>
                  Priority: {insightsData.procurement_recommendation.priority}
                </span>
              </div>

              <div className="p-3.5 rounded-2xl bg-[#F5EFFF] border border-[#CDC1FF] text-xs font-bold text-[#1F1B2C]">
                {insightsData.procurement_recommendation.recommendation}
              </div>

              <p className="text-xs text-[#5F5670] leading-relaxed">
                {insightsData.procurement_recommendation.reason}
              </p>

              <div className="pt-2 border-t border-[#F5EFFF] text-[11px] text-[#8E83A3]">
                Planning Horizon: <strong>{insightsData.procurement_recommendation.planning_period}</strong>
              </div>
            </section>
          </div>

          {/* Bottom Grid 2: Strategic Demand Planning & External Covariates */}
          <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
            {/* 5. Strategic Demand Planning */}
            <section className="p-6 rounded-3xl bg-white border border-[#E5D9F2] shadow-xs space-y-4">
              <div className="flex items-center gap-2.5">
                <div className="p-2 rounded-xl bg-[#F5EFFF] text-[#A294F9]">
                  <Briefcase className="w-4 h-4" />
                </div>
                <h2 className="text-lg font-bold font-heading text-[#1F1B2C]">
                  5. Strategic Demand Planning
                </h2>
              </div>

              <div className="p-3.5 rounded-2xl bg-[#F5EFFF] border border-[#CDC1FF] text-xs font-bold text-[#1F1B2C]">
                {insightsData.demand_planning?.action || insightsData.demand_planning?.state || "STRATEGIC DEMAND ALIGNMENT"}
              </div>

              <div className="space-y-2 text-xs text-[#5F5670] leading-relaxed">
                <p>
                  {insightsData.demand_planning?.explanation || insightsData.demand_planning?.medium_term_interpretation || insightsData.demand_planning?.short_term_interpretation || "Strategic demand projection aligns with current forecast velocity."}
                </p>
                {insightsData.demand_planning?.planning_focus && (
                  <p className="text-[11px] text-[#8E83A3]">
                    <strong>Planning Focus:</strong> {insightsData.demand_planning.planning_focus}
                  </p>
                )}
              </div>
            </section>

            {/* 6. External Feature Context */}
            {insightsData.optional_feature_context && Object.keys(insightsData.optional_feature_context).length > 0 && (
              <section className="p-6 rounded-3xl bg-white border border-[#E5D9F2] shadow-xs space-y-4">
                <div className="flex items-center gap-2.5">
                  <div className="p-2 rounded-xl bg-[#F5EFFF] text-[#A294F9]">
                    <Tag className="w-4 h-4" />
                  </div>
                  <h2 className="text-lg font-bold font-heading text-[#1F1B2C]">
                    6. External Feature Context
                  </h2>
                </div>

                <div className="space-y-2 text-xs">
                  {Object.entries(insightsData.optional_feature_context).map(([featKey, featVal]) => (
                    <div key={featKey} className="p-3 rounded-xl bg-[#F5EFFF]/60 border border-[#E5D9F2]">
                      <div className="flex items-center justify-between mb-1">
                        <span className="font-semibold text-[#1F1B2C] uppercase">{featKey}</span>
                        <span className={`text-[10px] font-bold px-2 py-0.5 rounded-full ${
                          featVal.available 
                            ? 'bg-emerald-100 text-emerald-700' 
                            : 'bg-gray-100 text-[#5F5670]'
                        }`}>
                          {featVal.available ? 'Available' : 'Unavailable'}
                        </span>
                      </div>
                      <span className="text-[#5F5670]">{featVal.insight}</span>
                      {/* Render event_names as pill tags for holiday — shows all named types clearly */}
                      {featVal.available && Array.isArray(featVal.event_names) && featVal.event_names.length > 0 && (
                        <div className="flex flex-wrap gap-1 mt-2">
                          {featVal.event_names.map((name) => (
                            <span
                              key={name}
                              className="text-[10px] px-1.5 py-0.5 rounded bg-[#E5D9F2] text-[#1F1B2C] font-medium"
                            >
                              {name}
                            </span>
                          ))}
                        </div>
                      )}
                    </div>
                  ))}
                </div>
              </section>
            )}
          </div>

          {/* Horizon Breakdown & Optional Covariates Banner */}
          <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
            {(() => {
              const is7dEval = Boolean(
                selectedHorizon >= 7 &&
                insightsData.horizon_insights?.['7D'] &&
                !insightsData.horizon_insights['7D'].toLowerCase().includes('unavailable') &&
                !insightsData.horizon_insights['7D'].toLowerCase().includes('not evaluated')
              );
              const is28dEval = Boolean(
                selectedHorizon >= 28 &&
                insightsData.horizon_insights?.['28D'] &&
                !insightsData.horizon_insights['28D'].toLowerCase().includes('not evaluated') &&
                !insightsData.horizon_insights['28D'].toLowerCase().includes('unavailable')
              );
              const is90dEval = Boolean(
                selectedHorizon >= 90 &&
                insightsData.horizon_insights?.['90D'] &&
                !insightsData.horizon_insights['90D'].toLowerCase().includes('not evaluated') &&
                !insightsData.horizon_insights['90D'].toLowerCase().includes('unavailable')
              );

              return (
                <>
                  <section className="p-5 rounded-2xl bg-white border border-[#E5D9F2] space-y-2">
                    <div className="flex items-center justify-between">
                      <div className="text-[11px] font-bold text-[#8E83A3] uppercase tracking-wider">7-Day Operational Focus</div>
                      <span className={`text-[10px] font-semibold px-2 py-0.5 rounded-full ${is7dEval ? 'bg-emerald-100 text-emerald-700' : 'bg-gray-100 text-gray-500'}`}>
                        {is7dEval ? 'Evaluated' : 'Not Evaluated'}
                      </span>
                    </div>
                    <p className="text-xs text-[#5F5670] leading-relaxed">{insightsData.horizon_insights?.['7D'] || 'Short-term tactical execution.'}</p>
                  </section>
                  <section className="p-5 rounded-2xl bg-white border border-[#E5D9F2] space-y-2">
                    <div className="flex items-center justify-between">
                      <div className="text-[11px] font-bold text-[#8E83A3] uppercase tracking-wider">28-Day Tactical Rebalance</div>
                      <span className={`text-[10px] font-semibold px-2 py-0.5 rounded-full ${is28dEval ? 'bg-emerald-100 text-emerald-700' : 'bg-gray-100 text-gray-500'}`}>
                        {is28dEval ? 'Evaluated' : 'Not Evaluated'}
                      </span>
                    </div>
                    <p className="text-xs text-[#5F5670] leading-relaxed">{insightsData.horizon_insights?.['28D'] || 'Monthly distribution cycle.'}</p>
                  </section>
                  <section className="p-5 rounded-2xl bg-white border border-[#E5D9F2] space-y-2">
                    <div className="flex items-center justify-between">
                      <div className="text-[11px] font-bold text-[#8E83A3] uppercase tracking-wider">90-Day Strategic Buffer</div>
                      <span className={`text-[10px] font-semibold px-2 py-0.5 rounded-full ${is90dEval ? 'bg-emerald-100 text-emerald-700' : 'bg-amber-100 text-amber-700'}`}>
                        {is90dEval ? 'Evaluated' : 'Not Evaluated'}
                      </span>
                    </div>
                    <p className="text-xs text-[#5F5670] leading-relaxed">{insightsData.horizon_insights?.['90D'] || 'Quarterly safety buffer.'}</p>
                  </section>
                </>
              );
            })()}
          </div>
        </div>
      ) : (
        /* Reference Demo Mode (purely when no real dataset is uploaded) */
        <div className="space-y-6">
          <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
            <section className="p-6 rounded-3xl bg-white border border-[#E5D9F2] shadow-xs space-y-4">
              <div className="flex items-center justify-between">
                <div className="flex items-center gap-2.5">
                  <div className="p-2 rounded-xl bg-[#F5EFFF] text-[#A294F9]"><TrendingUp className="w-4 h-4" /></div>
                  <h2 className="text-lg font-bold font-heading text-[#1F1B2C]">1. Demand Outlook</h2>
                </div>
                <span className="text-[11px] px-2.5 py-0.5 rounded-full font-semibold bg-emerald-100 text-emerald-700">INCREASING</span>
              </div>
              <p className="text-xs text-[#5F5670] leading-relaxed">
                Projected average demand of <strong>{Math.round(selectedProdObj.avgDaily * 1.15)} units/day</strong> for {selectedProdObj.id} ({selectedProdObj.name}) at {activeStore}.
              </p>
            </section>
            <section className="p-6 rounded-3xl bg-white border border-[#E5D9F2] shadow-xs space-y-4">
              <div className="flex items-center justify-between">
                <div className="flex items-center gap-2.5">
                  <div className="p-2 rounded-xl bg-[#F5EFFF] text-[#A294F9]"><Package className="w-4 h-4" /></div>
                  <h2 className="text-lg font-bold font-heading text-[#1F1B2C]">2. Inventory Replenishment</h2>
                </div>
                <span className="text-[10px] uppercase font-bold px-2 py-0.5 rounded-full bg-rose-100 text-rose-700">Priority: High</span>
              </div>
              <div className="p-3.5 rounded-2xl bg-[#F5EFFF] border border-[#CDC1FF] text-xs font-bold text-[#1F1B2C]">
                CONSIDER STOCKING UP / INCREASING REPLENISHMENT
              </div>
              <p className="text-xs text-[#5F5670] leading-relaxed">
                Anticipated upward velocity warrants proactive buffer re-evaluation.
              </p>
            </section>
          </div>
        </div>
      )}
    </div>
  );
}
