import React, { useState, useEffect, useMemo } from 'react';
import { 
  RotateCw, 
  Loader2, 
  PlayCircle, 
  ShieldAlert,
  Calendar,
  CheckCircle2,
  Clock,
  Layers,
  BarChart3,
  ArrowRight
} from 'lucide-react';
import { getEvaluationFromBackend, runBacktestInBackend } from '../services/api';

/**
 * Dynamically computes chronological rolling-origin fold definitions
 * based on the ACTIVE dataset's actual observation count, date range, and backtest results.
 * Never outputs stale historical indices (e.g. 1773 or 1913) for shorter datasets.
 */
function getFoldVisualizationData(uploadedDataset, evalData, horizon = 28, nFolds = 2) {
  // 1. If evaluation data exists with actual fold records, use the verified fold boundaries
  if (evalData && evalData.series_details && evalData.series_details.length > 0) {
    const matchSeries = evalData.series_details.find(s => s.horizon === horizon) || evalData.series_details[0];
    if (matchSeries && matchSeries.folds && matchSeries.folds.length > 0) {
      const h = matchSeries.horizon || horizon;
      const foldList = matchSeries.folds.filter(f => f.status === 'SUCCESS');
      if (foldList.length > 0) {
        const lastFold = foldList[foldList.length - 1];
        const totalObs = lastFold.train_count && lastFold.test_count 
          ? lastFold.train_count + lastFold.test_count 
          : (uploadedDataset?.profile?.rowsCount || 194);

        return foldList.map((f) => {
          const trainCnt = f.train_count || (totalObs - h);
          const testCnt = f.test_count || h;
          const totalFoldObs = trainCnt + testCnt;
          const trainPct = Math.round((trainCnt / totalFoldObs) * 100);
          const testPct = 100 - trainPct;

          return {
            fold: `Fold ${f.fold}`,
            trainPct: `${trainPct}%`,
            testPct: `${testPct}%`,
            trainDays: `Days 1–${trainCnt} (${f.train_start} to ${f.train_end})`,
            testDays: `Days ${trainCnt + 1}–${trainCnt + testCnt} (${h}D, ${f.forecast_start} to ${f.forecast_end})`,
            trainPeriod: `${f.train_start} to ${f.train_end}`,
            testPeriod: `${f.forecast_start} to ${f.forecast_end}`,
          };
        });
      }
    }
  }

  // 2. If an active dataset is loaded, compute folds from its actual observation count
  if (uploadedDataset?.profile?.rowsCount || uploadedDataset?.rows) {
    const totalRows = uploadedDataset.profile?.rowsCount || uploadedDataset.rows || 194;
    const uniqueSeries = uploadedDataset.profile?.uniqueSeriesCount || 1;
    // Observations per individual series
    const totalDays = uniqueSeries > 0 ? Math.round(totalRows / uniqueSeries) : totalRows;
    const dateRange = uploadedDataset.profile?.dateRange;
    const h = horizon;
    const actualFolds = Math.min(nFolds, Math.max(1, Math.floor((totalDays - h * 2) / h)));
    const folds = [];

    for (let k = 0; k < actualFolds; k++) {
      const testEndIdx = totalDays - (actualFolds - 1 - k) * h;
      const testStartIdx = testEndIdx - h + 1;
      const trainEndIdx = testStartIdx - 1;
      const trainPct = Math.round((trainEndIdx / totalDays) * 100);
      const testPct = Math.round((h / totalDays) * 100);

      folds.push({
        fold: `Fold ${k + 1}${k === actualFolds - 1 ? ' (Current)' : ''}`,
        trainPct: `${trainPct}%`,
        testPct: `${testPct}%`,
        trainDays: `Days 1–${trainEndIdx}${dateRange?.start_date ? ` (from ${dateRange.start_date})` : ''}`,
        testDays: `Days ${testStartIdx}–${testEndIdx} (${h}D Test)`,
        trainPeriod: `Days 1–${trainEndIdx}`,
        testPeriod: `Days ${testStartIdx}–${testEndIdx} (${h}D)`,
      });
    }
    return folds;
  }

  // 3. Fallback when no dataset is uploaded at all
  return [
    { fold: 'Fold 1', trainPct: '70%', testPct: '15%', trainDays: 'Day 1–138', testDays: 'Day 139–166 (28D Test)' },
    { fold: 'Fold 2 (Current)', trainPct: '85%', testPct: '15%', trainDays: 'Day 1–166', testDays: 'Day 167–194 (28D Test)' }
  ];
}

