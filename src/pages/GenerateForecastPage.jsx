import React, { useState, useMemo, useRef } from 'react';
import { 
  Upload, 
  FolderUp, 
  FileSpreadsheet, 
  Sparkles, 
  ArrowRight, 
  Check, 
  Database, 
  Lock, 
  Cpu, 
  Target, 
  TrendingUp, 
  Download, 
  Play, 
  AlertCircle,
  Scissors,
  CheckCircle2,
  Calendar,
  Layers,
  Zap,
  RefreshCw
} from 'lucide-react';
import ForecastChart from '../components/ForecastChart';
import { useDataset } from '../context/DatasetContext';

const modelColors = {
  arima: '#3B82F6',
  prophet: '#10B981',
  lightgbm: '#F59E0B',
  deepar: '#8B5CF6',
  tft: '#EC4899',
  ARIMA: '#3B82F6',
  Prophet: '#10B981',
  LightGBM: '#F59E0B',
  DeepAR: '#8B5CF6',
  TFT: '#EC4899',
};

export default function GenerateForecastPage({ onNavigate }) {
  const { 
    activeDatasetId, 
    datasetSummary, 
    benchmarkResults, 
    selectedModel, 
    setSelectedModel, 
    selectedHorizon, 
    setSelectedHorizon, 
    selectedSeriesId, 
    setSelectedSeriesId,
    currentInventory,
    setCurrentInventory,
    forecastResult, 
    uploadFiles,
    mapAndProcessSchema,
    preloadM5Dataset,
    resetWorkflow,
    uploadPreview,
    setUploadPreview,
    runBenchmark,
    runFutureForecast, 
    exportForecastToCsv,
    isLoading,
    loadingMessage,
    error,
    clearError,
    backendOnline
  } = useDataset();

  // Local Upload State
  const [selectedFiles, setSelectedFiles] = useState([]);
  const [datasetName, setDatasetName] = useState('');
  const [uploadWarning, setUploadWarning] = useState('');
  const [dragActive, setDragActive] = useState(false);

  // Column Mapping State
  const [timeCol, setTimeCol] = useState('');
  const [targetCol, setTargetCol] = useState('');
  const [seriesCol, setSeriesCol] = useState('');
  const [secondarySeriesCol, setSecondarySeriesCol] = useState('');

  // Future Forecast Options
  const [localHorizon, setLocalHorizon] = useState(selectedHorizon || 28);
  const [localInventory, setLocalInventory] = useState(currentInventory || '');

  const fileInputRef = useRef(null);
  const folderInputRef = useRef(null);

  // --- Handlers for File & Folder Upload ---
  const handleDrag = (e) => {
    e.preventDefault();
    e.stopPropagation();
    if (e.type === 'dragenter' || e.type === 'dragover') {
      setDragActive(true);
    } else if (e.type === 'dragleave') {
      setDragActive(false);
    }
  };

  const handleDrop = (e) => {
    e.preventDefault();
    e.stopPropagation();
    setDragActive(false);
    if (e.dataTransfer.files && e.dataTransfer.files.length > 0) {
      processSelectedFiles(Array.from(e.dataTransfer.files));
    }
  };

  const handleFileChange = (e) => {
    if (e.target.files && e.target.files.length > 0) {
      processSelectedFiles(Array.from(e.target.files));
    }
  };

  const processSelectedFiles = (files) => {
    setUploadWarning('');
    clearError();
    const csvFiles = files.filter(f => f.name.toLowerCase().endsWith('.csv'));
    if (csvFiles.length === 0) {
      setUploadWarning('No .csv files found in your selection. Please select one or more .csv files.');
      setSelectedFiles([]);
      return;
    }
    setSelectedFiles(files);
    if (!datasetName && files.length > 0) {
      const base = files[0].name.replace(/\.[^/.]+$/, "");
      setDatasetName(base);
    }
  };

  const handleUploadSubmit = async () => {
    if (selectedFiles.length === 0) {
      setUploadWarning('Please select at least one CSV file first.');
      return;
    }
    try {
      const preview = await uploadFiles(selectedFiles, datasetName);
      if (preview && preview.available_columns) {
        // Auto-guess columns cleanly without collisions
        const cols = preview.available_columns;
        const autoTime = cols.find(c => /^(date|timestamp|time|ds|day)$/i.test(c)) || cols.find(c => /date|time|timestamp/i.test(c)) || cols[0] || '';
        const nonTimeCols = cols.filter(c => c !== autoTime);

        const autoTarget = nonTimeCols.find(c => /sales|weekly_sales|units|demand|volume|qty|target/i.test(c)) || nonTimeCols[0] || '';
        const nonTargetCols = nonTimeCols.filter(c => c !== autoTarget);

        const autoSecondary = nonTargetCols.find(c => /store|branch|shop|location|warehouse|state/i.test(c)) || '';
        const remainingCols = nonTargetCols.filter(c => c !== autoSecondary);

        const autoSeries = remainingCols.find(c => /dept|department|item|product|sku|part|material|id$/i.test(c)) || '';

        setTimeCol(autoTime);
        setTargetCol(autoTarget);
        setSeriesCol(autoSeries);
        setSecondarySeriesCol(autoSecondary);
      }
    } catch {
      // Error handled in context
    }
  };

  const handleConfirmMapping = async () => {
    if (!timeCol || !targetCol) {
      setUploadWarning('Please select both a Timestamp column and a Target demand column.');
      return;
    }
    try {
      await mapAndProcessSchema({
        dataset_id: uploadPreview.dataset_id,
        time_column: timeCol,
        target_column: targetCol,
        series_id_column: seriesCol ? seriesCol : null,
        secondary_series_id_column: secondarySeriesCol ? secondarySeriesCol : null,
        dynamic_covariates: [],
        static_covariates: []
      });
      setSelectedFiles([]);
      setUploadPreview(null);
    } catch {
      // Error handled in context
    }
  };

  const handleUploadAnother = () => {
    resetWorkflow();
    setSelectedFiles([]);
    setDatasetName('');
    setUploadWarning('');
    setUploadPreview(null);
    setTimeCol('');
    setTargetCol('');
    setSeriesCol('');
    setSecondarySeriesCol('');
  };

  // --- Handlers for Backtesting Benchmark ---
  const handleRunBenchmark = async (e) => {
    if (e && e.preventDefault) e.preventDefault();
    try {
      await runBenchmark();
    } catch (err) {
      console.error('Benchmark execution error:', err);
    }
  };

  // --- Handlers for Future Forecasting ---
  const handleExecuteFutureForecast = async (e) => {
    if (e && e.preventDefault) e.preventDefault();
    setSelectedHorizon(localHorizon);
    setCurrentInventory(localInventory);
    try {
      await runFutureForecast(selectedModel, localHorizon, selectedSeriesId, localInventory);
    } catch (err) {
      console.error('Future forecast execution error:', err);
    }
  };

  // Chart data formatting
  const chartHistory = useMemo(() => {
    if (datasetSummary?.sample_records && Array.isArray(datasetSummary.sample_records)) {
      return datasetSummary.sample_records.map(r => ({
        date: r.timestamp || '',
        sales: Number(r.target || 0),
      }));
    }
    return [];
  }, [datasetSummary]);

  const leaderboard = benchmarkResults?.leaderboard || [];
  const testActuals = benchmarkResults?.test_actuals || [];
  const testTimestamps = benchmarkResults?.test_timestamps || [];
  const modelPredictions = benchmarkResults?.model_predictions || {};
  const splitInfo = benchmarkResults?.split_info;

  // Chart max
  const chartMax = useMemo(() => {
    let max = 0;
    testActuals.forEach(v => { if (v > max) max = v; });
    Object.values(modelPredictions).forEach(preds => {
      preds.forEach(v => { if (v > max) max = v; });
    });
    return Math.ceil((max * 1.15) / 10) * 10 || 100;
  }, [testActuals, modelPredictions]);

  return (
    <div className="space-y-10 max-w-6xl mx-auto pb-16">
      {/* Title */}
      <div>
        <div className="text-xs font-semibold uppercase tracking-wider text-[#8E83A3]">
          End-to-End Demand Pipeline
        </div>
        <h1 className="text-3xl font-bold font-heading text-[#1F1B2C]">
          Generate Forecast & Model Evaluation
        </h1>
        <p className="text-sm text-[#5F5670] mt-1 max-w-2xl">
          Upload any time-series dataset, evaluate all 5 models chronologically on hidden test data, and retrain on 100% of historical data to project future demand.
        </p>
      </div>

      {/* Global Alerts */}
      {(error || uploadWarning) && (
        <div className="p-4 rounded-2xl bg-rose-50 border border-rose-200 text-rose-800 text-xs flex items-center justify-between">
          <div className="flex items-center gap-2">
            <AlertCircle className="w-4 h-4 text-rose-600 shrink-0" />
            <span>{error || uploadWarning}</span>
          </div>
          <button 
            type="button"
            onClick={() => { clearError(); setUploadWarning(''); }}
            className="text-rose-600 hover:text-rose-900 font-bold"
          >
            ✕
          </button>
        </div>
      )}

      {/* ========================================================================= */}
      {/* SECTION 1: UPLOAD DATASET OR FOLDER */}
      {/* ========================================================================= */}
      <section className="p-6 sm:p-8 rounded-3xl bg-white border border-[#E5D9F2] shadow-xs space-y-6">
        <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4 pb-4 border-b border-[#F5EFFF]">
          <div>
            <div className="text-xs font-semibold uppercase tracking-wider text-[#A294F9]">
              Step 1
            </div>
            <h2 className="text-xl font-bold font-heading text-[#1F1B2C]">
              Upload Dataset or Multi-CSV Folder
            </h2>
            <p className="text-xs text-[#5F5670]">
              Upload a single CSV file or an entire folder of CSVs to forecast demand.
            </p>
          </div>

          <button
            type="button"
            onClick={handleUploadAnother}
            disabled={isLoading}
            className="inline-flex items-center gap-2 px-4 py-2.5 rounded-xl bg-[#F5EFFF] text-[#A294F9] border border-[#CDC1FF] text-xs font-bold hover:bg-[#E5D9F2] shadow-xs transition-colors cursor-pointer shrink-0"
            title="Reset and upload another dataset"
          >
            <RefreshCw className="w-4 h-4" />
            <span>Upload Another Dataset</span>
          </button>
        </div>

        {/* Upload Dropzone */}
        {!uploadPreview && (
          <div className="space-y-4">
            <div
              onDragEnter={handleDrag}
              onDragLeave={handleDrag}
              onDragOver={handleDrag}
              onDrop={handleDrop}
              className={`p-8 border-2 border-dashed rounded-3xl text-center transition-all ${
                dragActive 
                  ? 'border-[#A294F9] bg-[#F5EFFF]' 
                  : 'border-[#CDC1FF] bg-[#F5EFFF]/30 hover:bg-[#F5EFFF]/60'
              }`}
            >
              <div className="w-12 h-12 mx-auto rounded-2xl bg-white text-[#A294F9] border border-[#CDC1FF] flex items-center justify-center shadow-xs mb-3">
                <Upload className="w-6 h-6" />
              </div>
              <h3 className="text-sm font-bold text-[#1F1B2C]">
                Drag and drop CSV file(s) or entire dataset folder
              </h3>
              <p className="text-xs text-[#5F5670] mt-1 max-w-sm mx-auto">
                Supports single-CSV sales time-series or multi-file directories. Non-CSV files are safely excluded.
              </p>

              <div className="flex flex-wrap items-center justify-center gap-3 mt-4">
                <button
                  type="button"
                  onClick={() => fileInputRef.current?.click()}
                  className="px-4 py-2 rounded-xl bg-white border border-[#CDC1FF] text-xs font-semibold text-[#1F1B2C] hover:bg-[#F5EFFF] shadow-xs cursor-pointer flex items-center gap-2"
                >
                  <FileSpreadsheet className="w-4 h-4 text-[#A294F9]" />
                  <span>Choose CSV File(s)</span>
                </button>

                <button
                  type="button"
                  onClick={() => folderInputRef.current?.click()}
                  className="px-4 py-2 rounded-xl bg-white border border-[#CDC1FF] text-xs font-semibold text-[#1F1B2C] hover:bg-[#F5EFFF] shadow-xs cursor-pointer flex items-center gap-2"
                >
                  <FolderUp className="w-4 h-4 text-[#A294F9]" />
                  <span>Choose Folder</span>
                </button>

                <input
                  ref={fileInputRef}
                  type="file"
                  multiple
                  accept=".csv"
                  onChange={handleFileChange}
                  className="hidden"
                />
                <input
                  ref={folderInputRef}
                  type="file"
                  webkitdirectory="true"
                  directory="true"
                  multiple
                  onChange={handleFileChange}
                  className="hidden"
                />
              </div>
            </div>

            {/* Selected files preview */}
            {selectedFiles.length > 0 && (
              <div className="p-4 rounded-2xl bg-[#F5EFFF] border border-[#E5D9F2] space-y-3">
                <div className="flex items-center justify-between text-xs font-semibold text-[#1F1B2C]">
                  <span>Files Selected: {selectedFiles.length}</span>
                  <span className="text-emerald-700 font-bold">
                    {selectedFiles.filter(f => f.name.endsWith('.csv')).length} valid CSV file(s)
                  </span>
                </div>

                <div className="flex flex-wrap items-center gap-3">
                  <input
                    type="text"
                    placeholder="Dataset Name (optional)"
                    value={datasetName}
                    onChange={(e) => setDatasetName(e.target.value)}
                    className="flex-1 min-w-[200px] bg-white border border-[#CDC1FF] rounded-xl px-3 py-2 text-xs font-semibold text-[#1F1B2C] outline-none"
                  />
                  <button
                    type="button"
                    onClick={handleUploadSubmit}
                    disabled={isLoading}
                    className="px-5 py-2 rounded-xl bg-[#A294F9] text-white text-xs font-bold hover:bg-[#9181f7] shadow-xs cursor-pointer flex items-center gap-2"
                  >
                    <span>Upload & Map Columns</span>
                    <ArrowRight className="w-3.5 h-3.5" />
                  </button>
                </div>
              </div>
            )}
          </div>
        )}

        {/* Column Mapping Interface */}
        {uploadPreview && (
          <div className="space-y-4 p-5 rounded-2xl bg-[#F5EFFF]/50 border border-[#CDC1FF]">
            <div className="flex items-center justify-between">
              <div>
                <div className="text-xs font-bold text-[#1F1B2C]">
                  Map Columns for: {uploadPreview.dataset_name}
                </div>
                <div className="text-[11px] text-[#5F5670]">
                  Detected Type: {uploadPreview.detected_type} • Total Rows: {Number(uploadPreview.total_raw_rows).toLocaleString()}
                </div>
              </div>
              <button
                type="button"
                onClick={() => setUploadPreview(null)}
                className="text-xs text-[#8E83A3] hover:text-[#1F1B2C] underline"
              >
                Cancel
              </button>
            </div>

            <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-4">
              <div>
                <label className="block text-xs font-bold text-[#1F1B2C] mb-1">
                  1. Timestamp Column *
                </label>
                <select
                  value={timeCol}
                  onChange={(e) => setTimeCol(e.target.value)}
                  className="w-full bg-white border border-[#CDC1FF] rounded-xl px-3 py-2 text-xs font-semibold text-[#1F1B2C] outline-none"
                >
                  <option value="">Select timestamp column...</option>
                  {uploadPreview.available_columns.map(c => (
                    <option key={c} value={c}>{c}</option>
                  ))}
                </select>
              </div>

              <div>
                <label className="block text-xs font-bold text-[#1F1B2C] mb-1">
                  2. Target Demand *
                </label>
                <select
                  value={targetCol}
                  onChange={(e) => setTargetCol(e.target.value)}
                  className="w-full bg-white border border-[#CDC1FF] rounded-xl px-3 py-2 text-xs font-semibold text-[#1F1B2C] outline-none"
                >
                  <option value="">Select target metric...</option>
                  {uploadPreview.available_columns.map(c => (
                    <option key={c} value={c}>{c}</option>
                  ))}
                </select>
              </div>

              <div>
                <label className="block text-xs font-bold text-[#1F1B2C] mb-1">
                  3. Store / Location (Optional)
                </label>
                <select
                  value={secondarySeriesCol}
                  onChange={(e) => setSecondarySeriesCol(e.target.value)}
                  className="w-full bg-white border border-[#CDC1FF] rounded-xl px-3 py-2 text-xs font-semibold text-[#1F1B2C] outline-none"
                >
                  <option value="">None (All Stores / Global)</option>
                  {uploadPreview.available_columns.map(c => (
                    <option key={c} value={c}>{c}</option>
                  ))}
                </select>
              </div>

              <div>
                <label className="block text-xs font-bold text-[#1F1B2C] mb-1">
                  4. Product / Item (Optional)
                </label>
                <select
                  value={seriesCol}
                  onChange={(e) => setSeriesCol(e.target.value)}
                  className="w-full bg-white border border-[#CDC1FF] rounded-xl px-3 py-2 text-xs font-semibold text-[#1F1B2C] outline-none"
                >
                  <option value="">None (Single Product / Total)</option>
                  {uploadPreview.available_columns.map(c => (
                    <option key={c} value={c}>{c}</option>
                  ))}
                </select>
              </div>
            </div>

            <div className="pt-2 flex justify-end">
              <button
                type="button"
                onClick={handleConfirmMapping}
                disabled={isLoading}
                className="px-6 py-2.5 rounded-xl bg-[#A294F9] text-white text-xs font-bold hover:bg-[#9181f7] shadow-xs flex items-center gap-2 cursor-pointer"
              >
                <Check className="w-4 h-4" />
                <span>Confirm & Standardize Dataset</span>
              </button>
            </div>
          </div>
        )}

        {/* Current Active Dataset Summary Badge */}
        {datasetSummary && (
          <div className="p-4 rounded-2xl bg-[#F5EFFF] border border-[#E5D9F2] flex flex-wrap items-center justify-between gap-4 text-xs">
            <div className="space-y-0.5">
              <div className="font-bold text-[#1F1B2C] flex items-center gap-2">
                <Database className="w-4 h-4 text-[#A294F9]" />
                <span>Loaded Dataset: {datasetSummary.dataset_name}</span>
                <span className="text-[10px] px-2 py-0.5 rounded-full bg-emerald-100 text-emerald-800 font-bold">
                  Canonical Parquet Ready
                </span>
              </div>
              <div className="text-[11px] text-[#5F5670]">
                {Number(datasetSummary.total_observations).toLocaleString()} historical observations • {datasetSummary.series_count} time series • {datasetSummary.start_date} to {datasetSummary.end_date}
              </div>
            </div>

            {datasetSummary.series_ids?.length > 1 && (
              <div className="flex items-center gap-2">
                <span className="text-[#8E83A3]">Active Series ID:</span>
                <select
                  value={selectedSeriesId || ''}
                  onChange={(e) => setSelectedSeriesId(e.target.value)}
                  className="bg-white border border-[#CDC1FF] rounded-xl px-3 py-1.5 text-xs font-semibold text-[#1F1B2C] outline-none cursor-pointer"
                >
                  {datasetSummary.series_ids.map(s => (
                    <option key={s} value={s}>{s}</option>
                  ))}
                </select>
              </div>
            )}
          </div>
        )}
      </section>

      {/* ========================================================================= */}
      {/* SECTION 2: CHRONOLOGICAL BACKTESTING & EVALUATION (10-STEP ENGINE) */}
      {/* ========================================================================= */}
      <section className="p-6 sm:p-8 rounded-3xl bg-white border border-[#E5D9F2] shadow-xs space-y-6">
        <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4 pb-4 border-b border-[#F5EFFF]">
          <div>
            <div className="text-xs font-semibold uppercase tracking-wider text-[#A294F9]">
              Step 2
            </div>
            <h2 className="text-xl font-bold font-heading text-[#1F1B2C]">
              Chronological Backtesting & Model Evaluation
            </h2>
            <p className="text-xs text-[#5F5670]">
              First 80% used for model training. The remaining 20% is strictly hidden as holdout test data to calculate real MAPE and RMSE.
            </p>
          </div>

          <button
            type="button"
            onClick={handleRunBenchmark}
            disabled={isLoading || !backendOnline}
            className="inline-flex items-center gap-2 px-6 py-3 rounded-2xl bg-[#A294F9] text-white text-xs font-bold hover:bg-[#9181f7] shadow-sm hover:shadow transition-all cursor-pointer shrink-0"
          >
            <Play className="w-3.5 h-3.5 fill-current" />
            <span>{isLoading ? 'Evaluating 5 Models...' : 'Evaluate Models'}</span>
          </button>
        </div>

        {/* 80/20 Chronological Rule Card */}
        <div className="p-4 rounded-2xl bg-[#F5EFFF]/70 border border-[#CDC1FF] space-y-2 text-xs">
          <div className="flex items-center justify-between text-[#1F1B2C] font-bold">
            <span className="flex items-center gap-1.5">
              <Lock className="w-3.5 h-3.5 text-[#A294F9]" />
              <span>Chronological 80/20 Holdout Rule: Zero Data Leakage</span>
            </span>
            <span className="text-[11px] text-emerald-700 font-semibold">
              {splitInfo ? `${splitInfo.train_observations} Train / ${splitInfo.test_observations} Test Steps` : '80% Train / 20% Test'}
            </span>
          </div>

          <div className="w-full flex h-6 rounded-xl overflow-hidden border border-[#CDC1FF] text-[10px] font-bold">
            <div className="bg-[#E5D9F2] text-[#5F5670] flex items-center justify-center w-[80%]">
              1. Training Period (First 80%) — Models Learn Parameters
            </div>
            <div className="bg-[#A294F9] text-white flex items-center justify-center w-[20%]">
              2. Hidden Test (Last 20%)
            </div>
          </div>

          <p className="text-[11px] text-[#5F5670] leading-relaxed">
            The candidate models (ARIMA, Prophet, LightGBM, DeepAR, TFT) are fitted strictly on the first 80 days. They predict the remaining 20 days. Their predictions are compared against the known actuals to compute exact MAPE and RMSE.
          </p>
        </div>

        {/* Live Loading Progress State */}
        {isLoading && (
          <div className="p-6 rounded-2xl bg-[#F5EFFF] border border-[#CDC1FF] flex items-center gap-4 animate-pulse">
            <div className="w-8 h-8 rounded-xl bg-[#A294F9] text-white flex items-center justify-center shrink-0">
              <Sparkles className="w-4 h-4 animate-spin" />
            </div>
            <div>
              <div className="text-sm font-bold text-[#1F1B2C]">
                {loadingMessage || 'Training models... please wait'}
              </div>
              <div className="text-xs text-[#5F5670]">
                Running candidate AI models to find which one predicts your data with the lowest error.
              </div>
            </div>
          </div>
        )}

        {/* Dynamic Leaderboard Table */}
        {leaderboard.length > 0 && (
          <div className="space-y-4">
            <div className="flex items-center justify-between">
              <h3 className="font-bold text-base text-[#1F1B2C]">
                Candidate Model Evaluation Leaderboard (Lower Error is Better)
              </h3>
              <span className="text-xs text-[#8E83A3]">
                Ranked by: <strong>Primary: MAPE %</strong>, Tie-Breaker: <strong>RMSE</strong>
              </span>
            </div>

            <div className="overflow-x-auto border border-[#E5D9F2] rounded-2xl">
              <table className="w-full text-left text-xs border-collapse">
                <thead className="bg-[#F5EFFF] text-[#8E83A3] uppercase tracking-wider">
                  <tr>
                    <th className="py-3 px-4 font-semibold">Rank</th>
                    <th className="py-3 px-4 font-semibold">Candidate Model</th>
                    <th className="py-3 px-4 font-semibold">Architecture Class</th>
                    <th className="py-3 px-4 font-semibold">Backtested MAPE (%)</th>
                    <th className="py-3 px-4 font-semibold">RMSE (Units)</th>
                    <th className="py-3 px-4 font-semibold">Training Time</th>
                    <th className="py-3 px-4 font-semibold text-right">Selection for Future Forecast</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-[#F5EFFF]">
                  {leaderboard.map((row) => {
                    const isWinner = row.rank === 1;
                    const isSelected = selectedModel === row.model_key;
                    return (
                      <tr 
                        key={row.model_key} 
                        className={`transition-colors ${
                          isSelected ? 'bg-[#F5EFFF]/80' : 'hover:bg-[#F5EFFF]/30'
                        }`}
                      >
                        <td className="py-3.5 px-4">
                          <span className={`w-6 h-6 rounded-full flex items-center justify-center font-bold text-xs ${
                            isWinner 
                              ? 'bg-[#A294F9] text-white shadow-xs' 
                              : 'bg-[#E5D9F2] text-[#5F5670]'
                          }`}>
                            #{row.rank}
                          </span>
                        </td>
                        <td className="py-3.5 px-4 font-bold text-[#1F1B2C]">
                          <div className="flex items-center gap-2">
                            <span 
                              className="w-2.5 h-2.5 rounded-full inline-block"
                              style={{ backgroundColor: modelColors[row.model_key] || '#A294F9' }}
                            />
                            <span>{row.model_name}</span>
                            {isWinner && (
                              <span className="text-[9px] px-2 py-0.5 rounded-full bg-emerald-100 text-emerald-800 font-bold">
                                #1 WINNER
                              </span>
                            )}
                          </div>
                        </td>
                        <td className="py-3.5 px-4 text-[#5F5670]">
                          {row.model_type}
                        </td>
                        <td className="py-3.5 px-4 font-bold text-[#1F1B2C]">
                          <span className={isWinner ? 'text-emerald-700 font-extrabold text-sm' : ''}>
                            {row.mape != null ? `${Number(row.mape).toFixed(2)}%` : 'N/A'}
                          </span>
                        </td>
                        <td className="py-3.5 px-4 font-semibold text-[#1F1B2C]">
                          {row.rmse != null ? Number(row.rmse).toFixed(2) : 'N/A'}
                        </td>
                        <td className="py-3.5 px-4 text-[#8E83A3] font-mono">
                          {row.train_time_seconds != null ? `${Number(row.train_time_seconds).toFixed(2)}s` : '-'}
                        </td>
                        <td className="py-3.5 px-4 text-right">
                          <button
                            type="button"
                            onClick={() => setSelectedModel(row.model_key)}
                            className={`px-3.5 py-1.5 rounded-xl text-xs font-bold transition-all cursor-pointer ${
                              isSelected
                                ? 'bg-[#A294F9] text-white shadow-xs'
                                : 'bg-white border border-[#CDC1FF] text-[#1F1B2C] hover:bg-[#F5EFFF]'
                            }`}
                          >
                            {isSelected ? 'Selected Model ✓' : 'Select for Forecast'}
                          </button>
                        </td>
                      </tr>
                    );
                  })}
                </tbody>
              </table>
            </div>
          </div>
        )}
      </section>

      {/* ========================================================================= */}
      {/* SECTION 3: FUTURE FORECASTING (100% RETRAINING & FUTURE NUMBERS) */}
      {/* ========================================================================= */}
      <section className="p-6 sm:p-8 rounded-3xl bg-white border border-[#E5D9F2] shadow-xs space-y-6">
        <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4 pb-4 border-b border-[#F5EFFF]">
          <div>
            <div className="text-xs font-semibold uppercase tracking-wider text-[#A294F9]">
              Step 3
            </div>
            <h2 className="text-xl font-bold font-heading text-[#1F1B2C]">
              Future Forecasting (100% Historical Retraining)
            </h2>
            <p className="text-xs text-[#5F5670]">
              Retrain your selected model on 100% of historical data and project into the future with uncertainty bounds.
            </p>
          </div>

          <button
            type="button"
            onClick={handleExecuteFutureForecast}
            disabled={isLoading || !backendOnline}
            className="inline-flex items-center gap-2 px-6 py-3 rounded-2xl bg-[#A294F9] text-white text-xs font-bold hover:bg-[#9181f7] shadow-sm hover:shadow transition-all cursor-pointer shrink-0"
          >
            <Zap className="w-4 h-4" />
            <span>Generate Future Forecast Now</span>
          </button>
        </div>

        {/* Future Horizon & Model Selection Controls */}
        <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-4">
          {/* Selected Model */}
          <div className="p-4 rounded-2xl bg-[#F5EFFF] border border-[#CDC1FF] space-y-1">
            <span className="text-[11px] font-bold uppercase text-[#8E83A3]">Selected Candidate Model:</span>
            <div className="text-base font-bold text-[#1F1B2C] uppercase">{selectedModel}</div>
            <p className="text-[11px] text-[#5F5670]">
              Will be retrained on 100% of available historical observations.
            </p>
          </div>

          {/* Horizon Selection */}
          <div className="space-y-1.5">
            <label className="block text-xs font-bold text-[#1F1B2C]">
              Future Horizon Window
            </label>
            <div className="grid grid-cols-4 gap-1 bg-[#F5EFFF] p-1 rounded-xl border border-[#CDC1FF]">
              {[7, 14, 28, 90].map((days) => (
                <button
                  key={days}
                  type="button"
                  onClick={() => setLocalHorizon(days)}
                  className={`py-2 text-center text-xs rounded-lg font-bold transition-all cursor-pointer ${
                    localHorizon === days 
                      ? 'bg-[#A294F9] text-white shadow-xs' 
                      : 'text-[#5F5670] hover:text-[#1F1B2C]'
                  }`}
                >
                  {days}D
                </button>
              ))}
            </div>
            <div className="text-[11px] text-[#8E83A3]">
              {localHorizon === 7 ? 'Short-term replenishment' : localHorizon === 14 ? 'Bi-weekly cycle' : localHorizon === 28 ? 'Monthly demand planning' : 'Quarterly supply strategy'}
            </div>
          </div>

          {/* Optional Current Inventory */}
          <div className="space-y-1.5">
            <label className="block text-xs font-bold text-[#1F1B2C]">
              On-Hand Inventory (Optional)
            </label>
            <input
              type="number"
              placeholder="e.g. 500 units"
              value={localInventory}
              onChange={(e) => setLocalInventory(e.target.value)}
              className="w-full bg-[#F5EFFF] border border-[#CDC1FF] rounded-xl px-3 py-2 text-xs font-semibold text-[#1F1B2C] outline-none"
            />
            <div className="text-[11px] text-[#8E83A3]">
              Used to calculate stockout risk and estimated stockout dates.
            </div>
          </div>
        </div>

        {/* FUTURE FORECAST RESULTS */}
        {forecastResult && (
          <div className="space-y-6 pt-4 border-t border-[#F5EFFF]">
            {/* Top 4 Future KPI Cards */}
            <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4">
              <div className="p-4 rounded-2xl bg-[#F5EFFF]/70 border border-[#E5D9F2] space-y-1">
                <div className="text-[10px] font-bold uppercase text-[#8E83A3]">Total Projected Volume</div>
                <div className="text-2xl font-bold font-heading text-[#A294F9]">
                  {Math.round(forecastResult.insights.total_projected_volume).toLocaleString()} <span className="text-xs font-normal text-[#5F5670]">units</span>
                </div>
                <div className="text-[11px] text-[#5F5670]">
                  Across {forecastResult.horizon} upcoming future days
                </div>
              </div>

              <div className="p-4 rounded-2xl bg-[#F5EFFF]/70 border border-[#E5D9F2] space-y-1">
                <div className="text-[10px] font-bold uppercase text-[#8E83A3]">Daily Average Demand</div>
                <div className="text-2xl font-bold font-heading text-[#1F1B2C]">
                  {forecastResult.insights?.average_daily_demand != null ? Number(forecastResult.insights.average_daily_demand).toFixed(1) : '-'} <span className="text-xs font-normal text-[#5F5670]">units/day</span>
                </div>
                <div className="text-[11px] text-emerald-600 capitalize font-medium">
                  {forecastResult.insights?.demand_trend || 'stable'} trend
                </div>
              </div>

              <div className="p-4 rounded-2xl bg-[#F5EFFF]/70 border border-[#E5D9F2] space-y-1">
                <div className="text-[10px] font-bold uppercase text-[#8E83A3]">Peak Demand Date</div>
                <div className="text-xl font-bold font-heading text-[#1F1B2C]">
                  {forecastResult.insights?.peak_demand_value != null ? Number(forecastResult.insights.peak_demand_value).toFixed(1) : '-'} <span className="text-xs font-normal text-[#5F5670]">units</span>
                </div>
                <div className="text-[11px] text-[#8E83A3]">
                  Date: {forecastResult.insights?.peak_demand_date || '-'}
                </div>
              </div>

              <div className="p-4 rounded-2xl bg-[#F5EFFF]/70 border border-[#E5D9F2] space-y-1">
                <div className="text-[10px] font-bold uppercase text-[#8E83A3]">Recommended Safety Stock</div>
                <div className="text-2xl font-bold font-heading text-emerald-700">
                  {forecastResult.insights?.recommended_safety_stock != null ? Math.round(Number(forecastResult.insights.recommended_safety_stock)) : 0} <span className="text-xs font-normal text-[#5F5670]">units</span>
                </div>
                <div className="text-[11px] text-[#5F5670]">
                  Uncertainty safety buffer
                </div>
              </div>
            </div>

            {/* Interactive Future Forecast Chart */}
            <div className="space-y-3">
              <div className="text-xs font-bold text-[#1F1B2C]">
                100% Historical Data + Future Projections with 80% & 95% Confidence Intervals
              </div>
              <ForecastChart
                history={chartHistory}
                forecast={forecastResult.forecast}
                horizonDays={forecastResult.horizon}
                onHorizonChange={(days) => {
                  setLocalHorizon(days);
                  runFutureForecast(selectedModel, days, selectedSeriesId, localInventory).catch(() => {});
                }}
                showHorizonSwitch={true}
                storeName={forecastResult.dataset_id}
                productName={forecastResult.series_id}
              />
            </div>

            {/* Future Numbers Table with CSV Download */}
            <div className="space-y-3 pt-2">
              <div className="flex items-center justify-between">
                <h4 className="text-sm font-bold text-[#1F1B2C]">
                  Future Forecast Number Table ({forecastResult.horizon} Days)
                </h4>

                <button
                  type="button"
                  onClick={exportForecastToCsv}
                  className="inline-flex items-center gap-1.5 px-4 py-2 rounded-xl bg-[#A294F9] text-white text-xs font-bold hover:bg-[#9181f7] shadow-xs cursor-pointer"
                >
                  <Download className="w-3.5 h-3.5" />
                  <span>Download Forecast CSV</span>
                </button>
              </div>

              <div className="overflow-x-auto border border-[#E5D9F2] rounded-2xl max-h-72">
                <table className="w-full text-left text-xs border-collapse">
                  <thead className="bg-[#F5EFFF] text-[#8E83A3] sticky top-0">
                    <tr>
                      <th className="py-2.5 px-4 font-semibold">Date</th>
                      <th className="py-2.5 px-4 font-bold text-[#A294F9]">Point Prediction</th>
                      <th className="py-2.5 px-4 font-semibold">80% Lower</th>
                      <th className="py-2.5 px-4 font-semibold">80% Upper</th>
                      <th className="py-2.5 px-4 font-semibold">95% Lower</th>
                      <th className="py-2.5 px-4 font-semibold">95% Upper</th>
                    </tr>
                  </thead>
                  <tbody className="divide-y divide-[#F5EFFF]">
                    {forecastResult.forecast.map((row, idx) => (
                      <tr key={idx} className="hover:bg-[#F5EFFF]/30">
                        <td className="py-2 px-4 font-medium text-[#1F1B2C]">{row.timestamp}</td>
                        <td className="py-2 px-4 font-bold text-[#A294F9]">{row.prediction != null ? Number(row.prediction).toFixed(2) : '-'}</td>
                        <td className="py-2 px-4 text-[#5F5670]">{row.lower_80 != null ? Number(row.lower_80).toFixed(2) : '-'}</td>
                        <td className="py-2 px-4 text-[#5F5670]">{row.upper_80 != null ? Number(row.upper_80).toFixed(2) : '-'}</td>
                        <td className="py-2 px-4 text-[#8E83A3]">{row.lower_95 != null ? Number(row.lower_95).toFixed(2) : '-'}</td>
                        <td className="py-2 px-4 text-[#8E83A3]">{row.upper_95 != null ? Number(row.upper_95).toFixed(2) : '-'}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            </div>
          </div>
        )}
      </section>
    </div>
  );
}
