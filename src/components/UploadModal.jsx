import React, { useState, useRef } from 'react';
import { 
  X, 
  Upload, 
  FolderUp, 
  Database, 
  Check, 
  AlertCircle, 
  ArrowRight, 
  Sparkles, 
  FileSpreadsheet, 
  Layers
} from 'lucide-react';
import { useDataset } from '../context/DatasetContext';

export default function UploadModal() {
  const { 
    isUploadModalOpen, 
    setIsUploadModalOpen, 
    uploadFiles, 
    mapAndProcessSchema, 
    preloadM5Dataset, 
    uploadPreview, 
    setUploadPreview,
    availableDatasets,
    setActiveDatasetId,
    fetchSummary,
    isLoading,
    loadingMessage,
    error,
    clearError
  } = useDataset();

  const [activeTab, setActiveTab] = useState('upload'); // 'upload', 'm5', 'existing'
  const [selectedFiles, setSelectedFiles] = useState([]);
  const [datasetName, setDatasetName] = useState('');
  const [dragActive, setDragActive] = useState(false);
  const [clientWarning, setClientWarning] = useState('');

  // Column Mapping State
  const [timeCol, setTimeCol] = useState('');
  const [targetCol, setTargetCol] = useState('');
  const [seriesCol, setSeriesCol] = useState('');
  const [secondarySeriesCol, setSecondarySeriesCol] = useState('');
  const [selectedFileForMapping, setSelectedFileForMapping] = useState('');

  // M5 Preload options
  const [m5Aggregation, setM5Aggregation] = useState('total');
  const [m5MaxDays, setM5MaxDays] = useState(500);

  const fileInputRef = useRef(null);
  const folderInputRef = useRef(null);

  if (!isUploadModalOpen) return null;

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
      handleFiles(Array.from(e.dataTransfer.files));
    }
  };

  const handleFileChange = (e) => {
    if (e.target.files && e.target.files.length > 0) {
      handleFiles(Array.from(e.target.files));
    }
  };

  const handleFiles = (files) => {
    setClientWarning('');
    clearError();
    const csvFiles = files.filter(f => f.name.toLowerCase().endsWith('.csv'));
    if (csvFiles.length === 0) {
      setClientWarning('⚠️ No .csv files found in the selection. Please select one or more .csv files.');
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
      setClientWarning('Please select at least one CSV file before submitting.');
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
        if (preview.csv_files && preview.csv_files.length > 0) {
          setSelectedFileForMapping(preview.csv_files[0]);
        }
      }
    } catch {
      // Error handled in context
    }
  };

  const handleConfirmMapping = async () => {
    if (!timeCol || !targetCol) {
      setClientWarning('Please select both a Timestamp column and a Target demand column.');
      return;
    }
    try {
      await mapAndProcessSchema({
        dataset_id: uploadPreview.dataset_id,
        time_column: timeCol,
        target_column: targetCol,
        series_id_column: seriesCol ? seriesCol : null,
        secondary_series_id_column: secondarySeriesCol ? secondarySeriesCol : null,
        selected_file: selectedFileForMapping || null,
        dynamic_covariates: [],
        static_covariates: []
      });
    } catch {
      // Error handled in context
    }
  };

  const handleM5Preload = async () => {
    try {
      await preloadM5Dataset(m5Aggregation, m5MaxDays ? Number(m5MaxDays) : null);
    } catch {
      // Error handled in context
    }
  };

  const handleSelectExisting = async (dsId) => {
    setActiveDatasetId(dsId);
    await fetchSummary(dsId);
    setIsUploadModalOpen(false);
  };

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-black/40 backdrop-blur-xs">
      <div className="relative w-full max-w-3xl bg-white rounded-3xl shadow-2xl border border-[#CDC1FF] overflow-hidden animate-in fade-in zoom-in-95 duration-150 max-h-[90vh] flex flex-col">
        {/* Modal Header */}
        <div className="p-6 border-b border-[#F5EFFF] flex items-center justify-between bg-gradient-to-r from-white via-[#F5EFFF]/30 to-white">
          <div className="flex items-center gap-3">
            <div className="w-10 h-10 rounded-2xl bg-[#F5EFFF] text-[#A294F9] border border-[#CDC1FF] flex items-center justify-center">
              <Database className="w-5 h-5" />
            </div>
            <div>
              <h2 className="text-xl font-bold font-heading text-[#1F1B2C]">
                Dataset Ingestion & Schema Mapping
              </h2>
              <p className="text-xs text-[#5F5670]">
                Upload generic time-series CSVs, multi-file folders, or load the M5 benchmark.
              </p>
            </div>
          </div>

          <button
            onClick={() => {
              setIsUploadModalOpen(false);
              setUploadPreview(null);
              clearError();
              setClientWarning('');
            }}
            className="p-2 rounded-xl text-[#8E83A3] hover:text-[#1F1B2C] hover:bg-[#F5EFFF] transition-colors"
          >
            <X className="w-5 h-5" />
          </button>
        </div>

        {/* Tab Navigation */}
        <div className="flex border-b border-[#E5D9F2] px-6 bg-[#F5EFFF]/40 text-xs font-semibold">
          <button
            onClick={() => setActiveTab('upload')}
            className={`py-3 px-4 border-b-2 transition-all flex items-center gap-2 ${
              activeTab === 'upload'
                ? 'border-[#A294F9] text-[#A294F9] font-bold bg-white'
                : 'border-transparent text-[#5F5670] hover:text-[#1F1B2C]'
            }`}
          >
            <Upload className="w-4 h-4" />
            <span>Upload Generic CSV / Folder</span>
          </button>

          <button
            onClick={() => setActiveTab('m5')}
            className={`py-3 px-4 border-b-2 transition-all flex items-center gap-2 ${
              activeTab === 'm5'
                ? 'border-[#A294F9] text-[#A294F9] font-bold bg-white'
                : 'border-transparent text-[#5F5670] hover:text-[#1F1B2C]'
            }`}
          >
            <Sparkles className="w-4 h-4" />
            <span>1-Click M5 Benchmark</span>
          </button>

          {availableDatasets.length > 0 && (
            <button
              onClick={() => setActiveTab('existing')}
              className={`py-3 px-4 border-b-2 transition-all flex items-center gap-2 ${
                activeTab === 'existing'
                  ? 'border-[#A294F9] text-[#A294F9] font-bold bg-white'
                  : 'border-transparent text-[#5F5670] hover:text-[#1F1B2C]'
              }`}
            >
              <Layers className="w-4 h-4" />
              <span>Processed Datasets ({availableDatasets.length})</span>
            </button>
          )}
        </div>

        {/* Error / Warning Alert Banner */}
        {(error || clientWarning) && (
          <div className="mx-6 mt-4 p-3.5 rounded-2xl bg-rose-50 border border-rose-200 text-rose-800 text-xs flex items-center justify-between gap-3">
            <div className="flex items-center gap-2">
              <AlertCircle className="w-4 h-4 text-rose-600 shrink-0" />
              <span>{error || clientWarning}</span>
            </div>
            <button 
              onClick={() => { clearError(); setClientWarning(''); }}
              className="text-rose-600 hover:text-rose-900 font-bold"
            >
              ✕
            </button>
          </div>
        )}

        {/* Modal Body */}
        <div className="p-6 overflow-y-auto space-y-6 flex-1">
          {/* TAB 1: CSV / FOLDER UPLOAD */}
          {activeTab === 'upload' && !uploadPreview && (
            <div className="space-y-4">
              {/* Drag and drop box */}
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
                  Drag & Drop CSV files or entire dataset folder
                </h3>
                <p className="text-xs text-[#5F5670] mt-1 max-w-sm mx-auto">
                  Works with any single-CSV time series or multi-file directory. Non-CSV files are ignored.
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

              {/* Selected Files List */}
              {selectedFiles.length > 0 && (
                <div className="p-4 rounded-2xl bg-[#F5EFFF] border border-[#E5D9F2] space-y-2">
                  <div className="flex items-center justify-between text-xs font-semibold text-[#1F1B2C]">
                    <span>Selected Files ({selectedFiles.length}):</span>
                    <span className="text-[11px] text-emerald-600 font-bold">
                      {selectedFiles.filter(f => f.name.endsWith('.csv')).length} valid CSV(s)
                    </span>
                  </div>
                  <div className="max-h-24 overflow-y-auto space-y-1 text-xs text-[#5F5670]">
                    {selectedFiles.slice(0, 5).map((f, i) => (
                      <div key={i} className="flex justify-between items-center bg-white px-3 py-1.5 rounded-lg border border-[#E5D9F2]">
                        <span className="truncate">{f.name}</span>
                        <span className="text-[10px] text-[#8E83A3]">{(f.size / 1024).toFixed(1)} KB</span>
                      </div>
                    ))}
                    {selectedFiles.length > 5 && (
                      <div className="text-[10px] text-[#8E83A3] text-center">
                        + {selectedFiles.length - 5} more files
                      </div>
                    )}
                  </div>

                  <div className="pt-2 flex items-center gap-3">
                    <input
                      type="text"
                      placeholder="Dataset Name (optional)"
                      value={datasetName}
                      onChange={(e) => setDatasetName(e.target.value)}
                      className="flex-1 bg-white border border-[#CDC1FF] rounded-xl px-3 py-2 text-xs font-medium text-[#1F1B2C] outline-none"
                    />
                    <button
                      onClick={handleUploadSubmit}
                      disabled={isLoading}
                      className="px-5 py-2 rounded-xl bg-[#A294F9] text-white text-xs font-semibold hover:bg-[#9181f7] shadow-xs cursor-pointer flex items-center gap-2 shrink-0"
                    >
                      <span>Upload & Inspect Schema</span>
                      <ArrowRight className="w-3.5 h-3.5" />
                    </button>
                  </div>
                </div>
              )}
            </div>
          )}

          {/* TAB 1 (Step 2): COLUMN MAPPING INTERFACE */}
          {activeTab === 'upload' && uploadPreview && (
            <div className="space-y-5">
              <div className="p-4 rounded-2xl bg-[#F5EFFF] border border-[#CDC1FF] flex items-center justify-between">
                <div>
                  <div className="text-xs font-bold text-[#1F1B2C]">
                    Dataset: {uploadPreview.dataset_name}
                  </div>
                  <div className="text-[11px] text-[#5F5670]">
                    Detected Type: <strong className="text-[#A294F9]">{uploadPreview.detected_type}</strong> • Total Rows: {uploadPreview.total_raw_rows.toLocaleString()}
                  </div>
                </div>
                <button
                  onClick={() => setUploadPreview(null)}
                  className="text-xs text-[#8E83A3] hover:text-[#1F1B2C] underline"
                >
                  Change Files
                </button>
              </div>

              {/* Column Mapping Selectors */}
              <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-4">
                {/* Time column */}
                <div className="space-y-1.5">
                  <label className="block text-xs font-bold text-[#1F1B2C]">
                    1. Timestamp Column <span className="text-rose-500">*</span>
                  </label>
                  <select
                    value={timeCol}
                    onChange={(e) => setTimeCol(e.target.value)}
                    className="w-full bg-[#F5EFFF] border border-[#CDC1FF] rounded-xl px-3 py-2 text-xs font-semibold text-[#1F1B2C] outline-none"
                  >
                    <option value="">Select timestamp col...</option>
                    {uploadPreview.available_columns.map(c => (
                      <option key={c} value={c}>{c}</option>
                    ))}
                  </select>
                  <p className="text-[10px] text-[#8E83A3]">
                    e.g. date, timestamp, ds, d
                  </p>
                </div>

                {/* Target Demand column */}
                <div className="space-y-1.5">
                  <label className="block text-xs font-bold text-[#1F1B2C]">
                    2. Target Demand <span className="text-rose-500">*</span>
                  </label>
                  <select
                    value={targetCol}
                    onChange={(e) => setTargetCol(e.target.value)}
                    className="w-full bg-[#F5EFFF] border border-[#CDC1FF] rounded-xl px-3 py-2 text-xs font-semibold text-[#1F1B2C] outline-none"
                  >
                    <option value="">Select target metric...</option>
                    {uploadPreview.available_columns.map(c => (
                      <option key={c} value={c}>{c}</option>
                    ))}
                  </select>
                  <p className="text-[10px] text-[#8E83A3]">
                    e.g. sales, units, revenue, demand
                  </p>
                </div>

                {/* Location / Group Column */}
                <div className="space-y-1.5">
                  <label className="block text-xs font-bold text-[#1F1B2C]">
                    3. Store / Location (Optional)
                  </label>
                  <select
                    value={secondarySeriesCol}
                    onChange={(e) => setSecondarySeriesCol(e.target.value)}
                    className="w-full bg-[#F5EFFF] border border-[#CDC1FF] rounded-xl px-3 py-2 text-xs font-semibold text-[#1F1B2C] outline-none"
                  >
                    <option value="">None (All Stores / Global)</option>
                    {uploadPreview.available_columns.map(c => (
                      <option key={c} value={c}>{c}</option>
                    ))}
                  </select>
                  <p className="text-[10px] text-[#8E83A3]">
                    e.g. store, branch, warehouse, city
                  </p>
                </div>

                {/* Series / Item ID column */}
                <div className="space-y-1.5">
                  <label className="block text-xs font-bold text-[#1F1B2C]">
                    4. Product / Item (Optional)
                  </label>
                  <select
                    value={seriesCol}
                    onChange={(e) => setSeriesCol(e.target.value)}
                    className="w-full bg-[#F5EFFF] border border-[#CDC1FF] rounded-xl px-3 py-2 text-xs font-semibold text-[#1F1B2C] outline-none"
                  >
                    <option value="">None (Single Product / Total)</option>
                    {uploadPreview.available_columns.map(c => (
                      <option key={c} value={c}>{c}</option>
                    ))}
                  </select>
                  <p className="text-[10px] text-[#8E83A3]">
                    e.g. item, sku, product_id, model
                  </p>
                </div>
              </div>

              {/* Data Preview Table */}
              {uploadPreview.preview_rows && uploadPreview.preview_rows.length > 0 && (
                <div className="space-y-2">
                  <div className="text-xs font-semibold text-[#1F1B2C]">
                    Data Preview (First 5 Rows):
                  </div>
                  <div className="overflow-x-auto border border-[#E5D9F2] rounded-2xl">
                    <table className="w-full text-left text-[11px] border-collapse">
                      <thead className="bg-[#F5EFFF] text-[#8E83A3]">
                        <tr>
                          {uploadPreview.available_columns.map(col => (
                            <th key={col} className={`py-2 px-3 font-semibold ${
                              col === timeCol ? 'text-[#A294F9] bg-[#E5D9F2]/50' : 
                              col === targetCol ? 'text-emerald-700 bg-emerald-50' : 
                              col === seriesCol ? 'text-indigo-700 bg-indigo-50' : ''
                            }`}>
                              {col}
                            </th>
                          ))}
                        </tr>
                      </thead>
                      <tbody className="divide-y divide-[#F5EFFF]">
                        {uploadPreview.preview_rows.slice(0, 5).map((row, idx) => (
                          <tr key={idx} className="hover:bg-[#F5EFFF]/30">
                            {uploadPreview.available_columns.map(col => (
                              <td key={col} className="py-1.5 px-3 truncate max-w-[150px]">
                                {String(row[col] ?? '')}
                              </td>
                            ))}
                          </tr>
                        ))}
                      </tbody>
                    </table>
                  </div>
                </div>
              )}

              {/* Confirm Mapping Action Button */}
              <div className="pt-2 flex justify-end gap-3">
                <button
                  onClick={() => setUploadPreview(null)}
                  className="px-4 py-2 rounded-xl bg-white border border-[#E5D9F2] text-xs font-semibold text-[#5F5670] hover:bg-[#F5EFFF]"
                >
                  Cancel
                </button>
                <button
                  onClick={handleConfirmMapping}
                  disabled={isLoading}
                  className="px-6 py-2 rounded-xl bg-[#A294F9] text-white text-xs font-semibold hover:bg-[#9181f7] shadow-xs flex items-center gap-2"
                >
                  <Check className="w-3.5 h-3.5" />
                  <span>Convert to Canonical Parquet & Ingest</span>
                </button>
              </div>
            </div>
          )}

          {/* TAB 2: 1-CLICK M5 BENCHMARK PRELOAD */}
          {activeTab === 'm5' && (
            <div className="space-y-6">
              <div className="p-5 rounded-2xl bg-gradient-to-br from-[#F5EFFF] to-[#E5D9F2]/40 border border-[#CDC1FF] space-y-3">
                <div className="flex items-center gap-2 text-xs font-bold text-[#1F1B2C]">
                  <Sparkles className="w-4 h-4 text-[#A294F9]" />
                  <span>Standardized M5 Forecasting Accuracy Dataset</span>
                </div>
                <p className="text-xs text-[#5F5670] leading-relaxed">
                  Directly ingest the Walmart M5 reference competition data from the server repository (sales_train_validation.csv & calendar.csv). The pipeline automatically computes aggregations and calendar alignments.
                </p>
              </div>

              <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
                {/* Aggregation Level */}
                <div className="space-y-1.5">
                  <label className="block text-xs font-bold text-[#1F1B2C]">
                    Aggregation Hierarchy Level
                  </label>
                  <select
                    value={m5Aggregation}
                    onChange={(e) => setM5Aggregation(e.target.value)}
                    className="w-full bg-[#F5EFFF] border border-[#CDC1FF] rounded-xl px-3 py-2 text-xs font-semibold text-[#1F1B2C] outline-none"
                  >
                    <option value="total">Level 1: Total Aggregated Sales (Fastest Baseline)</option>
                    <option value="store">Level 2: Store Level (10 Stores)</option>
                    <option value="dept">Level 3: Department Level (7 Departments)</option>
                    <option value="state">Level 4: State Level (CA, TX, WI)</option>
                  </select>
                </div>

                {/* Max Historical Days */}
                <div className="space-y-1.5">
                  <label className="block text-xs font-bold text-[#1F1B2C]">
                    Historical Days Window
                  </label>
                  <select
                    value={m5MaxDays}
                    onChange={(e) => setM5MaxDays(e.target.value ? Number(e.target.value) : '')}
                    className="w-full bg-[#F5EFFF] border border-[#CDC1FF] rounded-xl px-3 py-2 text-xs font-semibold text-[#1F1B2C] outline-none"
                  >
                    <option value="365">Last 365 Days (1 Year)</option>
                    <option value="500">Last 500 Days (Recommended for Fast Backtesting)</option>
                    <option value="1000">Last 1000 Days</option>
                    <option value="">All 1913 Days (Full Competition History)</option>
                  </select>
                </div>
              </div>

              <div className="pt-2 flex justify-end">
                <button
                  onClick={handleM5Preload}
                  disabled={isLoading}
                  className="px-6 py-2.5 rounded-xl bg-[#A294F9] text-white text-xs font-bold hover:bg-[#9181f7] shadow-xs flex items-center gap-2 cursor-pointer"
                >
                  <Sparkles className="w-4 h-4" />
                  <span>Preload M5 Dataset & Compute Canonical Parquet</span>
                </button>
              </div>
            </div>
          )}

          {/* TAB 3: EXISTING PROCESSED DATASETS */}
          {activeTab === 'existing' && (
            <div className="space-y-3">
              <p className="text-xs text-[#5F5670]">
                Select any previously processed canonical dataset stored in local parquet storage:
              </p>
              <div className="space-y-2">
                {availableDatasets.map((ds) => (
                  <div 
                    key={ds.dataset_id}
                    onClick={() => handleSelectExisting(ds.dataset_id)}
                    className="p-3.5 rounded-2xl bg-white border border-[#E5D9F2] hover:border-[#A294F9] hover:bg-[#F5EFFF]/50 transition-all cursor-pointer flex items-center justify-between"
                  >
                    <div className="flex items-center gap-3">
                      <Database className="w-4 h-4 text-[#A294F9]" />
                      <div>
                        <div className="text-xs font-bold text-[#1F1B2C]">{ds.dataset_id}</div>
                        <div className="text-[10px] text-[#8E83A3]">{ds.filename} • {(ds.size_bytes / 1024).toFixed(1)} KB</div>
                      </div>
                    </div>
                    <span className="text-xs font-semibold text-[#A294F9]">
                      Select Dataset →
                    </span>
                  </div>
                ))}
              </div>
            </div>
          )}
        </div>

        {/* Loading Overlay */}
        {isLoading && (
          <div className="absolute inset-0 bg-white/80 backdrop-blur-xs flex flex-col items-center justify-center p-6 text-center z-50">
            <div className="w-12 h-12 rounded-2xl bg-[#F5EFFF] border border-[#CDC1FF] flex items-center justify-center text-[#A294F9] animate-bounce mb-3">
              <Sparkles className="w-6 h-6" />
            </div>
            <div className="text-sm font-bold font-heading text-[#1F1B2C]">
              Processing Dataset...
            </div>
            <div className="text-xs text-[#5F5670] mt-1 max-w-sm">
              {loadingMessage || 'Validating schema, regularizing frequency and persisting canonical Parquet...'}
            </div>
          </div>
        )}
      </div>
    </div>
  );
}