export default function EvaluationPage({ onNavigate, _onNavigate, uploadedDataset }) {
  const navigate = onNavigate || _onNavigate;
  const [evalData, setEvalData] = useState(null);
  const [isBacktesting, setIsBacktesting] = useState(false);
  const [backtestError, setBacktestError] = useState(null);

  // Load cached evaluation whenever dataset changes
  useEffect(() => {
    let isCancelled = false;
    if (uploadedDataset?.dataset_id) {
      getEvaluationFromBackend(uploadedDataset.dataset_id)
        .then(data => {
          if (!isCancelled && data) setEvalData(data);
        })
        .catch(() => {});
    } else {
      setEvalData(null);
    }

    return () => {
      isCancelled = true;
    };
  }, [uploadedDataset?.dataset_id]);

  const handleRunBacktest = async () => {
    if (!uploadedDataset?.dataset_id) return;
    setIsBacktesting(true);
    setBacktestError(null);
    try {
      const res = await runBacktestInBackend(uploadedDataset.dataset_id, {
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

  // Observations per series for active dataset
  const obsPerSeries = useMemo(() => {
    if (!uploadedDataset) return 194;
    const totalRows = uploadedDataset.profile?.rowsCount || uploadedDataset.rows || 194;
    const seriesCount = uploadedDataset.profile?.uniqueSeriesCount || 1;
    return seriesCount > 0 ? Math.round(totalRows / seriesCount) : totalRows;
  }, [uploadedDataset]);

  // Extract individual verified folds from evalData
  const realFolds = useMemo(() => {
    const list = [];
    if (evalData && evalData.series_details) {
      evalData.series_details.forEach(s => {
        if (s.folds) {
          s.folds.forEach(f => {
            if (f.status === 'SUCCESS') {
              list.push({
                fold: `Fold ${f.fold} (${s.series_id})`,
                trainPeriod: `${f.train_start} to ${f.train_end}`,
                testDays: `${s.horizon}D (${f.forecast_start} to ${f.forecast_end})`,
                bestModel: s.model?.toUpperCase(),
                avgMape: f.mape !== null ? `${f.mape}%` : 'N/A',
                avgRmse: f.rmse !== null ? `${f.rmse} units` : 'N/A',
                execTime: f.execution_time_ms ? `${f.execution_time_ms}ms` : '—'
              });
            }
          });
        }
      });
    }
    return list;
  }, [evalData]);

  // Dynamic fold walkthrough visualization
  const foldDiagramSteps = useMemo(() => {
    return getFoldVisualizationData(uploadedDataset, evalData, 28, 2);
  }, [uploadedDataset, evalData]);

  // Helper to resolve evaluated status per horizon in Horizon Consistency Matrix
  const getHorizonEvaluation = (horizonKey) => {
    if (!evalData) return { isEvaluated: false };
    const best = evalData.best_per_horizon?.[horizonKey];
    const mapes = evalData.table_1_model_x_horizon_mape || {};
    const rmses = evalData.table_2_model_x_horizon_rmse || {};

    const modelEntries = Object.keys(mapes)
      .filter(m => mapes[m]?.[horizonKey] != null)
      .map(m => ({
        model: m.toUpperCase(),
        mape: mapes[m][horizonKey],
        rmse: rmses[m]?.[horizonKey] ?? null,
      }))
      .sort((a, b) => a.mape - b.mape);

    const isEvaluated = modelEntries.length > 0;
    return {
      isEvaluated,
      bestModel: best?.best_model?.toUpperCase() || (modelEntries[0]?.model ?? null),
      bestMape: best?.mape ?? (modelEntries[0]?.mape ?? null),
      bestRmse: best?.rmse ?? (modelEntries[0]?.rmse ?? null),
      models: modelEntries,
    };
  };

  const eval7D = getHorizonEvaluation('7D');
  const eval28D = getHorizonEvaluation('28D');
  const eval90D = getHorizonEvaluation('90D');

  return (
    <div className="space-y-8 max-w-7xl mx-auto pb-12">
      {/* Header */}
      <div>
        <div className="text-xs font-semibold uppercase tracking-wider text-[#8E83A3]">
          Methodological Rigor
        </div>
        <h1 className="text-3xl font-bold font-heading text-[#1F1B2C]">
          Evaluation & Backtesting
        </h1>
        <p className="text-sm text-[#5F5670] mt-1 max-w-2xl">
          Understanding model accuracy, temporal out-of-sample backtesting, and performance degradation across 7-day, 28-day, and 90-day forecasting windows.
        </p>
      </div>

      {/* Active Dataset Backtest Context Banner */}
      {uploadedDataset && (
        <div className="p-5 rounded-3xl bg-white border border-[#CDC1FF] shadow-xs flex flex-col sm:flex-row sm:items-center justify-between gap-4">
          <div className="space-y-1">
            <div className="flex items-center gap-2">
              <span className="w-2.5 h-2.5 rounded-full bg-emerald-500 animate-pulse"></span>
              <span className="text-xs font-bold text-[#1F1B2C]">
                Active Dataset: <span className="text-[#A294F9]">{uploadedDataset.profile?.filename || uploadedDataset.filename}</span>
              </span>
            </div>
            <p className="text-[11px] text-[#5F5670]">
              {uploadedDataset.profile?.uniqueSeriesCount || 3} unique series • {obsPerSeries} daily observations per series
              {uploadedDataset.profile?.dateRange?.start_date && ` (${uploadedDataset.profile.dateRange.start_date} to ${uploadedDataset.profile.dateRange.end_date})`}
              {evalData ? ` • Backtest completed across ${evalData.total_series_evaluated} series & ${evalData.models_evaluated?.length || 4} models.` : ' • Backtesting pending.'}
            </p>
          </div>

          <button
            onClick={handleRunBacktest}
            disabled={isBacktesting}
            className="flex items-center gap-2 px-5 py-2.5 rounded-2xl text-xs font-bold text-white bg-[#A294F9] hover:bg-[#8E83A3] transition-all shadow-xs shrink-0 disabled:opacity-60"
          >
            {isBacktesting ? (
              <>
                <Loader2 className="w-3.5 h-3.5 animate-spin" />
                <span>Evaluating Folds...</span>
              </>
            ) : (
              <>
                <PlayCircle className="w-3.5 h-3.5" />
                <span>{evalData ? 'Re-run Dataset Backtest' : 'Run Dataset Backtest'}</span>
              </>
            )}
          </button>
        </div>
      )}

      {/* Human-Friendly Metric Explanations with Active Data Integration */}
      <section className="grid grid-cols-1 md:grid-cols-2 gap-6">
        {/* Metric 1: MAPE */}
        <div className="p-6 rounded-3xl bg-white border border-[#E5D9F2] shadow-xs space-y-3">
          <div className="flex items-center justify-between">
            <div className="flex items-center gap-2">
              <span className="w-8 h-8 rounded-xl bg-[#F5EFFF] text-[#A294F9] font-bold text-xs flex items-center justify-center border border-[#CDC1FF]">
                %
              </span>
              <h2 className="text-lg font-bold font-heading text-[#1F1B2C]">
                MAPE (Mean Absolute Percentage Error)
              </h2>
            </div>
            <span className="text-[11px] px-2.5 py-0.5 rounded-full bg-emerald-100 text-emerald-700 font-semibold">
              Relative Metric
            </span>
          </div>

          <p className="text-xs text-[#5F5670] leading-relaxed">
            <strong>What it tells a planner:</strong> "On average, by what percentage did our predicted demand deviate from the actual units sold?"
          </p>

          <div className="p-3.5 rounded-2xl bg-[#F5EFFF]/70 border border-[#E5D9F2] text-xs space-y-1.5">
            <div className="flex justify-between">
              <span className="text-[#5F5670]">Typical Retail Target:</span>
              <span className="font-semibold text-[#1F1B2C]">&lt; 15% Error</span>
            </div>
            <div className="flex justify-between">
              <span className="text-[#5F5670]">Best Short-term (7D) Evaluated:</span>
              <span className="font-semibold text-[#A294F9]">
                {eval7D.isEvaluated 
                  ? `${eval7D.bestMape}% (${eval7D.bestModel})` 
                  : (evalData?.best_model_overall ? `${evalData.best_model_overall.overall_mape}% (${evalData.best_model_overall.model.toUpperCase()})` : 'Not evaluated yet')}
              </span>
            </div>
            <div className="flex justify-between">
              <span className="text-[#5F5670]">Aggregation Policy:</span>
              <span className="font-medium text-[#1F1B2C]">Sample-weighted across non-zero held-out actuals; zero actuals excluded.</span>
            </div>
          </div>
        </div>

        {/* Metric 2: RMSE */}
        <div className="p-6 rounded-3xl bg-white border border-[#E5D9F2] shadow-xs space-y-3">
          <div className="flex items-center justify-between">
            <div className="flex items-center gap-2">
              <span className="w-8 h-8 rounded-xl bg-[#F5EFFF] text-[#A294F9] font-bold text-xs flex items-center justify-center border border-[#CDC1FF]">
                #
              </span>
              <h2 className="text-lg font-bold font-heading text-[#1F1B2C]">
                RMSE (Root Mean Squared Error)
              </h2>
            </div>
            <span className="text-[11px] px-2.5 py-0.5 rounded-full bg-[#E5D9F2] text-[#A294F9] font-semibold">
              Magnitude Metric
            </span>
          </div>

          <p className="text-xs text-[#5F5670] leading-relaxed">
            <strong>What it tells a planner:</strong> "In absolute product units, how far off are predictions, giving extra weight to large surprising misforecasts?"
          </p>

          <div className="p-3.5 rounded-2xl bg-[#F5EFFF]/70 border border-[#E5D9F2] text-xs space-y-1.5">
            <div className="flex justify-between">
              <span className="text-[#5F5670]">Unit Measurement:</span>
              <span className="font-semibold text-[#1F1B2C]">Cases / Pieces Sold</span>
            </div>
            <div className="flex justify-between">
              <span className="text-[#5F5670]">Best Short-term (7D) Evaluated:</span>
              <span className="font-semibold text-[#A294F9]">
                {eval7D.isEvaluated && eval7D.bestRmse !== null 
                  ? `${eval7D.bestRmse} Units (${eval7D.bestModel})` 
                  : 'Not evaluated yet'}
              </span>
            </div>
            <div className="flex justify-between">
              <span className="text-[#5F5670]">Key Advantage:</span>
              <span className="font-medium text-[#1F1B2C]">Root-mean-square penalizes massive operational stockouts and overstocks.</span>
            </div>
          </div>
        </div>
      </section>

      {/* Section C: Backtesting Rolling Window Workflow */}
      <section className="p-6 lg:p-8 rounded-3xl bg-white border border-[#E5D9F2] shadow-xs space-y-6">
        <div>
          <div className="text-xs font-semibold uppercase tracking-wider text-[#8E83A3]">
            Section C
          </div>
          <h2 className="text-xl font-bold font-heading text-[#1F1B2C]">
            Walk-Forward Rolling Window Backtesting
          </h2>
          <p className="text-xs text-[#5F5670]">
            Time-series data cannot be shuffled randomly. We simulate real enterprise operational conditions using chronological sliding windows across multiple historical folds.
          </p>
        </div>

        {/* Visual Walkthrough Diagram - Strictly Derived from Active Dataset */}
        <div className="p-5 rounded-2xl bg-[#F5EFFF]/50 border border-[#E5D9F2] space-y-4">
          <div className="text-xs font-semibold text-[#1F1B2C] flex items-center justify-between">
            <div className="flex items-center gap-2">
              <RotateCw className="w-4 h-4 text-[#A294F9]" />
              <span>Chronological Validation Strategy ({obsPerSeries} Days Active Series Span)</span>
            </div>
            <span className="text-[11px] text-[#8E83A3]">
              Zero future leakage
            </span>
          </div>

          {/* Dynamic Fold Steps Visual */}
          <div className="space-y-3">
            {foldDiagramSteps.map((f, i) => (
              <div key={i} className="flex flex-col sm:flex-row sm:items-center gap-3 p-3 rounded-xl bg-white border border-[#E5D9F2] text-xs">
                <div className="w-32 font-bold text-[#1F1B2C] shrink-0">{f.fold}</div>
                
                {/* Visual bar split */}
                <div className="w-full flex h-6 rounded-lg overflow-hidden border border-[#CDC1FF]">
                  <div 
                    className="bg-[#E5D9F2] flex items-center justify-center text-[10px] text-[#5F5670] font-medium px-2 truncate"
                    style={{ width: f.trainPct }}
                    title={f.trainDays}
                  >
                    Historical Training ({f.trainDays})
                  </div>
                  <div 
                    className="bg-[#A294F9] flex items-center justify-center text-[10px] text-white font-bold px-2 truncate"
                    style={{ width: f.testPct }}
                    title={f.testDays}
                  >
                    Test ({f.testDays})
                  </div>
                </div>
              </div>
            ))}
          </div>

          <div className="text-[11px] text-[#8E83A3] pt-1">
            * This methodology guarantees zero data leakage: models never observe future calendar, holiday, or price events during training.
          </div>
        </div>

        {backtestError && (
          <div className="p-3.5 rounded-xl bg-rose-50 border border-rose-200 text-rose-700 text-xs flex items-center gap-2">
            <ShieldAlert className="w-4 h-4 shrink-0" />
            <span>{backtestError}</span>
          </div>
        )}

        {/* Backtesting Folds Result Table */}
        <div className="overflow-x-auto">
          {realFolds.length > 0 ? (
            <table className="w-full text-left text-xs border-collapse">
              <thead>
                <tr className="border-b border-[#E5D9F2] text-[#8E83A3] uppercase tracking-wider">
                  <th className="py-3 px-4 font-semibold">Validation Window</th>
                  <th className="py-3 px-4 font-semibold">Training Range</th>
                  <th className="py-3 px-4 font-semibold">Unseen Test Horizon</th>
                  <th className="py-3 px-4 font-semibold">Model Evaluated</th>
                  <th className="py-3 px-4 font-semibold">Window MAPE</th>
                  <th className="py-3 px-4 font-semibold">Window RMSE</th>
                  <th className="py-3 px-4 font-semibold">Latency</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-[#F5EFFF]">
                {realFolds.map((f, i) => (
                  <tr key={i} className="hover:bg-[#F5EFFF]/40 transition-colors">
                    <td className="py-3 px-4 font-bold text-[#1F1B2C]">{f.fold}</td>
                    <td className="py-3 px-4 text-[#5F5670]">{f.trainPeriod}</td>
                    <td className="py-3 px-4 text-[#1F1B2C]">{f.testDays}</td>
                    <td className="py-3 px-4 font-semibold text-[#A294F9]">{f.bestModel}</td>
                    <td className="py-3 px-4 font-semibold text-emerald-600">{f.avgMape}</td>
                    <td className="py-3 px-4 font-semibold text-[#1F1B2C]">{f.avgRmse}</td>
                    <td className="py-3 px-4 text-[#8E83A3] font-mono">{f.execTime}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          ) : (
            <div className="p-8 text-center bg-[#F5EFFF]/30 rounded-2xl border border-dashed border-[#CDC1FF] space-y-2">
              <div className="text-xs font-bold text-[#1F1B2C]">
                {uploadedDataset 
                  ? `No Backtest Results Yet for ${uploadedDataset.profile?.filename || uploadedDataset.filename}` 
                  : 'No Active Dataset Loaded'}
              </div>
              <p className="text-[11px] text-[#5F5670] max-w-md mx-auto">
                {uploadedDataset 
                  ? 'Click "Run Dataset Backtest" above to fit models across rolling folds and compute genuine out-of-sample MAPE and RMSE.' 
                  : 'Upload a dataset to configure and execute rolling-origin backtesting.'}
              </p>
            </div>
          )}
        </div>
      </section>

      {/* Section D: Horizon Consistency Check - Strictly Derived from Actual Evaluations */}
      <section className="p-6 rounded-3xl bg-white border border-[#E5D9F2] shadow-xs space-y-4">
        <div>
          <div className="text-xs font-semibold uppercase tracking-wider text-[#8E83A3]">
            Section D
          </div>
          <h2 className="text-xl font-bold font-heading text-[#1F1B2C]">
            Horizon Consistency Matrix (Short vs Medium vs Long)
          </h2>
          <p className="text-xs text-[#5F5670]">
            Comparing empirical model performance and degradation across 7-day, 28-day, and 90-day planning horizons.
          </p>
        </div>

        <div className="grid grid-cols-1 md:grid-cols-3 gap-4 pt-2">
          {/* Card 1: 7 Days */}
          <div className="p-5 rounded-2xl bg-[#F5EFFF] border border-[#CDC1FF] space-y-3">
            <div className="flex items-center justify-between">
              <span className="text-xs font-bold text-[#A294F9] uppercase tracking-wider">
                Short Horizon (7 Days)
              </span>
              <span className={`text-[10px] font-bold px-2 py-0.5 rounded-full ${
                eval7D.isEvaluated 
                  ? 'bg-emerald-100 text-emerald-800' 
                  : 'bg-gray-100 text-gray-600'
              }`}>
                {eval7D.isEvaluated ? 'Evaluated' : 'Not Evaluated'}
              </span>
            </div>

            <div className="text-sm font-semibold text-[#1F1B2C]">
              Operational Day-to-Day Stability
            </div>

            {eval7D.isEvaluated ? (
              <div className="space-y-2">
                <p className="text-xs text-[#5F5670] leading-relaxed">
                  <strong>Best Model:</strong> <span className="font-bold text-[#1F1B2C]">{eval7D.bestModel}</span> achieved lowest error with <span className="font-bold text-emerald-600">{eval7D.bestMape}% MAPE</span> and {eval7D.bestRmse} RMSE across held-out folds.
                </p>
                <div className="pt-2 border-t border-[#CDC1FF]/60 space-y-1">
                  <div className="text-[10px] uppercase font-bold text-[#8E83A3] tracking-wider mb-1">
                    Evaluated 7D Rankings:
                  </div>
                  {eval7D.models.map(m => (
                    <div key={m.model} className="flex justify-between text-xs text-[#5F5670]">
                      <span className="font-semibold text-[#1F1B2C]">{m.model}</span>
                      <span>{m.mape}% MAPE {m.rmse !== null && `(${m.rmse} RMSE)`}</span>
                    </div>
                  ))}
                </div>
              </div>
            ) : (
              <p className="text-xs text-[#8E83A3] leading-relaxed">
                7-day horizon has not been evaluated for this dataset. Click "Run Dataset Backtest" to compute empirical operational accuracy.
              </p>
            )}
          </div>

          {/* Card 2: 28 Days */}
          <div className="p-5 rounded-2xl bg-[#F5EFFF] border border-[#CDC1FF] space-y-3">
            <div className="flex items-center justify-between">
              <span className="text-xs font-bold text-[#A294F9] uppercase tracking-wider">
                Medium Horizon (28 Days)
              </span>
              <span className={`text-[10px] font-bold px-2 py-0.5 rounded-full ${
                eval28D.isEvaluated 
                  ? 'bg-emerald-100 text-emerald-800' 
                  : 'bg-gray-100 text-gray-600'
              }`}>
                {eval28D.isEvaluated ? 'Evaluated' : 'Not Evaluated'}
              </span>
            </div>

            <div className="text-sm font-semibold text-[#1F1B2C]">
              Tactical Monthly Planning
            </div>

            {eval28D.isEvaluated ? (
              <div className="space-y-2">
                <p className="text-xs text-[#5F5670] leading-relaxed">
                  <strong>Best Model:</strong> <span className="font-bold text-[#1F1B2C]">{eval28D.bestModel}</span> achieved lowest error with <span className="font-bold text-emerald-600">{eval28D.bestMape}% MAPE</span> and {eval28D.bestRmse} RMSE across held-out folds.
                </p>
                <div className="pt-2 border-t border-[#CDC1FF]/60 space-y-1">
                  <div className="text-[10px] uppercase font-bold text-[#8E83A3] tracking-wider mb-1">
                    Evaluated 28D Rankings:
                  </div>
                  {eval28D.models.map(m => (
                    <div key={m.model} className="flex justify-between text-xs text-[#5F5670]">
                      <span className="font-semibold text-[#1F1B2C]">{m.model}</span>
                      <span>{m.mape}% MAPE {m.rmse !== null && `(${m.rmse} RMSE)`}</span>
                    </div>
                  ))}
                </div>
              </div>
            ) : (
              <p className="text-xs text-[#8E83A3] leading-relaxed">
                28-day horizon has not been evaluated for this dataset. Click "Run Dataset Backtest" to compute tactical monthly accuracy.
              </p>
            )}
          </div>

          {/* Card 3: 90 Days */}
          <div className="p-5 rounded-2xl bg-[#F5EFFF] border border-[#CDC1FF] space-y-3">
            <div className="flex items-center justify-between">
              <span className="text-xs font-bold text-[#A294F9] uppercase tracking-wider">
                Long Horizon (90 Days)
              </span>
              <span className={`text-[10px] font-bold px-2 py-0.5 rounded-full ${
                eval90D.isEvaluated 
                  ? 'bg-emerald-100 text-emerald-800' 
                  : 'bg-amber-100 text-amber-800'
              }`}>
                {eval90D.isEvaluated ? 'Evaluated' : 'Not Evaluated'}
              </span>
            </div>

            <div className="text-sm font-semibold text-[#1F1B2C]">
              Strategic Quarterly Outlook
            </div>

            {eval90D.isEvaluated ? (
              <div className="space-y-2">
                <p className="text-xs text-[#5F5670] leading-relaxed">
                  <strong>Best Model:</strong> <span className="font-bold text-[#1F1B2C]">{eval90D.bestModel}</span> achieved {eval90D.bestMape}% MAPE and {eval90D.bestRmse} RMSE.
                </p>
                <div className="pt-2 border-t border-[#CDC1FF]/60 space-y-1">
                  {eval90D.models.map(m => (
                    <div key={m.model} className="flex justify-between text-xs text-[#5F5670]">
                      <span className="font-semibold text-[#1F1B2C]">{m.model}</span>
                      <span>{m.mape}% MAPE</span>
                    </div>
                  ))}
                </div>
              </div>
            ) : (
              <div className="space-y-1.5 text-xs text-[#5F5670]">
                <p className="leading-relaxed">
                  {obsPerSeries < 270 
                    ? `Requires at least 270 historical observations (active series has ${obsPerSeries} days). Not evaluated for this dataset.`
                    : '90-day strategic horizon has not been evaluated for this dataset.'}
                </p>
                <div className="text-[11px] text-[#8E83A3]">
                  No benchmark claims are fabricated for unevaluated horizons.
                </div>
              </div>
            )}
          </div>
        </div>

        {/* Horizon Degradation Summary */}
        {eval7D.isEvaluated && eval28D.isEvaluated && (
          <div className="p-4 rounded-2xl bg-[#F5EFFF]/70 border border-[#CDC1FF] text-xs text-[#1F1B2C] flex items-center gap-3">
            <BarChart3 className="w-4 h-4 text-[#A294F9] shrink-0" />
            <div>
              <span className="font-bold">Empirical Horizon Degradation: </span>
              {`Across common evaluated models, short-term error averages ${
                Math.round(eval7D.models.reduce((acc, m) => acc + m.mape, 0) / eval7D.models.length * 10) / 10
              }% MAPE at 7D and steps to ${
                Math.round(eval28D.models.reduce((acc, m) => acc + m.mape, 0) / eval28D.models.length * 10) / 10
              }% MAPE at 28D.`}
            </div>
          </div>
        )}

        {/* Workflow Progression: Step 2 -> Step 3 (Model Comparison) */}
        <div className="p-5 rounded-2xl bg-white border border-[#E5D9F2] shadow-xs flex flex-col sm:flex-row sm:items-center justify-between gap-4 mt-6">
          <div>
            <div className="text-xs font-bold text-[#1F1B2C]">
              Step 2 Completed: Evaluation & Backtesting
            </div>
            <p className="text-xs text-[#5F5670] mt-0.5">
              Proceed to compare model architectures across horizons and select the winning model for demand forecasting.
            </p>
          </div>
          <button
            onClick={() => navigate && navigate('comparison')}
            className="px-5 py-2.5 rounded-xl bg-[#A294F9] text-white hover:bg-[#9181f7] text-xs font-semibold transition-colors shadow-xs flex items-center gap-2 shrink-0"
            data-testid="continue-to-comparison-step-btn"
          >
            <span>Proceed to Model Comparison (Step 3)</span>
            <ArrowRight className="w-3.5 h-3.5" />
          </button>
        </div>
      </section>
    </div>
  );
}
