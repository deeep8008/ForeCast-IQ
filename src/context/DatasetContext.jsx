import React, { createContext, useContext, useState, useEffect, useCallback, useRef } from 'react';
import { api } from '../services/api';

const DatasetContext = createContext(null);

export function DatasetProvider({ children }) {
  const [activeDatasetId, setActiveDatasetId] = useState(null);
  const [availableDatasets, setAvailableDatasets] = useState([]);
  const [datasetSummary, setDatasetSummary] = useState(null);
  const [splitMetadata, setSplitMetadata] = useState(null);
  const [benchmarkResults, setBenchmarkResults] = useState(null);
  
  // Forecast parameters & results
  const [selectedModel, setSelectedModel] = useState('lightgbm');
  const [selectedHorizon, setSelectedHorizon] = useState(28);
  const [selectedSeriesId, setSelectedSeriesId] = useState(null);
  const [currentInventory, setCurrentInventory] = useState('');
  const [forecastResult, setForecastResult] = useState(null);

  // Upload & Column Mapping workflow state
  const [isUploadModalOpen, setIsUploadModalOpen] = useState(false);
  const [uploadPreview, setUploadPreview] = useState(null);

  // Loading & Error States
  const [isLoading, setIsLoading] = useState(false);
  const [loadingMessage, setLoadingMessage] = useState('');
  const [error, setError] = useState(null);
  const [backendOnline, setBackendOnline] = useState(false);

  const activeDatasetIdRef = useRef(null);
  activeDatasetIdRef.current = activeDatasetId;

  const selectedSeriesIdRef = useRef(selectedSeriesId);
  selectedSeriesIdRef.current = selectedSeriesId;

  const currentInventoryRef = useRef(currentInventory);
  currentInventoryRef.current = currentInventory;

  const clearError = useCallback(() => setError(null), []);

  // Helper to safely load summary
  const fetchSummary = useCallback(async (datasetId) => {
    if (!datasetId) return null;
    try {
      setIsLoading(true);
      setLoadingMessage('Loading dataset summary...');

      // Restore any cached benchmark or forecast for this dataset
      try {
        const cachedBench = sessionStorage.getItem(`forecastiq_benchmark_${datasetId}`);
        if (cachedBench) {
          const parsed = JSON.parse(cachedBench);
          setBenchmarkResults(parsed);
          if (parsed.leaderboard?.length > 0) {
            setSelectedModel(parsed.leaderboard[0].model_key);
          }
        }
        const cachedFc = sessionStorage.getItem(`forecastiq_forecast_${datasetId}`);
        if (cachedFc) {
          setForecastResult(JSON.parse(cachedFc));
        }
      } catch (e) {
        console.warn('Storage restore warning:', e);
      }

      const summary = await api.exploreDataset(datasetId);
      if (summary && summary.total_observations !== undefined) {
        setDatasetSummary(summary);
        if (summary.series_ids?.length > 0) {
          setSelectedSeriesId(prev => {
            if (prev && summary.series_ids.includes(prev)) {
              return prev;
            }
            return summary.series_ids[0];
          });
        } else {
          setSelectedSeriesId(null);
        }
        setError(null);
        return summary;
      }
    } catch (err) {
      console.warn(`Notice: Summary for ${datasetId} unavailable (${err.message}).`);
    } finally {
      setIsLoading(false);
      setLoadingMessage('');
    }
    return null;
  }, []);

  // Safe single-shot initialization on mount ONLY
  useEffect(() => {
    let cancelled = false;

    async function init() {
      try {
        const isHealthy = await api.checkHealth();
        if (cancelled) return;
        setBackendOnline(isHealthy);
        if (!isHealthy) return;

        const listRes = await api.listDatasets().catch(() => ({ datasets: [] }));
        if (cancelled) return;
        const datasets = listRes.datasets || [];
        setAvailableDatasets(datasets);

        if (datasets.length > 0) {
          const m5Match = datasets.find(d => d.dataset_id === 'm5_reference' || d.dataset_id.startsWith('m5'));
          const targetId = m5Match ? m5Match.dataset_id : datasets[0].dataset_id;
          setActiveDatasetId(targetId);
          await fetchSummary(targetId);
        }
      } catch (err) {
        if (!cancelled) {
          setBackendOnline(false);
          console.warn('Backend server offline:', err);
        }
      }
    }

    init();

    return () => {
      cancelled = true;
    };
  }, [fetchSummary]);

  // Reset workflow back to initial state (removes benchmark, forecast, active dataset)
  const resetWorkflow = useCallback(() => {
    setActiveDatasetId(null);
    setDatasetSummary(null);
    setSplitMetadata(null);
    setBenchmarkResults(null);
    setForecastResult(null);
    setSelectedSeriesId(null);
    setUploadPreview(null);
    setError(null);
    activeDatasetIdRef.current = null;
    selectedSeriesIdRef.current = null;
    try {
      sessionStorage.clear();
    } catch (e) {
      console.warn('Session storage clear warning:', e);
    }
  }, []);

  // 1-Click Preload M5 Benchmark
  const preloadM5Dataset = useCallback(async (aggregationLevel = 'total', maxDays = 500) => {
    try {
      setIsLoading(true);
      setLoadingMessage(`Preloading M5 benchmark dataset (${aggregationLevel})...`);
      setError(null);
      
      const res = await api.preloadM5({
        aggregation_level: aggregationLevel,
        max_days: maxDays,
        max_series: 10
      });

      const targetId = res.dataset_id || 'm5_reference';
      setActiveDatasetId(targetId);
      await fetchSummary(targetId);
      setIsUploadModalOpen(false);
      return res;
    } catch (err) {
      setError(err.message || 'Failed to preload M5 benchmark');
      throw err;
    } finally {
      setIsLoading(false);
      setLoadingMessage('');
    }
  }, [fetchSummary]);

  // Upload generic CSV or folder
  const uploadFiles = useCallback(async (fileList, datasetName) => {
    try {
      setIsLoading(true);
      setLoadingMessage('Uploading and scanning CSV files...');
      setError(null);

      const preview = await api.uploadDataset(fileList, datasetName);
      setUploadPreview(preview);
      return preview;
    } catch (err) {
      setError(err.message || 'Failed to upload files');
      throw err;
    } finally {
      setIsLoading(false);
      setLoadingMessage('');
    }
  }, []);

  // Confirm and Map Schema
  const mapAndProcessSchema = useCallback(async (mappingPayload) => {
    try {
      setIsLoading(true);
      setLoadingMessage('Converting to Canonical Schema & regularizing...');
      setError(null);

      const res = await api.mapSchema(mappingPayload);
      setActiveDatasetId(res.dataset_id);
      setUploadPreview(null);
      setIsUploadModalOpen(false);
      
      await fetchSummary(res.dataset_id);
      return res;
    } catch (err) {
      setError(err.message || 'Failed to map schema');
      throw err;
    } finally {
      setIsLoading(false);
      setLoadingMessage('');
    }
  }, [fetchSummary]);

  // Chronological Split
  const runSplit = useCallback(async (trainPercentage = 0.80, fixedTestDays = null, seriesId = null) => {
    try {
      setIsLoading(true);
      setLoadingMessage('Preparing training & test data...');
      setError(null);

      const res = await api.splitDataset({
        dataset_id: activeDatasetIdRef.current,
        train_percentage: trainPercentage,
        fixed_test_days: fixedTestDays,
        series_id: seriesId || selectedSeriesIdRef.current,
      });

      setSplitMetadata(res);
      return res;
    } catch (err) {
      setError(err.message || 'Failed to perform chronological split');
      throw err;
    } finally {
      setIsLoading(false);
      setLoadingMessage('');
    }
  }, []);

  // Run 5-Model Historical Benchmark (Phase 3)
  const runBenchmark = useCallback(async (models = ['arima', 'prophet', 'lightgbm', 'deepar', 'tft'], trainPct = 0.80, fixedTestDays = null) => {
    try {
      setIsLoading(true);
      setLoadingMessage('Training and testing 5 AI models... please wait');
      setError(null);

      const targetDatasetId = activeDatasetIdRef.current || 'm5_reference';
      const res = await api.runBenchmark({
        dataset_id: targetDatasetId,
        candidate_models: models,
        train_percentage: trainPct,
        fixed_test_days: fixedTestDays,
        series_id: selectedSeriesIdRef.current,
      });

      setBenchmarkResults(res);
      try {
        sessionStorage.setItem(`forecastiq_benchmark_${targetDatasetId}`, JSON.stringify(res));
      } catch (e) {
        console.warn('Storage save warning:', e);
      }

      if (res.leaderboard && res.leaderboard.length > 0) {
        setSelectedModel(res.leaderboard[0].model_key);
      }

      return res;
    } catch (err) {
      setError(err.message || 'Failed to execute model benchmark');
      throw err;
    } finally {
      setIsLoading(false);
      setLoadingMessage('');
    }
  }, []);

  // Run Future Forecast & Business Insights (Phase 4)
  const runFutureForecast = useCallback(async (modelKey = null, horizon = null, seriesId = null, inventory = null) => {
    try {
      setIsLoading(true);
      setLoadingMessage('Calculating future demand numbers... please wait');
      setError(null);

      const targetDatasetId = activeDatasetIdRef.current || 'm5_reference';
      const targetModel = modelKey || 'lightgbm';
      const targetHorizon = horizon || 28;
      const targetSeries = seriesId || selectedSeriesIdRef.current;
      const targetInventory = inventory !== null && inventory !== undefined && inventory !== '' 
        ? inventory 
        : currentInventoryRef.current;

      const res = await api.runForecast({
        dataset_id: targetDatasetId,
        model: targetModel,
        horizon: targetHorizon,
        series_id: targetSeries,
        current_inventory: targetInventory,
      });

      setForecastResult(res);
      try {
        sessionStorage.setItem(`forecastiq_forecast_${targetDatasetId}`, JSON.stringify(res));
      } catch (e) {
        console.warn('Storage save warning:', e);
      }
      return res;
    } catch (err) {
      setError(err.message || 'Failed to generate future forecast');
      throw err;
    } finally {
      setIsLoading(false);
      setLoadingMessage('');
    }
  }, []);

  // CSV Exporter for Future Forecast
  const exportForecastToCsv = useCallback(() => {
    if (!forecastResult || !forecastResult.forecast) return;

    const headers = ['date', 'prediction', 'lower_80', 'upper_80', 'lower_95', 'upper_95'];
    const rows = forecastResult.forecast.map(pt => [
      pt.timestamp,
      pt.prediction,
      pt.lower_80,
      pt.upper_80,
      pt.lower_95,
      pt.upper_95,
    ]);

    const csvContent = 'data:text/csv;charset=utf-8,' + 
      [headers.join(','), ...rows.map(e => e.join(','))].join('\n');

    const encodedUri = encodeURI(csvContent);
    const link = document.createElement('a');
    link.setAttribute('href', encodedUri);
    link.setAttribute('download', `ForecastIQ_${forecastResult.dataset_id}_${forecastResult.selected_model}_${forecastResult.horizon}d.csv`);
    document.body.appendChild(link);
    link.click();
    document.body.removeChild(link);
  }, [forecastResult]);

  return (
    <DatasetContext.Provider
      value={{
        activeDatasetId,
        setActiveDatasetId,
        availableDatasets,
        datasetSummary,
        splitMetadata,
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
        setForecastResult,
        isUploadModalOpen,
        setIsUploadModalOpen,
        uploadPreview,
        setUploadPreview,
        isLoading,
        loadingMessage,
        error,
        clearError,
        backendOnline,
        // Stable Handlers
        fetchSummary,
        preloadM5Dataset,
        uploadFiles,
        mapAndProcessSchema,
        resetWorkflow,
        runSplit,
        runBenchmark,
        runFutureForecast,
        exportForecastToCsv,
      }}
    >
      {children}
    </DatasetContext.Provider>
  );
}

export function useDataset() {
  const context = useContext(DatasetContext);
  if (!context) {
    throw new Error('useDataset must be used within a DatasetProvider');
  }
  return context;
}
