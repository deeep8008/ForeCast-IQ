import React, { useState, useRef, useEffect } from 'react';
import { 
  Upload, 
  FileText, 
  CheckCircle2, 
  AlertTriangle, 
  AlertCircle, 
  Sparkles, 
  RotateCcw, 
  ArrowRight, 
  Check, 
  Info
} from 'lucide-react';
import { DEMO_DATASETS } from '../utils/datasetAnalyzer';
import { uploadDatasetToBackend, remapDatasetInBackend, convertM5SampleInBackend } from '../services/api';

export default function UploadDatasetPage({ onNavigate, onDatasetReady, uploadedDataset = null, onClearDataset = null }) {
  const [dragActive, setDragActive] = useState(false);
  const [_file, setFile] = useState(null);
  const [analysis, setAnalysis] = useState(uploadedDataset);
  const [isAnalyzing, setIsAnalyzing] = useState(false);
  const [analysisStep, setAnalysisStep] = useState('');
  const [uploadError, setUploadError] = useState(null);

  // Column mapping edit state
  const [customMapping, setCustomMapping] = useState({
    date: uploadedDataset?.mapping?.date || '',
    series_id: uploadedDataset?.mapping?.series_id || '',
    target: uploadedDataset?.mapping?.target || '',
    composite_series_keys: uploadedDataset?.mapping?.composite_series_keys || []
  });

  const fileInputRef = useRef(null);

  // Synchronize internal state whenever uploadedDataset changes (e.g. restored from backend after refresh)
  useEffect(() => {
    if (uploadedDataset) {
      setAnalysis(uploadedDataset);
      if (uploadedDataset.mapping) {
        setCustomMapping({
          date: uploadedDataset.mapping.date || '',
          series_id: uploadedDataset.mapping.series_id || '',
          target: uploadedDataset.mapping.target || '',
          composite_series_keys: uploadedDataset.mapping.composite_series_keys || []
        });
      }
    }
  }, [uploadedDataset]);

  // Handle upload directly to backend
  const processCSVUpload = async (filename, fileOrBlob) => {
    setUploadError(null);
    setIsAnalyzing(true);
    setAnalysisStep('Uploading dataset to backend analysis engine...');

    try {
      setAnalysisStep('Validating canonical schema and computing profile in Python backend...');
      const backendResult = await uploadDatasetToBackend(fileOrBlob, filename);

      setCustomMapping({
        date: backendResult.mapping.date,
        series_id: backendResult.mapping.series_id,
        target: backendResult.mapping.target
      });
      setAnalysis(backendResult);
      setIsAnalyzing(false);

      if (onDatasetReady) {
        onDatasetReady(backendResult);
      }
    } catch (err) {
      setIsAnalyzing(false);
      setUploadError(err.message || 'Failed to connect to backend engine.');
    }
  };

  // File Upload Handlers
  const handleFileChange = (e) => {
    const selected = e.target.files && e.target.files[0];
    if (selected) {
      if (!selected.name.toLowerCase().endsWith('.csv')) {
        setUploadError('Invalid file type. Please upload a standard CSV file (.csv).');
        return;
      }
      setFile(selected);
      processCSVUpload(selected.name, selected);
    }
  };

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

    if (e.dataTransfer.files && e.dataTransfer.files[0]) {
      const dropped = e.dataTransfer.files[0];
      if (!dropped.name.toLowerCase().endsWith('.csv')) {
        setUploadError('Invalid file format. Please upload a standard CSV file (.csv).');
        return;
      }
      setFile(dropped);
      processCSVUpload(dropped.name, dropped);
    }
  };

  // Re-run analysis when user changes mapping manually in backend
  const handleMappingChange = async (field, newCol) => {
    const nextMapping = { ...customMapping, [field]: newCol };
    // If user explicitly maps a direct series_id column, clear composite keys
    if (field === 'series_id' && newCol) {
      nextMapping.composite_series_keys = [];
    }
    setCustomMapping(nextMapping);

    if (analysis?.dataset_id) {
      try {
        const updated = await remapDatasetInBackend(analysis.dataset_id, nextMapping);
        setAnalysis(prev => ({
          ...updated,
          previewRows: prev.previewRows
        }));
        if (onDatasetReady) onDatasetReady(updated);
      } catch (err) {
        setUploadError(err.message || 'Remapping failed on backend.');
      }
    }
  };

  const handleToggleCompositeKey = async (colName) => {
    const currentKeys = customMapping.composite_series_keys || [];
    const nextKeys = currentKeys.includes(colName)
      ? currentKeys.filter(k => k !== colName)
      : [...currentKeys, colName];

    const nextMapping = {
      ...customMapping,
      series_id: '',
      composite_series_keys: nextKeys
    };
    setCustomMapping(nextMapping);

    if (analysis?.dataset_id) {
      try {
        const updated = await remapDatasetInBackend(analysis.dataset_id, nextMapping);
        setAnalysis(prev => ({
          ...updated,
          previewRows: prev.previewRows
        }));
        if (onDatasetReady) onDatasetReady(updated);
      } catch (err) {
        setUploadError(err.message || 'Failed to update composite identifier mapping.');
      }
    }
  };

  const handleLoadDemo = async (key) => {
    if (key === 'm5Sample') {
      setUploadError(null);
      setIsAnalyzing(true);
      setAnalysisStep('Converting local M5 dataset into universal canonical schema...');
      setFile({ name: 'm5_canonical_sample.csv' });
      try {
        const backendResult = await convertM5SampleInBackend(3, 194);
        setCustomMapping({
          date: backendResult.mapping.date,
          series_id: backendResult.mapping.series_id,
          target: backendResult.mapping.target
        });
        setAnalysis(backendResult);
        setIsAnalyzing(false);
        if (onDatasetReady) {
          onDatasetReady(backendResult);
        }
      } catch (err) {
        setIsAnalyzing(false);
        setUploadError(err.message || 'M5 dataset conversion failed.');
      }
      return;
    }

    const demo = DEMO_DATASETS[key];
    if (demo) {
      setFile({ name: demo.filename });
      const blob = new Blob([demo.csv], { type: 'text/csv' });
      processCSVUpload(demo.filename, blob);
    }
  };

  const handleReset = () => {
    setFile(null);
    setAnalysis(null);
    setUploadError(null);
    setCustomMapping({ date: '', series_id: '', target: '' });
    if (fileInputRef.current) fileInputRef.current.value = '';
    if (onClearDataset) onClearDataset();
  };

  return (
    <div className="space-y-8 max-w-7xl mx-auto pb-12" data-testid="upload-dataset-page">
      {/* Header */}
      <div>
        <div className="text-xs font-semibold uppercase tracking-wider text-[#8E83A3]">
          Universal Dataset Ingestion
        </div>
        <h1 className="text-3xl font-bold font-heading text-[#1F1B2C]">
          Upload Dataset
        </h1>
        <p className="text-sm text-[#5F5670] mt-1 max-w-3xl">
          Bring your enterprise demand observations into ForecastIQ. Compatible with time-series data from retail stores, wholesale warehouses, regional branches, or manufacturing product lines.
        </p>
      </div>

      {/* Mandatory & Optional Columns Notice Card */}
      <section className="p-5 rounded-2xl bg-white border border-[#E5D9F2] shadow-xs">
        <div className="flex flex-col md:flex-row md:items-center justify-between gap-4">
          <div className="space-y-1">
            <div className="flex items-center gap-2">
              <span className="w-2 h-2 rounded-full bg-[#A294F9]"></span>
              <span className="text-xs font-bold uppercase tracking-wider text-[#1F1B2C]">
                Universal Schema Specification
              </span>
            </div>
            <p className="text-xs text-[#5F5670]">
              Every custom dataset requires only two mandatory fields: date and target. Series identifiers are optional for single series or can be derived from composite entity columns.
            </p>
          </div>

          <div className="flex flex-wrap items-center gap-2 text-xs">
            <span className="px-3 py-1 rounded-lg bg-[#F5EFFF] text-[#1F1B2C] border border-[#CDC1FF] font-semibold">
              Mandatory: <span className="font-mono text-[#A294F9]">date</span>, <span className="font-mono text-[#A294F9]">target</span>
            </span>
            <span className="px-3 py-1 rounded-lg bg-emerald-50 text-emerald-800 border border-emerald-200 font-medium">
              Optional / Auto-resolved: <span className="font-mono text-emerald-700">series_id</span> (or composite keys)
            </span>
            <span className="px-3 py-1 rounded-lg bg-gray-50 text-[#5F5670] border border-gray-200">
              Covariates: store_id, item_id, category, price, promo, etc.
            </span>
          </div>
        </div>
      </section>

      {/* Upload Zone & Demo Presets (Shown when no dataset analyzed or during reset) */}
      {!analysis && !isAnalyzing && (
        <section className="space-y-6">
          {/* Drag & Drop Area */}
          <div
            onDragEnter={handleDrag}
            onDragOver={handleDrag}
            onDragLeave={handleDrag}
            onDrop={handleDrop}
            className={`
              relative p-10 sm:p-14 rounded-3xl border-2 border-dashed text-center transition-all cursor-pointer bg-white
              ${dragActive 
                ? 'border-[#A294F9] bg-[#F5EFFF]/70 shadow-md ring-2 ring-[#CDC1FF]' 
                : 'border-[#CDC1FF] hover:border-[#A294F9] hover:bg-[#F5EFFF]/30 shadow-xs'
              }
            `}
            onClick={() => fileInputRef.current?.click()}
            data-testid="drop-zone"
          >
            <input
              ref={fileInputRef}
              type="file"
              accept=".csv"
              onChange={handleFileChange}
              className="hidden"
              data-testid="csv-file-input"
            />

            <div className="w-16 h-16 mx-auto rounded-3xl bg-[#F5EFFF] border border-[#CDC1FF] flex items-center justify-center text-[#A294F9] mb-4 shadow-xs">
              <Upload className="w-8 h-8" />
            </div>

            <h3 className="text-lg font-bold font-heading text-[#1F1B2C]">
              Drag and drop your demand CSV here
            </h3>
            <p className="text-xs text-[#5F5670] mt-1.5 max-w-md mx-auto leading-relaxed">
              Upload standard comma-separated values (.csv). Columns are automatically mapped and evaluated for multi-horizon readiness.
            </p>

            <div className="mt-5 flex items-center justify-center gap-3">
              <button
                type="button"
                className="px-5 py-2.5 rounded-xl bg-[#A294F9] text-white text-xs font-semibold hover:bg-[#9181f7] shadow-xs transition-colors"
              >
                Browse Files
              </button>
            </div>

            {uploadError && (
              <div className="mt-4 p-3 rounded-xl bg-red-50 border border-red-200 text-red-700 text-xs font-medium max-w-md mx-auto flex items-center justify-center gap-2" data-testid="upload-error-banner">
                <AlertCircle className="w-4 h-4 shrink-0 text-red-600" />
                <span>{uploadError}</span>
              </div>
            )}
          </div>

          {/* Quick Demo Dataset Presets for Instant 1-Click Verification */}
          <div className="p-6 rounded-3xl bg-white border border-[#E5D9F2] shadow-xs space-y-4">
            <div>
              <div className="text-xs font-semibold uppercase tracking-wider text-[#8E83A3]">
                Instant Verification Presets
              </div>
              <h3 className="text-base font-bold font-heading text-[#1F1B2C]">
                Try with a pre-configured enterprise dataset
              </h3>
              <p className="text-xs text-[#5F5670]">
                Select a sample dataset to test column mapping, quality diagnostics, and forecast readiness immediately.
              </p>
            </div>

            <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
              <div 
                onClick={() => handleLoadDemo('universalRetail')}
                className="p-4 rounded-2xl bg-[#F5EFFF]/60 border border-[#E5D9F2] hover:border-[#CDC1FF] hover:bg-[#F5EFFF] cursor-pointer transition-all space-y-2"
                data-testid="load-demo-retail"
              >
                <div className="flex items-center justify-between">
                  <span className="text-[10px] uppercase font-bold tracking-wider text-emerald-700 bg-emerald-100 px-2 py-0.5 rounded-full">
                    Compliant
                  </span>
                  <FileText className="w-4 h-4 text-[#A294F9]" />
                </div>
                <div className="text-xs font-bold text-[#1F1B2C]">
                  Enterprise Retail Branch Demand
                </div>
                <p className="text-[11px] text-[#5F5670] leading-relaxed">
                  Universal format with date, series_id, target, store_id, and promotional features.
                </p>
              </div>

              <div 
                onClick={() => handleLoadDemo('m5Sample')}
                className="p-4 rounded-2xl bg-[#F5EFFF]/60 border border-[#E5D9F2] hover:border-[#CDC1FF] hover:bg-[#F5EFFF] cursor-pointer transition-all space-y-2"
                data-testid="load-demo-m5"
              >
                <div className="flex items-center justify-between">
                  <span className="text-[10px] uppercase font-bold tracking-wider text-[#A294F9] bg-[#E5D9F2] px-2 py-0.5 rounded-full">
                    M5 Benchmark
                  </span>
                  <FileText className="w-4 h-4 text-[#A294F9]" />
                </div>
                <div className="text-xs font-bold text-[#1F1B2C]">
                  M5 Standardized Sample
                </div>
                <p className="text-[11px] text-[#5F5670] leading-relaxed">
                  Real store-item time series converted into universal format for seamless model training.
                </p>
              </div>

              <div 
                onClick={() => handleLoadDemo('needsAttention')}
                className="p-4 rounded-2xl bg-[#F5EFFF]/60 border border-[#E5D9F2] hover:border-[#CDC1FF] hover:bg-[#F5EFFF] cursor-pointer transition-all space-y-2"
                data-testid="load-demo-audit"
              >
                <div className="flex items-center justify-between">
                  <span className="text-[10px] uppercase font-bold tracking-wider text-amber-700 bg-amber-100 px-2 py-0.5 rounded-full">
                    Quality Flags
                  </span>
                  <FileText className="w-4 h-4 text-amber-500" />
                </div>
                <div className="text-xs font-bold text-[#1F1B2C]">
                  Unverified Branch Audit CSV
                </div>
                <p className="text-[11px] text-[#5F5670] leading-relaxed">
                  Includes duplicate timestamps, negative returns, and missing values to test diagnostics.
                </p>
              </div>
            </div>
          </div>
        </section>
      )}

      {/* Progress / Analyzing State */}
      {isAnalyzing && (
        <div className="p-12 rounded-3xl bg-white border border-[#E5D9F2] shadow-xs text-center max-w-md mx-auto space-y-4 my-8" data-testid="analyzing-state">
          <div className="w-14 h-14 mx-auto rounded-2xl bg-[#F5EFFF] border border-[#CDC1FF] flex items-center justify-center text-[#A294F9]">
            <Sparkles className="w-7 h-7 animate-pulse" />
          </div>
          <div>
            <h3 className="text-lg font-bold font-heading text-[#1F1B2C]">
              {analysisStep}
            </h3>
            <p className="text-xs text-[#5F5670] mt-1">
              Validating columns, checking chronological cadence, and detecting forecast readiness.
            </p>
          </div>
        </div>
      )}

      {/* Complete Dataset Analysis Views (Displayed when analyzed) */}
      {analysis && !isAnalyzing && (
        <div className="space-y-8" data-testid="analysis-results">
          {/* Top Actions & Overall Status Banner */}
          <div className="p-5 rounded-2xl bg-white border border-[#E5D9F2] shadow-xs flex flex-col sm:flex-row sm:items-center justify-between gap-4">
            <div className="flex items-center gap-3">
              <div className={`p-2.5 rounded-xl ${
                analysis.quality.overallStatus === 'FORECAST READY'
                  ? 'bg-emerald-50 text-emerald-600 border border-emerald-200'
                  : 'bg-amber-50 text-amber-600 border border-amber-200'
              }`}>
                {analysis.quality.overallStatus === 'FORECAST READY' ? (
                  <CheckCircle2 className="w-6 h-6" />
                ) : (
                  <AlertTriangle className="w-6 h-6" />
                )}
              </div>

              <div>
                <div className="flex items-center gap-2">
                  <span className={`text-xs font-extrabold px-2.5 py-0.5 rounded-full ${
                    analysis.quality.overallStatus === 'FORECAST READY'
                      ? 'bg-emerald-100 text-emerald-800'
                      : 'bg-amber-100 text-amber-800'
                  }`} data-testid="dataset-status-badge">
                    {analysis.quality.overallStatus}
                  </span>
                  <span className="text-xs font-semibold text-[#1F1B2C] truncate max-w-xs">
                    {analysis.profile.filename}
                  </span>
                </div>
                <p className="text-xs text-[#5F5670] mt-0.5">
                  {analysis.quality.overallStatus === 'FORECAST READY'
                    ? 'Your dataset is verified and ready for multi-horizon model training.'
                    : 'Data issues identified below require attention before training.'}
                </p>
              </div>
            </div>

            <div className="flex items-center gap-2.5">
              <button
                onClick={handleReset}
                className="px-3.5 py-2 rounded-xl bg-[#F5EFFF] text-[#5F5670] hover:text-[#1F1B2C] border border-[#CDC1FF] text-xs font-semibold transition-colors flex items-center gap-1.5"
                data-testid="upload-another-btn"
              >
                <RotateCcw className="w-3.5 h-3.5" />
                <span>Upload Another</span>
              </button>

              <button
                onClick={() => onNavigate('evaluation')}
                className="px-5 py-2 rounded-xl bg-[#A294F9] text-white hover:bg-[#9181f7] text-xs font-semibold transition-colors shadow-xs flex items-center gap-1.5"
                data-testid="continue-to-evaluation-btn"
              >
                <span>Continue to Evaluation & Backtesting →</span>
                <ArrowRight className="w-3.5 h-3.5" />
              </button>
            </div>
          </div>

          {/* 1. DATASET PROFILE UI */}
          <section className="p-6 lg:p-8 rounded-3xl bg-white border border-[#E5D9F2] shadow-xs space-y-6" data-testid="dataset-profile-section">
            <div>
              <div className="text-xs font-semibold uppercase tracking-wider text-[#8E83A3]">
                Dataset Profile
              </div>
              <h2 className="text-xl font-bold font-heading text-[#1F1B2C]">
                Structural Overview
              </h2>
              <p className="text-xs text-[#5F5670]">
                High-level dimensions, observation frequency, and chronological date span.
              </p>
            </div>

            {/* Profile Grid Cards */}
            <div className="grid grid-cols-2 sm:grid-cols-3 lg:grid-cols-6 gap-3.5">
              <div className="p-4 rounded-2xl bg-[#F5EFFF]/70 border border-[#E5D9F2]">
                <div className="text-[11px] text-[#8E83A3] font-medium">Total Rows</div>
                <div className="text-xl font-bold font-heading text-[#1F1B2C] mt-1" data-testid="profile-rows-count">
                  {analysis.profile.rowsCount.toLocaleString()}
                </div>
              </div>

              <div className="p-4 rounded-2xl bg-[#F5EFFF]/70 border border-[#E5D9F2]">
                <div className="text-[11px] text-[#8E83A3] font-medium">Columns</div>
                <div className="text-xl font-bold font-heading text-[#1F1B2C] mt-1">
                  {analysis.profile.columnsCount}
                </div>
              </div>

              <div className="p-4 rounded-2xl bg-[#F5EFFF]/70 border border-[#E5D9F2]">
                <div className="text-[11px] text-[#8E83A3] font-medium">Detected Cadence</div>
                <div className="text-sm font-bold font-heading text-[#A294F9] mt-1 truncate">
                  {analysis.profile.detectedFrequency}
                </div>
              </div>

              <div className="p-4 rounded-2xl bg-[#F5EFFF]/70 border border-[#E5D9F2]">
                <div className="text-[11px] text-[#8E83A3] font-medium">Unique Series</div>
                <div className="text-xl font-bold font-heading text-[#1F1B2C] mt-1" data-testid="profile-series-count">
                  {analysis.profile.uniqueSeriesCount}
                </div>
              </div>

              <div className="p-4 rounded-2xl bg-[#F5EFFF]/70 border border-[#E5D9F2] col-span-2">
                <div className="text-[11px] text-[#8E83A3] font-medium">Date Range (Historical Span)</div>
                <div className="text-xs font-bold text-[#1F1B2C] mt-1">
                  {analysis.profile.dateRange.start} → {analysis.profile.dateRange.end}
                </div>
                <div className="text-[10px] text-[#5F5670]">
                  {analysis.profile.dateRange.spanDays} Calendar Days
                </div>
              </div>
            </div>
          </section>

          {/* 2. COLUMN MAPPING UI */}
          <section className="p-6 lg:p-8 rounded-3xl bg-white border border-[#E5D9F2] shadow-xs space-y-6" data-testid="column-mapping-section">
            <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-3">
              <div>
                <div className="text-xs font-semibold uppercase tracking-wider text-[#8E83A3]">
                  Column Configuration
                </div>
                <h2 className="text-xl font-bold font-heading text-[#1F1B2C]">
                  Column Mapping
                </h2>
                <p className="text-xs text-[#5F5670]">
                  Confirm the three mandatory forecasting columns. You can manually adjust mapping if automatic detection was uncertain.
                </p>
              </div>

              <span className="text-[11px] text-[#A294F9] bg-[#F5EFFF] px-3 py-1 rounded-full border border-[#CDC1FF] font-medium self-start sm:self-auto">
                Auto-Detection Active
              </span>
            </div>

            {/* Mandatory Columns Dropdown Selectors */}
            <div className="grid grid-cols-1 md:grid-cols-3 gap-4 p-5 rounded-2xl bg-[#F5EFFF]/40 border border-[#E5D9F2]">
              {/* Date */}
              <div className="space-y-1.5">
                <label className="flex items-center justify-between text-xs font-bold text-[#1F1B2C]">
                  <span>Mandatory Date Column:</span>
                  <span className="text-[10px] px-2 py-0.5 rounded-full bg-[#A294F9] text-white">Required</span>
                </label>
                <select
                  value={customMapping.date}
                  onChange={(e) => handleMappingChange('date', e.target.value)}
                  className="w-full bg-white border border-[#CDC1FF] rounded-xl px-3 py-2 text-xs font-semibold text-[#1F1B2C] outline-none"
                  data-testid="map-date-select"
                >
                  <option value="">-- Select Date Column --</option>
                  {(analysis.profile?.headers || []).map(h => (
                    <option key={h} value={h}>{h}</option>
                  ))}
                </select>
                <div className="text-[10px] text-[#5F5670]">
                  Observation timestamp or chronological calendar date.
                </div>
              </div>

              {/* Series ID (Optional) */}
              <div className="space-y-1.5">
                <label className="flex items-center justify-between text-xs font-bold text-[#1F1B2C]">
                  <span>Series ID Column:</span>
                  <span className="text-[10px] px-2 py-0.5 rounded-full bg-emerald-100 text-emerald-800 font-semibold">Optional</span>
                </label>
                <select
                  value={customMapping.series_id}
                  onChange={(e) => handleMappingChange('series_id', e.target.value)}
                  className="w-full bg-white border border-[#CDC1FF] rounded-xl px-3 py-2 text-xs font-semibold text-[#1F1B2C] outline-none"
                  data-testid="map-series-select"
                >
                  <option value="">-- None (Single-Series: default_series) --</option>
                  {(analysis.profile?.headers || []).map(h => (
                    <option key={h} value={h}>{h}</option>
                  ))}
                </select>
                <div className="text-[10px] text-[#5F5670]">
                  Leave empty if CSV contains only 1 series. Will use internal <span className="font-mono text-purple-700">default_series</span>.
                </div>
              </div>

              {/* Target */}
              <div className="space-y-1.5">
                <label className="flex items-center justify-between text-xs font-bold text-[#1F1B2C]">
                  <span>Mandatory Target Column:</span>
                  <span className="text-[10px] px-2 py-0.5 rounded-full bg-[#A294F9] text-white">Required</span>
                </label>
                <select
                  value={customMapping.target}
                  onChange={(e) => handleMappingChange('target', e.target.value)}
                  className="w-full bg-white border border-[#CDC1FF] rounded-xl px-3 py-2 text-xs font-semibold text-[#1F1B2C] outline-none"
                  data-testid="map-target-select"
                >
                  <option value="">-- Select Target Column --</option>
                  {(analysis.profile?.headers || []).map(h => (
                    <option key={h} value={h}>{h}</option>
                  ))}
                </select>
                <div className="text-[10px] text-[#5F5670]">
                  Numerical quantity to predict (e.g. sales, demand, units).
                </div>
              </div>
            </div>

            {/* Candidate Entity Columns & User-Confirmed Composite Identifier */}
            {((analysis.mapping?.candidate_entity_columns || []).length > 0 || (customMapping.composite_series_keys || []).length > 0) && (
              <div className="p-4 rounded-2xl bg-[#F5EFFF]/70 border border-[#CDC1FF] space-y-3" data-testid="composite-keys-section">
                <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-2">
                  <div className="space-y-0.5">
                    <div className="text-xs font-bold text-[#1F1B2C] flex items-center gap-1.5">
                      <span>Composite Series Identifier Auto-Detection</span>
                      <span className="text-[10px] bg-purple-100 text-purple-800 px-2 py-0.5 rounded-full font-semibold">
                        Entity Dimensions
                      </span>
                    </div>
                    <p className="text-[11px] text-[#5F5670]">
                      Multiple entity columns were detected (excluding explanatory covariates like price/promo). Confirm which columns distinguish separate time series (e.g. <span className="font-mono text-purple-700">store_id + item_id</span>):
                    </p>
                  </div>

                  {(customMapping.composite_series_keys || []).length > 0 && (
                    <span className="text-[10px] font-bold px-2.5 py-1 rounded-full bg-emerald-100 text-emerald-800 shrink-0">
                      Composite Key Active: {customMapping.composite_series_keys.join(' + ')}
                    </span>
                  )}
                </div>

                <div className="flex flex-wrap gap-2 pt-1">
                  {Array.from(new Set([
                    ...(analysis.mapping?.candidate_entity_columns || []),
                    ...(customMapping.composite_series_keys || [])
                  ])).map((col) => {
                    const isSelected = (customMapping.composite_series_keys || []).includes(col);
                    return (
                      <button
                        key={col}
                        type="button"
                        onClick={() => handleToggleCompositeKey(col)}
                        className={`px-3 py-1.5 rounded-xl text-xs font-medium transition-all flex items-center gap-1.5 border ${
                          isSelected
                            ? 'bg-[#A294F9] text-white border-[#A294F9] shadow-xs'
                            : 'bg-white text-[#1F1B2C] border-[#CDC1FF] hover:border-[#A294F9]'
                        }`}
                        data-testid={`composite-col-${col}`}
                      >
                        <span className="font-mono">{col}</span>
                        {isSelected ? <Check className="w-3 h-3 text-white" /> : <span className="text-[10px] text-gray-400">+ Add</span>}
                      </button>
                    );
                  })}
                </div>
              </div>
            )}

            {/* Optional Detected Columns Section */}
            <div>
              <div className="text-xs font-bold text-[#1F1B2C] mb-2">
                Optional Detected Columns & Roles:
              </div>
              {(!analysis.mapping?.optional || analysis.mapping.optional.length === 0) ? (
                <div className="p-3 rounded-xl bg-gray-50 border border-gray-200 text-xs text-[#5F5670]">
                  No optional columns detected in this CSV. The forecasting models will run using univariate lag features.
                </div>
              ) : (
                <div className="grid grid-cols-2 sm:grid-cols-3 lg:grid-cols-4 gap-2.5">
                  {analysis.mapping.optional.map((opt, i) => (
                    <div key={i} className="p-3 rounded-xl bg-white border border-[#E5D9F2] text-xs space-y-1">
                      <div className="font-semibold text-[#1F1B2C] truncate font-mono">
                        {opt.name}
                      </div>
                      <div className="text-[10px] text-[#A294F9] font-medium">
                        {opt.role}
                      </div>
                    </div>
                  ))}
                </div>
              )}
            </div>
          </section>

          {/* 3. DATA QUALITY UI */}
          <section className="p-6 lg:p-8 rounded-3xl bg-white border border-[#E5D9F2] shadow-xs space-y-6" data-testid="data-quality-section">
            <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-3">
              <div>
                <div className="text-xs font-semibold uppercase tracking-wider text-[#8E83A3]">
                  Diagnostic Audit
                </div>
                <h2 className="text-xl font-bold font-heading text-[#1F1B2C]">
                  Data Quality & Integrity
                </h2>
                <p className="text-xs text-[#5F5670]">
                  Transparent inspection of missing values, timestamp conflicts, and potential data leakage.
                </p>
              </div>

              <div className="flex items-center gap-2">
                <span className={`px-3 py-1 rounded-full text-xs font-bold ${
                  analysis.quality.overallStatus === 'FORECAST READY'
                    ? 'bg-emerald-100 text-emerald-800'
                    : 'bg-amber-100 text-amber-800'
                }`}>
                  Audit: {analysis.quality.overallStatus}
                </span>
              </div>
            </div>

            {/* Quality Metrics Grid */}
            <div className="grid grid-cols-2 sm:grid-cols-3 lg:grid-cols-5 gap-3.5 text-xs">
              <div className="p-4 rounded-2xl bg-[#F5EFFF]/50 border border-[#E5D9F2] space-y-1">
                <div className="text-[#8E83A3]">Missing Entries</div>
                <div className="text-lg font-bold text-[#1F1B2C]">
                  {analysis.quality.missingValuesCount}
                </div>
                <div className="text-[10px] text-[#5F5670]">
                  {analysis.quality.missingPct}% of cells
                </div>
              </div>

              <div className="p-4 rounded-2xl bg-[#F5EFFF]/50 border border-[#E5D9F2] space-y-1">
                <div className="text-[#8E83A3]">Duplicate Rows</div>
                <div className="text-lg font-bold text-[#1F1B2C]">
                  {analysis.quality.duplicateRowsCount}
                </div>
                <div className="text-[10px] text-[#5F5670]">
                  Exact duplicate records
                </div>
              </div>

              <div className="p-4 rounded-2xl bg-[#F5EFFF]/50 border border-[#E5D9F2] space-y-1">
                <div className="text-[#8E83A3]">Timestamp Conflicts</div>
                <div className="text-lg font-bold text-[#1F1B2C]">
                  {analysis.quality.conflictingPairsCount}
                </div>
                <div className="text-[10px] text-[#5F5670]">
                  Same series + date pairs
                </div>
              </div>

              <div className="p-4 rounded-2xl bg-[#F5EFFF]/50 border border-[#E5D9F2] space-y-1">
                <div className="text-[#8E83A3]">Invalid Dates</div>
                <div className="text-lg font-bold text-[#1F1B2C]">
                  {analysis.quality.invalidDatesCount}
                </div>
                <div className="text-[10px] text-[#5F5670]">
                  Unparseable timestamps
                </div>
              </div>

              <div className="p-4 rounded-2xl bg-[#F5EFFF]/50 border border-[#E5D9F2] space-y-1">
                <div className="text-[#8E83A3]">Negative Values</div>
                <div className="text-lg font-bold text-[#1F1B2C]">
                  {analysis.quality.negativeTargetCount}
                </div>
                <div className="text-[10px] text-[#5F5670]">
                  Review if returns exist
                </div>
              </div>
            </div>

            {/* Phase 3 Real Data Cleaning & Preprocessing Report */}
            {analysis.cleaning && (

              <div className="pt-3 border-t border-[#E5D9F2] space-y-3">
                <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-2">
                  <div className="text-xs font-bold text-[#1F1B2C]">
                    Data Cleaning & Series Deduplication Engine:
                  </div>
                  <span className={`text-[10px] font-bold px-2.5 py-0.5 rounded-full ${
                    analysis.pipelineStatus === 'READY FOR MODEL TRAINING'
                      ? 'bg-emerald-100 text-emerald-800'
                      : 'bg-amber-100 text-amber-800'
                  }`}>
                    Pipeline: {analysis.pipelineStatus}
                  </span>
                </div>

                <div className="grid grid-cols-2 sm:grid-cols-4 gap-3 text-xs">
                  <div className="p-3 rounded-xl bg-white border border-[#E5D9F2]">
                    <div className="text-[10px] text-[#8E83A3]">Cleaned Records</div>
                    <div className="font-bold text-[#1F1B2C]" data-testid="cleaned-rows-count">{analysis.cleaning.cleaned_rows}</div>
                    <div className="text-[9px] text-[#5F5670]">of {analysis.cleaning.original_rows} raw ({analysis.cleaning.eligible_for_training_row_count || analysis.cleaning.cleaned_rows} eligible)</div>
                  </div>
                  <div className="p-3 rounded-xl bg-white border border-[#E5D9F2]">
                    <div className="text-[10px] text-[#8E83A3]">Deduplicated Rows</div>
                    <div className="font-bold text-[#1F1B2C]">{analysis.cleaning.exact_duplicates_removed}</div>
                    <div className="text-[9px] text-[#5F5670]">exact matches purged</div>
                  </div>
                  <div className="p-3 rounded-xl bg-white border border-[#E5D9F2]">
                    <div className="text-[10px] text-[#8E83A3]">Conflict Resolution</div>
                    <div className="font-bold text-[#1F1B2C]">{analysis.cleaning.conflicts_resolved}</div>
                    <div className="text-[9px] text-[#5F5670]">{analysis.cleaning.aggregation_rule}</div>
                  </div>
                  <div className="p-3 rounded-xl bg-white border border-[#E5D9F2]">
                    <div className="text-[10px] text-[#8E83A3]">Zero Sales Kept</div>
                    <div className="font-bold text-[#1F1B2C]">{analysis.cleaning.zero_targets_preserved}</div>
                    <div className="text-[9px] text-[#5F5670]">genuine raw zeros preserved</div>
                  </div>
                </div>

                {(analysis.cleaning.summary_notes || []).length > 0 && (
                  <div className="space-y-1.5 pt-1">
                    {(analysis.cleaning.summary_notes || []).map((note, idx) => (
                      <div key={idx} className="p-2.5 rounded-lg bg-[#F5EFFF]/60 text-[11px] text-[#5F5670] flex items-center gap-2 border border-[#CDC1FF]/40">
                        <Check className="w-3.5 h-3.5 text-emerald-600 shrink-0" />
                        <span>{note}</span>
                      </div>
                    ))}
                  </div>
                )}
              </div>
            )}

            {/* Chronological Train / Val / Test Splits Card */}
            {analysis.splits && analysis.splits.train && analysis.splits.val && analysis.splits.test && (
              <div className="pt-3 border-t border-[#E5D9F2] space-y-2.5">
                <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-1">
                  <div className="text-xs font-bold text-[#1F1B2C]">
                    Chronological Train / Validation / Test Temporal Splits:
                  </div>
                  <div className="flex items-center gap-2">
                    {analysis.splits.split_ratio && (
                      <span className="text-[10px] font-bold px-2 py-0.5 rounded-full bg-emerald-100 text-emerald-800" data-testid="split-ratio-badge">
                        Split: {analysis.splits.split_ratio}
                      </span>
                    )}
                    <span className="text-[10px] font-semibold text-[#8E83A3]">
                      {analysis.splits.split_strategy}
                    </span>
                    <span className="text-[10px] font-bold px-2 py-0.5 rounded-full bg-purple-100 text-purple-800" data-testid="split-reconciliation-total">
                      Total: {((analysis.splits.train_row_count || analysis.splits.train.rows_count) + (analysis.splits.validation_row_count || analysis.splits.val.rows_count) + (analysis.splits.test_row_count || analysis.splits.test.rows_count))} / {analysis.cleaning?.cleaned_rows || analysis.profile.rowsCount} Cleaned Rows
                    </span>
                  </div>
                </div>

                <div className="grid grid-cols-1 md:grid-cols-3 gap-3 text-xs">
                  <div className="p-3 rounded-xl bg-purple-50/60 border border-purple-200">
                    <div className="font-bold text-purple-900">{analysis.splits.train.name}</div>
                    <div className="text-[11px] text-purple-700">{analysis.splits.train.start_date} to {analysis.splits.train.end_date}</div>
                    <div className="text-[10px] text-purple-600 mt-1" data-testid="split-train-count">{analysis.splits.train_row_count || analysis.splits.train.rows_count} rows ({analysis.splits.train.series_count} series)</div>
                  </div>
                  <div className="p-3 rounded-xl bg-indigo-50/60 border border-indigo-200">
                    <div className="font-bold text-indigo-900">{analysis.splits.val.name}</div>
                    <div className="text-[11px] text-indigo-700">{analysis.splits.val.start_date} to {analysis.splits.val.end_date}</div>
                    <div className="text-[10px] text-indigo-600 mt-1" data-testid="split-val-count">{analysis.splits.validation_row_count || analysis.splits.val.rows_count} rows ({analysis.splits.val.series_count} series)</div>
                  </div>
                  <div className="p-3 rounded-xl bg-emerald-50/60 border border-emerald-200">
                    <div className="font-bold text-emerald-900">{analysis.splits.test.name}</div>
                    <div className="text-[11px] text-emerald-700">{analysis.splits.test.start_date} to {analysis.splits.test.end_date}</div>
                    <div className="text-[10px] text-emerald-600 mt-1" data-testid="split-test-count">{analysis.splits.test_row_count || analysis.splits.test.rows_count} rows ({analysis.splits.test.series_count} series)</div>
                  </div>
                </div>
              </div>
            )}

            {/* Quality Issues / Warnings Box */}
            {((analysis.quality?.statusIssues || []).length > 0 || (analysis.quality?.featureWarnings || []).length > 0 || (analysis.quality?.leakageWarnings || []).length > 0) && (
              <div className="space-y-3 pt-2">
                {(analysis.quality?.statusIssues || []).map((issue, idx) => (
                  <div key={idx} className="p-3.5 rounded-xl bg-red-50 border border-red-200 text-red-800 text-xs flex items-center gap-2.5">
                    <AlertCircle className="w-4 h-4 text-red-600 shrink-0" />
                    <span className="font-semibold">{issue}</span>
                  </div>
                ))}

                {(analysis.quality?.featureWarnings || []).map((warn, idx) => (
                  <div key={idx} className="p-3.5 rounded-xl bg-amber-50 border border-amber-200 text-amber-800 text-xs flex items-center gap-2.5">
                    <AlertTriangle className="w-4 h-4 text-amber-600 shrink-0" />
                    <span>{warn}</span>
                  </div>
                ))}

                {(analysis.quality?.leakageWarnings || []).map((leak, idx) => (
                  <div key={idx} className="p-3.5 rounded-xl bg-purple-50 border border-purple-200 text-purple-900 text-xs flex items-center gap-2.5">
                    <Info className="w-4 h-4 text-purple-600 shrink-0" />
                    <span><strong>Data Leakage Alert:</strong> {leak}</span>
                  </div>
                ))}
              </div>
            )}
          </section>



          {/* 4. FORECAST READINESS & HORIZON FEASIBILITY */}
          {analysis.readiness && (
            <section className="p-6 lg:p-8 rounded-3xl bg-white border border-[#E5D9F2] shadow-xs space-y-6" data-testid="forecast-readiness-section">
              <div>
                <div className="text-xs font-semibold uppercase tracking-wider text-[#8E83A3]">
                  Training Readiness
                </div>
                <h2 className="text-xl font-bold font-heading text-[#1F1B2C]">
                  Forecast Readiness & Horizon Feasibility
                </h2>
                <p className="text-xs text-[#5F5670]">
                  Pre-flight checklist to verify compatibility with short, medium, and long-term multi-horizon forecasting models.
                </p>
              </div>

              {/* Readiness Checklist */}
              <div className="space-y-2.5">
                {(analysis.readiness.checklist || []).map((item, i) => (
                  <div key={i} className="p-3.5 rounded-xl bg-[#F5EFFF]/50 border border-[#E5D9F2] flex items-center justify-between text-xs">
                    <div className="flex items-center gap-3">
                      <div className={`w-5 h-5 rounded-full flex items-center justify-center shrink-0 ${
                        item.passed ? 'bg-emerald-500 text-white' : 'bg-amber-500 text-white'
                      }`}>
                        {item.passed ? <Check className="w-3 h-3" /> : <AlertTriangle className="w-3 h-3" />}
                      </div>
                      <div>
                        <div className="font-bold text-[#1F1B2C]">{item.title}</div>
                        <div className="text-[11px] text-[#5F5670]">{item.detail}</div>
                      </div>
                    </div>

                    <span className={`text-[10px] font-bold px-2.5 py-0.5 rounded-full ${
                      item.passed ? 'bg-emerald-100 text-emerald-800' : 'bg-amber-100 text-amber-800'
                    }`}>
                      {item.passed ? 'PASSED' : 'REVIEW'}
                    </span>
                  </div>
                ))}
              </div>

              {/* Multi-Horizon Feasibility Cards */}
              <div className="grid grid-cols-1 md:grid-cols-3 gap-4 pt-2">
                {Object.values(analysis.readiness.horizons || {}).map((h) => (
                  <div key={h.days} className="p-4 rounded-2xl bg-white border border-[#E5D9F2] space-y-2">
                    <div className="flex items-center justify-between">
                      <span className="text-xs font-bold text-[#1F1B2C]">{h.label}</span>
                      <span className={`text-[10px] font-semibold px-2 py-0.5 rounded-full ${
                        h.status === 'Supported' 
                          ? 'bg-emerald-100 text-emerald-700' 
                          : 'bg-amber-100 text-amber-700'
                      }`}>
                        {h.status}
                      </span>
                    </div>
                    <p className="text-[11px] text-[#5F5670] leading-relaxed">
                      {h.note}
                    </p>
                  </div>
                ))}
              </div>

              {/* Model Compatibility Grid */}
              <div className="pt-2">
                <div className="text-xs font-bold text-[#1F1B2C] mb-3">
                  Supported Model Architecture Compatibility:
                </div>
                <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-3">
                  {(analysis.readiness.models || []).map((mod, idx) => (
                    <div key={idx} className="p-3.5 rounded-xl bg-[#F5EFFF]/40 border border-[#E5D9F2] text-xs space-y-1">
                      <div className="flex items-center justify-between">
                        <span className="font-bold text-[#1F1B2C]">{mod.model}</span>
                        <span className={`text-[9px] font-bold px-1.5 py-0.5 rounded-md ${
                          mod.ready ? 'bg-emerald-100 text-emerald-700' : 'bg-gray-100 text-gray-600'
                        }`}>
                          {mod.ready ? 'Compatible' : 'Limited'}
                        </span>
                      </div>
                      <div className="text-[10px] text-[#A294F9] font-medium">{mod.type}</div>
                      <p className="text-[10px] text-[#5F5670] leading-snug pt-1">
                        {mod.requirement}
                      </p>
                    </div>
                  ))}
                </div>
              </div>
            </section>
          )}

          {/* 5. DATA PREVIEW TABLE */}
          <section className="p-6 lg:p-8 rounded-3xl bg-white border border-[#E5D9F2] shadow-xs space-y-4" data-testid="data-preview-section">
            <div>
              <div className="text-xs font-semibold uppercase tracking-wider text-[#8E83A3]">
                Verification Sample
              </div>
              <h2 className="text-xl font-bold font-heading text-[#1F1B2C]">
                First 5 Observation Rows
              </h2>
              <p className="text-xs text-[#5F5670]">
                Preview of parsed rows with mandatory and optional column headers.
              </p>
            </div>

            <div className="overflow-x-auto rounded-2xl border border-[#E5D9F2]">
              <table className="w-full text-left text-xs border-collapse">
                <thead>
                  <tr className="bg-[#F5EFFF] text-[#1F1B2C] border-b border-[#E5D9F2]">
                    {(analysis.profile?.headers || []).map(h => {
                      const isMandatory = h === customMapping.date || h === customMapping.series_id || h === customMapping.target;
                      return (
                        <th key={h} className="py-2.5 px-3 font-semibold whitespace-nowrap">
                          <span className={isMandatory ? 'text-[#A294F9] font-bold' : ''}>
                            {h}
                          </span>
                          {isMandatory && (
                            <span className="ml-1 text-[9px] px-1 py-0.2 bg-[#A294F9] text-white rounded-xs">
                              Key
                            </span>
                          )}
                        </th>
                      );
                    })}
                  </tr>
                </thead>
                <tbody className="divide-y divide-[#F5EFFF]">
                  {(analysis.previewRows || []).map((row, rIdx) => (
                    <tr key={rIdx} className="hover:bg-[#F5EFFF]/40 font-mono text-[11px]">
                      {(analysis.profile?.headers || []).map((h, cIdx) => (
                        <td key={cIdx} className="py-2 px-3 whitespace-nowrap text-[#5F5670]">
                          {row[h] !== undefined && row[h] !== '' ? row[h] : <span className="text-gray-300 italic">empty</span>}
                        </td>
                      ))}
                    </tr>
                  ))}
                  {(!analysis.previewRows || analysis.previewRows.length === 0) && (
                    <tr>
                      <td colSpan={analysis.profile?.headers?.length || 1} className="py-4 text-center text-xs text-[#5F5670] italic">
                        Preview rows loaded from backend profile.
                      </td>
                    </tr>
                  )}
                </tbody>
              </table>
            </div>
          </section>

          {/* Final Call to Action */}
          <div className="p-6 rounded-3xl bg-gradient-to-r from-white via-[#F5EFFF]/60 to-white border border-[#CDC1FF] flex flex-col sm:flex-row items-center justify-between gap-4">
            <div className="space-y-1">
              <h3 className="font-bold text-base text-[#1F1B2C]">
                Dataset verified and mapped successfully
              </h3>
              <p className="text-xs text-[#5F5670]">
                Proceed to the Forecasting Engine to configure horizons (7D, 28D, 90D) and choose between statistical, ML, or deep architectures.
              </p>
            </div>

            <button
              onClick={() => onNavigate('forecast')}
              className="px-6 py-3 rounded-xl bg-[#A294F9] text-white text-xs font-bold hover:bg-[#9181f7] shadow-sm transition-all flex items-center gap-2 shrink-0"
              data-testid="bottom-continue-btn"
            >
              <span>Continue to Forecast</span>
              <ArrowRight className="w-4 h-4" />
            </button>
          </div>
        </div>
      )}
    </div>
  );
}
