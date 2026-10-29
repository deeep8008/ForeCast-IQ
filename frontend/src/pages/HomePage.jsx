import React, { useState, useMemo } from 'react';
import { 
  ArrowRight, 
  Sparkles, 
  Clock, 
  Cpu, 
  Database, 
  Target, 
  ChevronRight
} from 'lucide-react';
import ForecastChart from '../components/ForecastChart';
import { 
  STORES, 
  PRODUCTS, 
  MODELS, 
  generateTimeSeries, 
  FORECAST_DRIVERS 
} from '../data/mockData';

export default function HomePage({ onNavigate }) {
  const [selectedStore, setSelectedStore] = useState('CA_1');
  const [selectedProduct, setSelectedProduct] = useState('FOODS_3_090');
  const [selectedModel, setSelectedModel] = useState('tft');
  const [selectedHorizon, setSelectedHorizon] = useState(28);

  const seriesData = useMemo(() => {
    return generateTimeSeries(selectedStore, selectedProduct, selectedModel, selectedHorizon);
  }, [selectedStore, selectedProduct, selectedModel, selectedHorizon]);

  return (
    <div className="space-y-8 max-w-7xl mx-auto pb-12">
      {/* Hero Section */}
      <section className="relative overflow-hidden rounded-3xl bg-white border border-[#E5D9F2] p-8 lg:p-10 shadow-xs">
        <div className="absolute top-0 right-0 -mt-10 -mr-10 w-96 h-96 bg-gradient-to-br from-[#F5EFFF] via-[#E5D9F2]/50 to-transparent rounded-full blur-2xl pointer-events-none"></div>

        <div className="relative z-10 grid grid-cols-1 lg:grid-cols-12 gap-8 items-center">
          {/* Hero Left Content */}
          <div className="lg:col-span-7 space-y-4">
            <div className="inline-flex items-center gap-2 px-3.5 py-1.5 rounded-full bg-[#F5EFFF] border border-[#CDC1FF] text-xs font-bold uppercase tracking-wider text-[#A294F9]">
              <Sparkles className="w-3.5 h-3.5" />
              <span>Enterprise AI Engine</span>
            </div>

            <div>
              <h1 className="text-4xl sm:text-5xl lg:text-6xl font-black font-heading text-[#1F1B2C] tracking-tight leading-tight">
                Forecast<span className="text-[#A294F9]">-IQ</span>
              </h1>
              <p className="text-xl sm:text-2xl lg:text-3xl font-extrabold text-[#5F5670] mt-1 tracking-tight">
                See what demand looks like <span className="text-[#A294F9]">next.</span>
              </p>
            </div>

            <p className="text-base sm:text-lg text-[#5F5670] leading-relaxed max-w-xl pt-1">
              Generate short-, medium-, and long-term demand forecasts to support inventory, staffing, and enterprise planning across retail tiers.
            </p>

            <div className="flex flex-wrap items-center gap-3 pt-2">
              <button
                onClick={() => onNavigate('upload')}
                className="inline-flex items-center gap-2 px-6 py-3 rounded-xl bg-[#A294F9] text-white font-semibold text-sm hover:bg-[#9181f7] shadow-sm hover:shadow transition-all"
                data-testid="hero-start-workflow-btn"
              >
                <span>Start Forecasting Workflow →</span>
                <ArrowRight className="w-4 h-4" />
              </button>

              <button
                onClick={() => onNavigate('forecast')}
                className="inline-flex items-center gap-2 px-6 py-3 rounded-xl bg-[#F5EFFF] text-[#1F1B2C] font-semibold text-sm hover:bg-[#E5D9F2] border border-[#CDC1FF] transition-all"
                data-testid="hero-generate-forecast-btn"
              >
                <span>Generate Forecast</span>
              </button>
            </div>
          </div>

          {/* Hero Right Visual: Abstract Analytical Forecast Preview */}
          <div className="lg:col-span-5">
            <div className="p-5 rounded-2xl bg-[#F5EFFF]/60 border border-[#E5D9F2] shadow-xs space-y-3">
              <div className="flex items-center justify-between text-xs text-[#5F5670]">
                <span className="font-semibold text-[#1F1B2C]">Live Architecture Pipeline</span>
                <span className="text-[11px] px-2 py-0.5 rounded-full bg-emerald-100 text-emerald-700 font-medium">
                  Verified Clean Split
                </span>
              </div>

              {/* Multi-horizon step badges */}
              <div className="grid grid-cols-3 gap-2 text-center">
                <div className="p-2.5 rounded-xl bg-white border border-[#E5D9F2]">
                  <div className="text-[11px] text-[#8E83A3]">Short</div>
                  <div className="font-bold text-sm text-[#1F1B2C]">7 Days</div>
                  <div className="text-[10px] text-[#5F5670]">Replenish</div>
                </div>
                <div className="p-2.5 rounded-xl bg-white border border-[#CDC1FF] shadow-xs">
                  <div className="text-[11px] text-[#A294F9] font-medium">Medium</div>
                  <div className="font-bold text-sm text-[#A294F9]">28 Days</div>
                  <div className="text-[10px] text-[#5F5670]">Staffing</div>
                </div>
                <div className="p-2.5 rounded-xl bg-white border border-[#E5D9F2]">
                  <div className="text-[11px] text-[#8E83A3]">Long</div>
                  <div className="font-bold text-sm text-[#1F1B2C]">90 Days</div>
                  <div className="text-[10px] text-[#5F5670]">Strategy</div>
                </div>
              </div>

              {/* Minimal waveform illustration */}
              <div className="h-20 w-full pt-2 flex items-end justify-between gap-1 px-1">
                {[30, 45, 60, 40, 75, 50, 85, 65, 90, 80, 70, 95, 88, 76, 85, 92, 105, 98, 110, 118].map((h, i) => (
                  <div 
                    key={i} 
                    className={`w-full rounded-t-xs transition-all ${
                      i >= 14 ? 'bg-[#A294F9]' : 'bg-[#CDC1FF]'
                    }`}
                    style={{ height: `${(h / 120) * 100}%` }}
                  />
                ))}
              </div>

              <div className="flex items-center justify-between text-[11px] text-[#8E83A3] pt-1">
                <span>← 90D History</span>
                <span className="text-[#A294F9] font-medium">Multi-Horizon Projection →</span>
              </div>
            </div>
          </div>
        </div>
      </section>

      {/* 4 Clean KPI Cards */}
      <section className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4">
        {/* Card 1 */}
        <div className="p-5 rounded-2xl bg-white border border-[#E5D9F2] shadow-xs space-y-2 hover:border-[#CDC1FF] transition-colors">
          <div className="flex items-center justify-between">
            <span className="text-xs font-semibold uppercase tracking-wider text-[#8E83A3]">
              Forecast Horizons
            </span>
            <div className="p-1.5 rounded-lg bg-[#F5EFFF] text-[#A294F9]">
              <Clock className="w-4 h-4" />
            </div>
          </div>
          <div className="text-2xl font-bold font-heading text-[#1F1B2C]">
            7D <span className="text-[#CDC1FF]">|</span> 28D <span className="text-[#CDC1FF]">|</span> 90D
          </div>
          <p className="text-xs text-[#5F5670]">
            Operational, tactical & strategic decision windows.
          </p>
        </div>

        {/* Card 2 */}
        <div className="p-5 rounded-2xl bg-white border border-[#E5D9F2] shadow-xs space-y-2 hover:border-[#CDC1FF] transition-colors">
          <div className="flex items-center justify-between">
            <span className="text-xs font-semibold uppercase tracking-wider text-[#8E83A3]">
              Forecast Models
            </span>
            <div className="p-1.5 rounded-lg bg-[#F5EFFF] text-[#A294F9]">
              <Cpu className="w-4 h-4" />
            </div>
          </div>
          <div className="text-lg font-bold font-heading text-[#1F1B2C] leading-snug">
            ARIMA • SARIMA • Prophet • LightGBM • DeepAR • TFT
          </div>
          <p className="text-xs text-[#5F5670]">
            Statistical, seasonal, tree-based ML & deep attention networks.
          </p>
        </div>

        {/* Card 3 */}
        <div className="p-5 rounded-2xl bg-white border border-[#E5D9F2] shadow-xs space-y-2 hover:border-[#CDC1FF] transition-colors">
          <div className="flex items-center justify-between">
            <span className="text-xs font-semibold uppercase tracking-wider text-[#8E83A3]">
              Active Series
            </span>
            <div className="p-1.5 rounded-lg bg-[#F5EFFF] text-[#A294F9]">
              <Database className="w-4 h-4" />
            </div>
          </div>
          <div className="text-2xl font-bold font-heading text-[#1F1B2C]">
            42,840
          </div>
          <p className="text-xs text-[#5F5670]">
            Product-store granular series across 10 retail locations.
          </p>
        </div>

        {/* Card 4 */}
        <div className="p-5 rounded-2xl bg-white border border-[#E5D9F2] shadow-xs space-y-2 hover:border-[#CDC1FF] transition-colors">
          <div className="flex items-center justify-between">
            <span className="text-xs font-semibold uppercase tracking-wider text-[#8E83A3]">
              Evaluation Metrics
            </span>
            <div className="p-1.5 rounded-lg bg-[#F5EFFF] text-[#A294F9]">
              <Target className="w-4 h-4" />
            </div>
          </div>
          <div className="text-2xl font-bold font-heading text-[#1F1B2C]">
            MAPE & RMSE
          </div>
          <p className="text-xs text-[#5F5670]">
            Percentage error and magnitude backtested on unseen folds.
          </p>
        </div>
      </section>

      {/* Main Visual: Actual vs Forecast Interactive Section */}
      <section className="rounded-3xl bg-white border border-[#E5D9F2] p-6 lg:p-8 shadow-xs space-y-6">
        <div className="flex flex-col md:flex-row md:items-center justify-between gap-4 pb-4 border-b border-[#F5EFFF]">
          <div>
            <div className="text-xs font-semibold uppercase tracking-wider text-[#8E83A3]">
              Interactive Forecasting Engine
            </div>
            <h2 className="text-2xl font-bold font-heading text-[#1F1B2C]">
              Actual vs Forecast
            </h2>
            <p className="text-sm text-[#5F5670]">
              Daily demand trajectory for the selected product-store series with confidence bands.
            </p>
          </div>

          {/* Interactive Selector Controls */}
          <div className="flex flex-wrap items-center gap-2.5">
            {/* Store Select */}
            <div className="flex items-center gap-1.5 bg-[#F5EFFF] px-3 py-1.5 rounded-xl border border-[#E5D9F2] text-xs">
              <span className="text-[#8E83A3] font-medium">Store:</span>
              <select
                value={selectedStore}
                onChange={(e) => setSelectedStore(e.target.value)}
                className="bg-transparent font-semibold text-[#1F1B2C] outline-none cursor-pointer"
              >
                {STORES.map(s => (
                  <option key={s.id} value={s.id}>{s.id} ({s.state})</option>
                ))}
              </select>
            </div>

            {/* Product Select */}
            <div className="flex items-center gap-1.5 bg-[#F5EFFF] px-3 py-1.5 rounded-xl border border-[#E5D9F2] text-xs">
              <span className="text-[#8E83A3] font-medium">Product:</span>
              <select
                value={selectedProduct}
                onChange={(e) => setSelectedProduct(e.target.value)}
                className="bg-transparent font-semibold text-[#1F1B2C] outline-none cursor-pointer max-w-[140px] truncate"
              >
                {PRODUCTS.map(p => (
                  <option key={p.id} value={p.id}>{p.id} - {p.name}</option>
                ))}
              </select>
            </div>

            {/* Model Select */}
            <div className="flex items-center gap-1.5 bg-[#F5EFFF] px-3 py-1.5 rounded-xl border border-[#E5D9F2] text-xs">
              <span className="text-[#8E83A3] font-medium">Model:</span>
              <select
                value={selectedModel}
                onChange={(e) => setSelectedModel(e.target.value)}
                className="bg-transparent font-semibold text-[#1F1B2C] outline-none cursor-pointer"
              >
                {MODELS.map(m => (
                  <option key={m.id} value={m.id}>{m.name}</option>
                ))}
              </select>
            </div>
          </div>
        </div>

        {/* Forecast Chart */}
        <ForecastChart
          history={seriesData.history}
          forecast={seriesData.forecast}
          todayDate={seriesData.todayDate}
          horizonDays={selectedHorizon}
          onHorizonChange={setSelectedHorizon}
          showHorizonSwitch={true}
          storeName={seriesData.store.id}
          productName={seriesData.product.name}
        />

        {/* Quick Performance Indicators */}
        <div className="grid grid-cols-2 sm:grid-cols-4 gap-3 pt-2">
          <div className="p-3.5 rounded-xl bg-[#F5EFFF]/70 border border-[#E5D9F2] text-center">
            <div className="text-[11px] text-[#8E83A3]">Active Horizon</div>
            <div className="font-bold text-base text-[#1F1B2C]">{selectedHorizon} Days</div>
          </div>
          <div className="p-3.5 rounded-xl bg-[#F5EFFF]/70 border border-[#E5D9F2] text-center">
            <div className="text-[11px] text-[#8E83A3]">Total Projected Units</div>
            <div className="font-bold text-base text-[#1F1B2C]">{seriesData.summary.totalDemand}</div>
          </div>
          <div className="p-3.5 rounded-xl bg-[#F5EFFF]/70 border border-[#E5D9F2] text-center">
            <div className="text-[11px] text-[#8E83A3]">Backtested MAPE</div>
            <div className="font-bold text-base text-[#A294F9]">{seriesData.mape}%</div>
          </div>
          <div className="p-3.5 rounded-xl bg-[#F5EFFF]/70 border border-[#E5D9F2] text-center">
            <div className="text-[11px] text-[#8E83A3]">Backtested RMSE</div>
            <div className="font-bold text-base text-[#1F1B2C]">{seriesData.rmse} units</div>
          </div>
        </div>
      </section>

      {/* "What Changed?" Plain-Language Business Driver Section */}
      <section className="space-y-4">
        <div>
          <div className="text-xs font-semibold uppercase tracking-wider text-[#8E83A3]">
            Explanatory Intelligence
          </div>
          <h2 className="text-2xl font-bold font-heading text-[#1F1B2C]">
            What changed?
          </h2>
          <p className="text-sm text-[#5F5670]">
            Plain-language summary of demand drivers behind current projections, avoiding black-box ML jargon.
          </p>
        </div>

        <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
          {FORECAST_DRIVERS.map((driver) => (
            <div 
              key={driver.id} 
              className="p-5 rounded-2xl bg-white border border-[#E5D9F2] shadow-xs space-y-3 hover:border-[#CDC1FF] transition-all"
            >
              <div className="flex items-center justify-between">
                <span className="text-xs font-semibold px-2.5 py-1 rounded-full bg-[#F5EFFF] text-[#A294F9] border border-[#CDC1FF]">
                  {driver.badge}
                </span>
                <span className="text-[11px] text-[#8E83A3]">Verified Signal</span>
              </div>
              <h3 className="font-semibold text-base text-[#1F1B2C]">
                {driver.title}
              </h3>
              <p className="text-xs sm:text-sm text-[#5F5670] leading-relaxed">
                {driver.description}
              </p>
            </div>
          ))}
        </div>
      </section>

      {/* Direct Quick Nav to Next Steps */}
      <section className="p-6 rounded-2xl bg-gradient-to-r from-white via-[#F5EFFF]/50 to-white border border-[#E5D9F2] flex flex-col sm:flex-row items-center justify-between gap-4">
        <div>
          <div className="font-bold text-base text-[#1F1B2C]">
            Ready to evaluate alternative forecasting models?
          </div>
          <div className="text-xs text-[#5F5670]">
            Compare statistical ARIMA vs Tabular LightGBM vs Temporal Fusion Transformer across 7D, 28D, and 90D horizons.
          </div>
        </div>
        <button
          onClick={() => onNavigate('comparison')}
          className="inline-flex items-center gap-2 px-5 py-2.5 rounded-xl bg-[#A294F9] text-white text-xs font-semibold hover:bg-[#9181f7] shadow-xs transition-colors shrink-0"
        >
          <span>Compare All 6 Models</span>
          <ChevronRight className="w-4 h-4" />
        </button>
      </section>
    </div>
  );
}
