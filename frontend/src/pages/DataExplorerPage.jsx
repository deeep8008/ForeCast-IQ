import React, { useState, useEffect, useMemo, useRef } from 'react';
import { STORES, CATEGORIES, PRODUCTS } from '../data/mockData';
import { getExplorerDataFromBackend } from '../services/api';

// ---------------------------------------------------------------------------
// Real-data mode: DataExplorer computed from the FULL active dataset via backend
// ---------------------------------------------------------------------------
function RealDataExplorer({ uploadedDataset, onNavigate }) {
  const [selectedStore, setSelectedStore] = useState('');
  const [selectedCategory, setSelectedCategory] = useState('');
  const [selectedItem, setSelectedItem] = useState('');
  const [selectedSeries, setSelectedSeries] = useState('');
  const [dateWindow, setDateWindow] = useState('all');
  const [showMovingAvg, setShowMovingAvg] = useState(true);

  const [explorerData, setExplorerData] = useState(null);
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState(null);

  const abortControllerRef = useRef(null);

  useEffect(() => {
    if (!uploadedDataset?.dataset_id) return;

    if (abortControllerRef.current) {
      abortControllerRef.current.abort();
    }
    const controller = new AbortController();
    abortControllerRef.current = controller;

    Promise.resolve().then(() => {
      setIsLoading(true);
      setError(null);
    });

    getExplorerDataFromBackend(
      uploadedDataset.dataset_id,
      {
        store_id: selectedStore || undefined,
        category: selectedCategory || undefined,
        item_id: selectedItem || undefined,
        series_id: selectedSeries || undefined,
        date_range: dateWindow,
      },
      controller.signal
    )
      .then((data) => {
        if (!data) {
          setError('Could not retrieve full dataset analytics.');
          setIsLoading(false);
          return;
        }
        setExplorerData(data);
        setIsLoading(false);

        // Synchronize default selections with returned available filters if empty
        if (!selectedStore && data.scope?.store_id) {
          setSelectedStore(data.scope.store_id);
        }
        if (!selectedCategory && data.scope?.category) {
          setSelectedCategory(data.scope.category);
        }
        if (!selectedItem && data.scope?.item_id) {
          setSelectedItem(data.scope.item_id);
        }
        if (!selectedSeries && data.scope?.series_id) {
          setSelectedSeries(data.scope.series_id);
        }
      })
      .catch((err) => {
        if (err.name !== 'AbortError') {
          setError('Failed to fetch full dataset analytics.');
          setIsLoading(false);
        }
      });

    return () => {
      controller.abort();
    };
  }, [uploadedDataset?.dataset_id, selectedStore, selectedCategory, selectedItem, selectedSeries, dateWindow]);

  const dimensions = explorerData?.dimensions || {};
  const availableFilters = explorerData?.available_filters || { stores: [], categories: [], items: [], series: [] };
  const trend = explorerData?.trend || [];
  const maxSales = trend.length > 0 ? Math.max(1, Math.max(...trend.map((t) => t.sales || 0))) : 1;

  return (
    <div className="space-y-8 max-w-7xl mx-auto pb-12">
      {/* Header */}
      <div>
        <div className="text-xs font-semibold uppercase tracking-wider text-[#8E83A3]">
          Complete Dataset Exploration
        </div>
        <h1 className="text-3xl font-bold font-heading text-[#1F1B2C]">Data Explorer</h1>
        <p className="text-sm text-[#5F5670] mt-1 max-w-2xl">
          Aggregating strictly from the <strong className="text-[#1F1B2C]">complete active dataset</strong>: <span className="font-semibold text-[#1F1B2C]">{uploadedDataset.filename}</span>
          {' '}— {explorerData ? `${explorerData.total_rows.toLocaleString()} filtered observations (${explorerData.total_series} series)` : 'Analyzing full series records...'}
        </p>
      </div>

      {/* Filter Bar */}
      <section className="p-5 rounded-2xl bg-white border border-[#E5D9F2] shadow-xs">
        <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-5 gap-3.5 items-end">
          {/* Store filter */}
          {dimensions.has_store && availableFilters.stores.length > 0 && (
            <div>
              <label className="block text-[11px] font-semibold uppercase tracking-wider text-[#8E83A3] mb-1.5">
                Store
              </label>
              <select
                value={selectedStore || (explorerData?.scope?.store_id || '')}
                onChange={(e) => {
                  setSelectedStore(e.target.value);
                  setSelectedCategory('');
                  setSelectedItem('');
                  setSelectedSeries('');
                }}
                className="w-full bg-[#F5EFFF] border border-[#CDC1FF] rounded-xl px-3 py-2 text-xs font-semibold text-[#1F1B2C] outline-none"
              >
                {availableFilters.stores.map((s) => (
                  <option key={s} value={s}>{s}</option>
                ))}
              </select>
            </div>
          )}

          {/* Category filter */}
          {dimensions.has_category && availableFilters.categories.length > 0 && (
            <div>
              <label className="block text-[11px] font-semibold uppercase tracking-wider text-[#8E83A3] mb-1.5">
                Category
              </label>
              <select
                value={selectedCategory || (explorerData?.scope?.category || '')}
                onChange={(e) => {
                  setSelectedCategory(e.target.value);
                  setSelectedItem('');
                  setSelectedSeries('');
                }}
                className="w-full bg-[#F5EFFF] border border-[#CDC1FF] rounded-xl px-3 py-2 text-xs font-semibold text-[#1F1B2C] outline-none"
              >
                {availableFilters.categories.map((c) => (
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
                value={selectedItem || (explorerData?.scope?.item_id || '')}
                onChange={(e) => {
                  setSelectedItem(e.target.value);
                  setSelectedSeries('');
                }}
                className="w-full bg-[#F5EFFF] border border-[#CDC1FF] rounded-xl px-3 py-2 text-xs font-semibold text-[#1F1B2C] outline-none"
              >
                {availableFilters.items.map((it) => (
                  <option key={it} value={it}>{it}</option>
                ))}
              </select>
            </div>
          )}

          {/* Series filter */}
          {availableFilters.series.length > 0 && (
            <div>
              <label className="block text-[11px] font-semibold uppercase tracking-wider text-[#8E83A3] mb-1.5">
                Series ID
              </label>
              <select
                value={selectedSeries || (explorerData?.scope?.series_id || '')}
                onChange={(e) => setSelectedSeries(e.target.value)}
                className="w-full bg-[#F5EFFF] border border-[#CDC1FF] rounded-xl px-3 py-2 text-xs font-semibold text-[#1F1B2C] outline-none truncate"
              >
                {availableFilters.series.map((s) => (
                  <option key={s} value={s}>{s}</option>
                ))}
              </select>
            </div>
          )}

          {/* Date Window */}
          <div>
            <label className="block text-[11px] font-semibold uppercase tracking-wider text-[#8E83A3] mb-1.5">
              Date Window
            </label>
            <div className="grid grid-cols-4 gap-1 bg-[#F5EFFF] p-1 rounded-xl border border-[#CDC1FF]">
              {[
                { id: '30d', label: '30D' },
                { id: '90d', label: '90D' },
                { id: '180d', label: '180D' },
                { id: 'all', label: 'ALL' },
              ].map((opt) => (
                <button
                  key={opt.id}
                  onClick={() => setDateWindow(opt.id)}
                  className={`py-1 text-center text-xs rounded-lg font-medium transition-all ${
                    dateWindow === opt.id
                      ? 'bg-[#A294F9] text-white shadow-xs font-bold'
                      : 'text-[#5F5670] hover:text-[#1F1B2C]'
                  }`}
                >
                  {opt.label}
                </button>
              ))}
            </div>
          </div>
        </div>
      </section>

      {/* Loading State Overlay */}
      {isLoading && (
        <div className="p-8 rounded-3xl bg-white border border-[#E5D9F2] text-center space-y-2">
          <div className="animate-spin text-2xl">⏳</div>
          <h3 className="text-sm font-bold text-[#1F1B2C]">Computing Analytics Across Full Dataset...</h3>
          <p className="text-xs text-[#5F5670]">
            Filtering complete dataset on the server to prevent preview sampling errors.
          </p>
        </div>
      )}

      {error && !isLoading && (
        <div className="p-6 rounded-3xl bg-rose-50 border border-rose-200 text-rose-700 text-xs">
          {error}
        </div>
      )}

      {/* Active Data Sections */}
      {!isLoading && explorerData && (
        <>
          {/* Section A: Historical Sales Trend from FULL dataset */}
          <section className="p-6 rounded-3xl bg-white border border-[#E5D9F2] shadow-xs space-y-4">
            <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4">
              <div>
                <div className="text-xs font-semibold uppercase tracking-wider text-[#8E83A3]">Section A</div>
                <h2 className="text-xl font-bold font-heading text-[#1F1B2C]">
                  Historical Demand Trend — {explorerData.scope.series_id || explorerData.scope.item_id || 'Selected Scope'}
                </h2>
                <p className="text-xs text-[#5F5670]">
                  Full dataset calculation: {trend.length} daily time steps ({explorerData.date_min} → {explorerData.date_max}).
                  Total volume: <strong className="text-[#1F1B2C]">{Number(explorerData.total_demand).toLocaleString()}</strong> units.
                </p>
              </div>
              <button
                onClick={() => setShowMovingAvg(!showMovingAvg)}
                className={`text-xs px-3 py-1.5 rounded-xl border transition-all ${
                  showMovingAvg
                    ? 'bg-[#E5D9F2] text-[#1F1B2C] border-[#CDC1FF] font-semibold'
                    : 'bg-white text-[#5F5670] border-[#E5D9F2]'
                }`}
              >
                {showMovingAvg ? '✓ 7-Day Moving Avg Enabled' : '+ Show 7-Day Moving Avg'}
              </button>
            </div>

            <div className="relative w-full h-64 bg-[#F5EFFF]/30 rounded-2xl border border-[#E5D9F2] p-4 flex flex-col justify-end">
              <svg viewBox="0 0 800 200" className="w-full h-full overflow-visible">
                {[0, 50, 100, 150].map((yVal, i) => (
                  <line key={i} x1="0" y1={200 - yVal} x2="800" y2={200 - yVal} stroke="#E5D9F2" strokeDasharray="3 3" />
                ))}
                <path
                  d={trend.map((pt, i) => {
                    const x = trend.length > 1 ? (i / (trend.length - 1)) * 800 : 400;
                    const y = 200 - (pt.sales / maxSales) * 170;
                    return `${i === 0 ? 'M' : 'L'} ${x} ${y}`;
                  }).join(' ')}
                  fill="none" stroke="#A294F9" strokeWidth="2" strokeLinejoin="round"
                />
                {showMovingAvg && (
                  <path
                    d={trend.map((pt, i) => {
                      const x = trend.length > 1 ? (i / (trend.length - 1)) * 800 : 400;
                      const y = 200 - (pt.rollingAvg / maxSales) * 170;
                      return `${i === 0 ? 'M' : 'L'} ${x} ${y}`;
                    }).join(' ')}
                    fill="none" stroke="#5F5670" strokeWidth="2" strokeDasharray="4 2"
                  />
                )}
              </svg>
              <div className="flex items-center justify-between text-[11px] text-[#8E83A3] mt-2">
                <span>{explorerData.date_min}</span>
                <div className="flex items-center gap-4">
                  <span className="flex items-center gap-1.5"><span className="w-3 h-0.5 bg-[#A294F9] inline-block" />Full Dataset Demand</span>
                  {showMovingAvg && <span className="flex items-center gap-1.5"><span className="w-3 h-0.5 bg-[#5F5670] inline-block" />7-Day Rolling Trend</span>}
                </div>
                <span>{explorerData.date_max}</span>
              </div>
            </div>
          </section>

          {/* Grid: Sections B, C, D */}
          <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
            {/* Section B: Sales by Store from FULL dataset */}
            <section className="p-6 rounded-3xl bg-white border border-[#E5D9F2] shadow-xs space-y-4">
              <div>
                <div className="text-xs font-semibold uppercase tracking-wider text-[#8E83A3]">Section B</div>
                <h3 className="text-lg font-bold font-heading text-[#1F1B2C]">
                  {dimensions.has_store ? 'Sales by Store (Full Data)' : 'Series Distribution'}
                </h3>
                <p className="text-xs text-[#5F5670]">
                  {dimensions.has_store ? 'Total actual demand across store network.' : 'All series in active dataset.'}
                </p>
              </div>
              <div className="space-y-3 pt-2">
                {dimensions.has_store && explorerData.store_breakdown.length > 0 ? (
                  explorerData.store_breakdown.map((item) => (
                    <div key={item.id} className="space-y-1">
                      <div className="flex justify-between text-xs">
                        <span className={`font-semibold ${item.id === explorerData.scope.store_id ? 'text-[#A294F9]' : 'text-[#1F1B2C]'}`}>
                          {item.id} {item.id === explorerData.scope.store_id ? '(Selected)' : ''}
                        </span>
                        <span className="text-[#5F5670] font-medium">{Number(item.val).toLocaleString()} total units</span>
                      </div>
                      <div className="h-2 w-full bg-[#F5EFFF] rounded-full overflow-hidden">
                        <div
                          className={`h-full rounded-full transition-all ${item.id === explorerData.scope.store_id ? 'bg-[#A294F9]' : 'bg-[#CDC1FF]'}`}
                          style={{ width: `${item.pct || 0}%` }}
                        />
                      </div>
                    </div>
                  ))
                ) : (
                  availableFilters.series.slice(0, 6).map((s) => (
                    <div key={s} className={`p-2.5 rounded-xl text-xs border ${s === explorerData.scope.series_id ? 'bg-[#F5EFFF] border-[#CDC1FF] text-[#A294F9] font-bold' : 'bg-white border-[#E5D9F2] text-[#1F1B2C]'}`}>
                      {s}
                    </div>
                  ))
                )}
              </div>
            </section>

            {/* Section C: Category Share from FULL dataset */}
            <section className="p-6 rounded-3xl bg-white border border-[#E5D9F2] shadow-xs space-y-4">
              <div>
                <div className="text-xs font-semibold uppercase tracking-wider text-[#8E83A3]">Section C</div>
                <h3 className="text-lg font-bold font-heading text-[#1F1B2C]">
                  {dimensions.has_category ? 'Category Share (Full Data)' : 'Dataset Information'}
                </h3>
                <p className="text-xs text-[#5F5670]">
                  {dimensions.has_category ? `Actual category distribution for ${explorerData.scope.store_id || 'all stores'}.` : 'Column structure.'}
                </p>
              </div>
              <div className="space-y-3 pt-2">
                {dimensions.has_category && explorerData.category_breakdown.length > 0 ? (
                  explorerData.category_breakdown.map((cat, i) => {
                    const colors = ['#A294F9', '#CDC1FF', '#E5D9F2'];
                    return (
                      <div
                        key={cat.name}
                        className={`p-3.5 rounded-2xl border transition-all ${explorerData.scope.category === cat.name ? 'bg-[#F5EFFF] border-[#CDC1FF] shadow-xs' : 'bg-white border-[#E5D9F2]'}`}
                      >
                        <div className="flex items-center justify-between">
                          <div className="flex items-center gap-2.5">
                            <span className="w-3 h-3 rounded-full" style={{ backgroundColor: colors[i % colors.length] }} />
                            <span className="text-xs font-bold text-[#1F1B2C]">{cat.name}</span>
                          </div>
                          <span className="text-xs font-bold text-[#1F1B2C]">{cat.share}</span>
                        </div>
                        <div className="text-[11px] text-[#8E83A3] mt-1 pl-5.5">
                          {Number(cat.count).toLocaleString()} total demand units
                        </div>
                      </div>
                    );
                  })
                ) : (
                  <div className="space-y-2 text-xs">
                    <div className="flex justify-between py-1.5 border-b border-[#F5EFFF]">
                      <span className="text-[#5F5670]">Total Observations:</span>
                      <span className="font-mono font-semibold text-[#1F1B2C]">{explorerData.total_rows.toLocaleString()}</span>
                    </div>
                    <div className="flex justify-between py-1.5 border-b border-[#F5EFFF]">
                      <span className="text-[#5F5670]">Series Detected:</span>
                      <span className="font-mono font-semibold text-[#1F1B2C]">{explorerData.total_series}</span>
                    </div>
                    <div className="flex justify-between py-1.5 border-b border-[#F5EFFF]">
                      <span className="text-[#5F5670]">Date Coverage:</span>
                      <span className="font-mono font-semibold text-[#1F1B2C]">{explorerData.date_min} → {explorerData.date_max}</span>
                    </div>
                  </div>
                )}
              </div>
            </section>

            {/* Section D: Series Summary Card computed from FULL dataset */}
            <section className="p-6 rounded-3xl bg-white border border-[#E5D9F2] shadow-xs space-y-4">
              <div>
                <div className="text-xs font-semibold uppercase tracking-wider text-[#8E83A3]">Section D</div>
                <h3 className="text-lg font-bold font-heading text-[#1F1B2C]">Series Summary Card</h3>
                <p className="text-xs text-[#5F5670]">Authentic statistics calculated from full dataset.</p>
              </div>
              <div className="space-y-2.5 text-xs">
                {dimensions.has_store && (
                  <div className="flex justify-between py-1.5 border-b border-[#F5EFFF]">
                    <span className="text-[#5F5670]">Selected Store:</span>
                    <span className="font-semibold text-[#1F1B2C]">{explorerData.scope.store_id || 'All'}</span>
                  </div>
                )}
                {dimensions.has_category && (
                  <div className="flex justify-between py-1.5 border-b border-[#F5EFFF]">
                    <span className="text-[#5F5670]">Category:</span>
                    <span className="font-semibold text-[#1F1B2C]">{explorerData.scope.category || 'All'}</span>
                  </div>
                )}
                <div className="flex justify-between py-1.5 border-b border-[#F5EFFF]">
                  <span className="text-[#5F5670]">Selected Series:</span>
                  <span className="font-semibold text-[#1F1B2C] text-right max-w-[60%] break-all">{explorerData.scope.series_id || 'Scope aggregate'}</span>
                </div>
                <div className="flex justify-between py-1.5 border-b border-[#F5EFFF]">
                  <span className="text-[#5F5670]">Observation Count (Full):</span>
                  <span className="font-semibold text-[#1F1B2C]">{explorerData.total_rows.toLocaleString()}</span>
                </div>
                <div className="flex justify-between py-1.5 border-b border-[#F5EFFF]">
                  <span className="text-[#5F5670]">Average Daily Demand:</span>
                  <span className="font-semibold text-[#A294F9]">{explorerData.avg_daily_demand} units</span>
                </div>
                <div className="flex justify-between py-1.5 border-b border-[#F5EFFF]">
                  <span className="text-[#5F5670]">Peak Day Demand:</span>
                  <span className="font-semibold text-[#1F1B2C]">{explorerData.max_demand} units</span>
                </div>
                <div className="flex justify-between py-1.5">
                  <span className="text-[#5F5670]">Zero-Demand Frequency:</span>
                  <span className={`font-semibold ${explorerData.zero_days_pct > 20 ? 'text-amber-600' : 'text-emerald-600'}`}>
                    {explorerData.zero_days_pct}% ({explorerData.zero_days_count.toLocaleString()} days)
                  </span>
                </div>
              </div>
              <div className="pt-2">
                <button
                  onClick={() => onNavigate('forecast')}
                  className="w-full py-2.5 rounded-xl bg-[#A294F9] text-white text-xs font-semibold hover:bg-[#9181f7] shadow-xs transition-colors"
                >
                  Configure Forecast for {explorerData.scope.series_id || 'this Series'} →
                </button>
              </div>
            </section>
          </div>
        </>
      )}
    </div>
  );
}

// ---------------------------------------------------------------------------
// M5 Demo mode (shown ONLY when no dataset is uploaded)
// ---------------------------------------------------------------------------
function M5DemoExplorer({ _onNavigate }) {
  const [selectedState, setSelectedState] = useState('CA');
  const [selectedStore, setSelectedStore] = useState('CA_1');
  const [selectedCategory, setSelectedCategory] = useState('FOODS');
  const [selectedProduct, setSelectedProduct] = useState('FOODS_3_090');
  const [dateRange, setDateRange] = useState('90d');
  const [showMovingAvg, setShowMovingAvg] = useState(true);

  const availableStores = useMemo(() => STORES.filter((s) => s.state === selectedState), [selectedState]);
  const availableProducts = useMemo(() => PRODUCTS.filter((p) => p.category === selectedCategory), [selectedCategory]);
  const currentProduct = useMemo(() => PRODUCTS.find((p) => p.id === selectedProduct) || PRODUCTS[0], [selectedProduct]);

  const salesHistory = useMemo(() => {
    const days = dateRange === '30d' ? 30 : dateRange === '90d' ? 90 : 180;
    const list = [];
    const base = currentProduct.avgDaily;
    const storeMultiplier = selectedStore.startsWith('CA') ? 1.15 : selectedStore.startsWith('TX') ? 0.95 : 0.9;
    for (let i = days; i >= 1; i--) {
      const d = new Date('2016-04-24');
      d.setDate(d.getDate() - i);
      const isWeekend = d.getDay() === 0 || d.getDay() === 6;
      const weekendBoost = isWeekend ? 1.3 : 0.92;
      const noise = Math.sin(i * 1.5) * 0.18 + Math.cos(i * 0.7) * 0.12;
      const isPromo = i === 12 || i === 42 || i === 70;
      const promoBoost = isPromo ? 1.45 : 1.0;
      const sales = Math.max(0, Math.round(base * storeMultiplier * weekendBoost * (1 + noise) * promoBoost));
      list.push({
        date: d.toISOString().split('T')[0],
        sales,
        isWeekend,
        isPromo,
        promoName: isPromo ? (i === 12 ? 'Spring Promotion' : i === 42 ? 'SNAP Benefit Start' : 'Weekend Flash Sale') : null,
        price: currentProduct.currentPrice - (isPromo ? 0.2 : 0),
      });
    }
    return list.map((item, idx, arr) => {
      const windowStart = Math.max(0, idx - 6);
      const windowItems = arr.slice(windowStart, idx + 1);
      const avg = Math.round(windowItems.reduce((acc, curr) => acc + curr.sales, 0) / windowItems.length);
      return { ...item, rollingAvg: avg };
    });
  }, [currentProduct, selectedStore, dateRange]);

  const summaryStats = useMemo(() => {
    const total = salesHistory.reduce((acc, item) => acc + item.sales, 0);
    const avg = (total / salesHistory.length).toFixed(1);
    const max = Math.max(...salesHistory.map((s) => s.sales));
    const zeroDays = salesHistory.filter((s) => s.sales === 0).length;
    const zeroPct = ((zeroDays / salesHistory.length) * 100).toFixed(1);
    return { total, avg, max, zeroDays, zeroPct };
  }, [salesHistory]);

  return (
    <div className="space-y-8 max-w-7xl mx-auto pb-12">
      <div>
        <div className="text-xs font-semibold uppercase tracking-wider text-[#8E83A3]">M5 Reference Demonstration</div>
        <h1 className="text-3xl font-bold font-heading text-[#1F1B2C]">Data Explorer</h1>
        <p className="text-sm text-[#5F5670] mt-1 max-w-2xl">
          Inspect historical sales velocity, price changes, calendar events, and store distributions before training or inference.
        </p>
      </div>

      <section className="p-5 rounded-2xl bg-white border border-[#E5D9F2] shadow-xs">
        <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-5 gap-3.5 items-end">
          <div>
            <label className="block text-[11px] font-semibold uppercase tracking-wider text-[#8E83A3] mb-1.5">1. State</label>
            <select
              value={selectedState}
              onChange={(e) => {
                setSelectedState(e.target.value);
                const next = STORES.find((s) => s.state === e.target.value);
                if (next) setSelectedStore(next.id);
              }}
              className="w-full bg-[#F5EFFF] border border-[#CDC1FF] rounded-xl px-3 py-2 text-xs font-semibold text-[#1F1B2C] outline-none"
            >
              <option value="CA">California (CA)</option>
              <option value="TX">Texas (TX)</option>
              <option value="WI">Wisconsin (WI)</option>
            </select>
          </div>
          <div>
            <label className="block text-[11px] font-semibold uppercase tracking-wider text-[#8E83A3] mb-1.5">2. Store</label>
            <select
              value={selectedStore}
              onChange={(e) => setSelectedStore(e.target.value)}
              className="w-full bg-[#F5EFFF] border border-[#CDC1FF] rounded-xl px-3 py-2 text-xs font-semibold text-[#1F1B2C] outline-none"
            >
              {availableStores.map((s) => <option key={s.id} value={s.id}>{s.name}</option>)}
            </select>
          </div>
          <div>
            <label className="block text-[11px] font-semibold uppercase tracking-wider text-[#8E83A3] mb-1.5">3. Category</label>
            <select
              value={selectedCategory}
              onChange={(e) => {
                setSelectedCategory(e.target.value);
                const next = PRODUCTS.find((p) => p.category === e.target.value);
                if (next) setSelectedProduct(next.id);
              }}
              className="w-full bg-[#F5EFFF] border border-[#CDC1FF] rounded-xl px-3 py-2 text-xs font-semibold text-[#1F1B2C] outline-none"
            >
              {CATEGORIES.map((c) => <option key={c.id} value={c.id}>{c.name}</option>)}
            </select>
          </div>
          <div>
            <label className="block text-[11px] font-semibold uppercase tracking-wider text-[#8E83A3] mb-1.5">4. Product Series</label>
            <select
              value={selectedProduct}
              onChange={(e) => setSelectedProduct(e.target.value)}
              className="w-full bg-[#F5EFFF] border border-[#CDC1FF] rounded-xl px-3 py-2 text-xs font-semibold text-[#1F1B2C] outline-none truncate"
            >
              {availableProducts.map((p) => <option key={p.id} value={p.id}>{p.id} — {p.name}</option>)}
            </select>
          </div>
          <div>
            <label className="block text-[11px] font-semibold uppercase tracking-wider text-[#8E83A3] mb-1.5">5. Date Window</label>
            <div className="grid grid-cols-3 gap-1 bg-[#F5EFFF] p-1 rounded-xl border border-[#CDC1FF]">
              {[{ id: '30d', label: '30D' }, { id: '90d', label: '90D' }, { id: '180d', label: '180D' }].map((opt) => (
                <button
                  key={opt.id}
                  onClick={() => setDateRange(opt.id)}
                  className={`py-1.5 text-center text-xs rounded-lg font-medium transition-all ${
                    dateRange === opt.id ? 'bg-[#A294F9] text-white shadow-xs font-bold' : 'text-[#5F5670] hover:text-[#1F1B2C]'
                  }`}
                >
                  {opt.label}
                </button>
              ))}
            </div>
          </div>
        </div>
      </section>

      <section className="p-6 rounded-3xl bg-white border border-[#E5D9F2] shadow-xs space-y-4">
        <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4">
          <div>
            <div className="text-xs font-semibold uppercase tracking-wider text-[#8E83A3]">Section A</div>
            <h2 className="text-xl font-bold font-heading text-[#1F1B2C]">Historical Sales Trend ({dateRange.toUpperCase()})</h2>
            <p className="text-xs text-[#5F5670]">Daily observations showing weekly recurring peaks and promotional spikes.</p>
          </div>
          <button
            onClick={() => setShowMovingAvg(!showMovingAvg)}
            className={`text-xs px-3 py-1.5 rounded-xl border transition-all ${
              showMovingAvg ? 'bg-[#E5D9F2] text-[#1F1B2C] border-[#CDC1FF] font-semibold' : 'bg-white text-[#5F5670] border-[#E5D9F2]'
            }`}
          >
            {showMovingAvg ? '✓ 7-Day Moving Avg Enabled' : '+ Show 7-Day Moving Avg'}
          </button>
        </div>
        <div className="relative w-full h-64 bg-[#F5EFFF]/30 rounded-2xl border border-[#E5D9F2] p-4 flex flex-col justify-end">
          <svg viewBox="0 0 800 200" className="w-full h-full overflow-visible">
            {[0, 50, 100, 150].map((yVal, i) => (
              <line key={i} x1="0" y1={200 - yVal} x2="800" y2={200 - yVal} stroke="#E5D9F2" strokeDasharray="3 3" />
            ))}
            <path
              d={salesHistory.map((pt, i) => {
                const x = (i / (salesHistory.length - 1)) * 800;
                const y = 200 - (pt.sales / summaryStats.max) * 170;
                return `${i === 0 ? 'M' : 'L'} ${x} ${y}`;
              }).join(' ')}
              fill="none" stroke="#A294F9" strokeWidth="2" strokeLinejoin="round"
            />
            {showMovingAvg && (
              <path
                d={salesHistory.map((pt, i) => {
                  const x = (i / (salesHistory.length - 1)) * 800;
                  const y = 200 - (pt.rollingAvg / summaryStats.max) * 170;
                  return `${i === 0 ? 'M' : 'L'} ${x} ${y}`;
                }).join(' ')}
                fill="none" stroke="#5F5670" strokeWidth="2" strokeDasharray="4 2"
              />
            )}
            {salesHistory.map((pt, i) => {
              if (!pt.isPromo) return null;
              const x = (i / (salesHistory.length - 1)) * 800;
              const y = 200 - (pt.sales / summaryStats.max) * 170;
              return (
                <g key={i}>
                  <circle cx={x} cy={y} r="5" fill="#A294F9" stroke="#FFFFFF" strokeWidth="2" />
                  <line x1={x} y1={y} x2={x} y2={195} stroke="#CDC1FF" strokeWidth="1" strokeDasharray="2 2" />
                </g>
              );
            })}
          </svg>
          <div className="flex items-center justify-between text-[11px] text-[#8E83A3] mt-2">
            <span>{salesHistory[0]?.date}</span>
            <div className="flex items-center gap-4">
              <span className="flex items-center gap-1.5"><span className="w-3 h-0.5 bg-[#A294F9] inline-block" />Daily Sales</span>
              {showMovingAvg && <span className="flex items-center gap-1.5"><span className="w-3 h-0.5 bg-[#5F5670] inline-block" />7-Day Rolling Trend</span>}
            </div>
            <span>{salesHistory[salesHistory.length - 1]?.date} (Cutoff)</span>
          </div>
        </div>
      </section>

      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
        <section className="p-6 rounded-3xl bg-white border border-[#E5D9F2] shadow-xs space-y-4">
          <div>
            <div className="text-xs font-semibold uppercase tracking-wider text-[#8E83A3]">Section B</div>
            <h3 className="text-lg font-bold font-heading text-[#1F1B2C]">Sales by Store</h3>
            <p className="text-xs text-[#5F5670]">Relative store volume across state retail network.</p>
          </div>
          <div className="space-y-3 pt-2">
            {[
              { id: 'CA_1', name: 'California 1', val: 124, pct: 100 },
              { id: 'CA_2', name: 'California 2', val: 108, pct: 87 },
              { id: 'CA_3', name: 'California 3', val: 95, pct: 76 },
              { id: 'TX_1', name: 'Texas 1', val: 86, pct: 69 },
              { id: 'WI_1', name: 'Wisconsin 1', val: 82, pct: 66 },
            ].map((item) => (
              <div key={item.id} className="space-y-1">
                <div className="flex justify-between text-xs">
                  <span className={`font-semibold ${item.id === selectedStore ? 'text-[#A294F9]' : 'text-[#1F1B2C]'}`}>
                    {item.name} {item.id === selectedStore ? '(Selected)' : ''}
                  </span>
                  <span className="text-[#5F5670] font-medium">{item.val} avg units/day</span>
                </div>
                <div className="h-2 w-full bg-[#F5EFFF] rounded-full overflow-hidden">
                  <div
                    className={`h-full rounded-full transition-all ${item.id === selectedStore ? 'bg-[#A294F9]' : 'bg-[#CDC1FF]'}`}
                    style={{ width: `${item.pct}%` }}
                  />
                </div>
              </div>
            ))}
          </div>
        </section>

        <section className="p-6 rounded-3xl bg-white border border-[#E5D9F2] shadow-xs space-y-4">
          <div>
            <div className="text-xs font-semibold uppercase tracking-wider text-[#8E83A3]">Section C</div>
            <h3 className="text-lg font-bold font-heading text-[#1F1B2C]">Category Share</h3>
            <p className="text-xs text-[#5F5670]">High-level demand distribution in {selectedStore}.</p>
          </div>
          <div className="space-y-3 pt-2">
            {[
              { id: 'FOODS', name: 'Foods & Perishables', share: '68%', color: '#A294F9', count: '1,437 items' },
              { id: 'HOUSEHOLD', name: 'Household Staples', share: '22%', color: '#CDC1FF', count: '1,047 items' },
              { id: 'HOBBIES', name: 'Hobbies & Crafts', share: '10%', color: '#E5D9F2', count: '565 items' },
            ].map((cat) => (
              <div
                key={cat.id}
                className={`p-3.5 rounded-2xl border transition-all ${
                  selectedCategory === cat.id ? 'bg-[#F5EFFF] border-[#CDC1FF] shadow-xs' : 'bg-white border-[#E5D9F2]'
                }`}
              >
                <div className="flex items-center justify-between">
                  <div className="flex items-center gap-2.5">
                    <span className="w-3 h-3 rounded-full" style={{ backgroundColor: cat.color }} />
                    <span className="text-xs font-bold text-[#1F1B2C]">{cat.name}</span>
                  </div>
                  <span className="text-xs font-bold text-[#1F1B2C]">{cat.share}</span>
                </div>
                <div className="text-[11px] text-[#8E83A3] mt-1 pl-5.5">{cat.count} in store inventory</div>
              </div>
            ))}
          </div>
        </section>

        <section className="p-6 rounded-3xl bg-white border border-[#E5D9F2] shadow-xs space-y-4">
          <div>
            <div className="text-xs font-semibold uppercase tracking-wider text-[#8E83A3]">Section D</div>
            <h3 className="text-lg font-bold font-heading text-[#1F1B2C]">Price Movement</h3>
            <p className="text-xs text-[#5F5670]">Historical shelf price changes from sell_prices.csv.</p>
          </div>
          <div className="p-4 rounded-2xl bg-[#F5EFFF]/70 border border-[#E5D9F2] space-y-3">
            <div className="flex items-center justify-between">
              <span className="text-xs text-[#5F5670]">Current Base Price:</span>
              <span className="text-lg font-bold text-[#1F1B2C]">${currentProduct.currentPrice.toFixed(2)}</span>
            </div>
            <div className="flex items-center justify-between text-xs">
              <span className="text-[#5F5670]">Promotional Discount:</span>
              <span className="text-emerald-600 font-semibold">- $0.20 on feature events</span>
            </div>
            <div className="text-[11px] text-[#8E83A3] leading-relaxed pt-2 border-t border-[#E5D9F2]">
              Price elasticity coefficients are automatically included in LightGBM and TFT covariate pipelines.
            </div>
          </div>
        </section>
      </div>
    </div>
  );
}

// ---------------------------------------------------------------------------
// Main Export: Routes between Full-dataset Explorer and Reference Demo
// ---------------------------------------------------------------------------
export default function DataExplorerPage({ onNavigate, uploadedDataset }) {
  if (uploadedDataset?.dataset_id) {
    return <RealDataExplorer uploadedDataset={uploadedDataset} onNavigate={onNavigate} />;
  }
  return <M5DemoExplorer onNavigate={onNavigate} />;
}
