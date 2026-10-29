/**
 * API Service for ForecastIQ Backend Integration (Phase 2 & Phase 3)
 * Connects frontend with FastAPI Universal Dataset & Cleaning Engine.
 */

const API_BASE = '/api';

/**
 * Upload a CSV file (File object or Blob with filename) to the backend.
 * Returns the backend readiness report, dataset profile, cleaning report, series quality, and splits.
 */
export async function uploadDatasetToBackend(fileOrBlob, filename = 'dataset.csv') {
  const formData = new FormData();
  if (fileOrBlob instanceof Blob && !(fileOrBlob instanceof File)) {
    formData.append('file', fileOrBlob, filename);
  } else {
    formData.append('file', fileOrBlob);
  }

  let uploadRes;
  try {
    uploadRes = await fetch(`${API_BASE}/data/upload`, {
      method: 'POST',
      body: formData,
    });
  } catch {
    // If proxy failed, attempt direct backend URL
    try {
      uploadRes = await fetch(`http://localhost:8000/api/data/upload`, {
        method: 'POST',
        body: formData,
      });
    } catch {
      throw new Error(
        'Backend Service Unavailable: Could not connect to ForecastIQ backend at http://localhost:8000. ' +
        'Please ensure the backend server is running.'
      );
    }
  }

  if (!uploadRes.ok) {
    const errorData = await uploadRes.json().catch(() => ({ detail: uploadRes.statusText }));
    throw new Error(errorData.detail || `Upload failed with HTTP ${uploadRes.status}`);
  }

  const uploadData = await uploadRes.json();
  const datasetId = uploadData.dataset_id;

  const isDirect = uploadRes.url && uploadRes.url.includes(':8000');
  const baseUrl = isDirect ? 'http://localhost:8000/api' : API_BASE;

  // Run initial cleaning first, then fetch dependent reports
  const [readinessRes, previewRes, cleaningRes] = await Promise.all([
    fetch(`${baseUrl}/data/${datasetId}/readiness`),
    fetch(`${baseUrl}/data/${datasetId}/preview`),
    fetch(`${baseUrl}/data/${datasetId}/clean`, { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ additive_aggregation: true }) }).catch(() => null),
  ]);

  const [qualityRes, splitsRes] = await Promise.all([
    fetch(`${baseUrl}/data/${datasetId}/series-quality`).catch(() => null),
    fetch(`${baseUrl}/data/${datasetId}/splits?test_horizon=28&val_horizon=14`).catch(() => null),
  ]);

  if (!readinessRes.ok) {
    throw new Error('Failed to retrieve validation and readiness report from backend.');
  }

  const readinessData = await readinessRes.json();
  let previewData = { headers: [], rows: [] };
  if (previewRes && previewRes.ok) {
    previewData = await previewRes.json();
  }

  const cleaningData = cleaningRes && cleaningRes.ok ? await cleaningRes.json() : null;
  const qualityData = qualityRes && qualityRes.ok ? await qualityRes.json() : null;
  const splitsData = splitsRes && splitsRes.ok ? await splitsRes.json() : null;

  return formatBackendReportToUI(readinessData, previewData, cleaningData, qualityData, splitsData);
}

/**
 * Convert local M5 sample into canonical schema via backend POST /data/m5/convert.
 * Returns the formatted backend dataset report for UI state ingestion.
 */
export async function convertM5SampleInBackend(maxSeries = 3, maxDays = 194) {
  let convRes;
  try {
    convRes = await fetch(`${API_BASE}/data/m5/convert?max_series=${maxSeries}&max_days=${maxDays}`, {
      method: 'POST',
    });
  } catch {
    try {
      convRes = await fetch(`http://localhost:8000/api/data/m5/convert?max_series=${maxSeries}&max_days=${maxDays}`, {
        method: 'POST',
      });
    } catch {
      throw new Error(
        'Backend Service Unavailable: Could not connect to ForecastIQ backend at http://localhost:8000 to convert M5 sample.'
      );
    }
  }

  if (!convRes.ok) {
    const errorData = await convRes.json().catch(() => ({ detail: convRes.statusText }));
    throw new Error(errorData.detail || `M5 conversion failed with HTTP ${convRes.status}`);
  }

  const convData = await convRes.json();
  const datasetId = convData.dataset_id;

  const isDirect = convRes.url && convRes.url.includes(':8000');
  const baseUrl = isDirect ? 'http://localhost:8000/api' : API_BASE;

  const [readinessRes, previewRes, cleaningRes] = await Promise.all([
    fetch(`${baseUrl}/data/${datasetId}/readiness`),
    fetch(`${baseUrl}/data/${datasetId}/preview`),
    fetch(`${baseUrl}/data/${datasetId}/clean`, { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ additive_aggregation: true }) }).catch(() => null),
  ]);

  const [qualityRes, splitsRes] = await Promise.all([
    fetch(`${baseUrl}/data/${datasetId}/series-quality`).catch(() => null),
    fetch(`${baseUrl}/data/${datasetId}/splits?test_horizon=28&val_horizon=14`).catch(() => null),
  ]);

  if (!readinessRes.ok) {
    throw new Error('Failed to retrieve validation and readiness report for converted M5 dataset.');
  }

  const readinessData = await readinessRes.json();
  let previewData = { headers: [], rows: [] };
  if (previewRes && previewRes.ok) {
    previewData = await previewRes.json();
  }

  const cleaningData = cleaningRes && cleaningRes.ok ? await cleaningRes.json() : null;
  const qualityData = qualityRes && qualityRes.ok ? await qualityRes.json() : null;
  const splitsData = splitsRes && splitsRes.ok ? await splitsRes.json() : null;

  return formatBackendReportToUI(readinessData, previewData, cleaningData, qualityData, splitsData);
}

/**
 * Update column mappings in the backend and re-evaluate readiness and cleaning.
 */
export async function remapDatasetInBackend(datasetId, mapping) {
  const payload = {
    date: mapping.date,
    series_id: mapping.series_id || null,
    target: mapping.target,
    composite_series_keys: mapping.composite_series_keys || [],
    candidate_entity_columns: mapping.candidate_entity_columns || [],
    optional: mapping.optional || {}
  };

  let res;
  try {
    res = await fetch(`${API_BASE}/data/${datasetId}/remap`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(payload),
    });
  } catch {
    try {
      res = await fetch(`http://localhost:8000/api/data/${datasetId}/remap`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(payload),
      });
    } catch {
      throw new Error('Backend Service Unavailable: Could not connect to backend server for remapping.');
    }
  }

  if (!res.ok) {
    const errData = await res.json().catch(() => ({ detail: res.statusText }));
    throw new Error(errData.detail || 'Remapping failed on backend.');
  }

  const isDirect = res.url && res.url.includes(':8000');
  const baseUrl = isDirect ? 'http://localhost:8000/api' : API_BASE;

  const [cleaningRes, qualityRes, splitsRes] = await Promise.all([
    fetch(`${baseUrl}/data/${datasetId}/clean`, { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ additive_aggregation: true }) }).catch(() => null),
    fetch(`${baseUrl}/data/${datasetId}/series-quality`).catch(() => null),
    fetch(`${baseUrl}/data/${datasetId}/splits?test_horizon=28&val_horizon=14`).catch(() => null),
  ]);

  const readinessData = await res.json();
  const cleaningData = cleaningRes && cleaningRes.ok ? await cleaningRes.json() : null;
  const qualityData = qualityRes && qualityRes.ok ? await qualityRes.json() : null;
  const splitsData = splitsRes && splitsRes.ok ? await splitsRes.json() : null;

  return formatBackendReportToUI(readinessData, null, cleaningData, qualityData, splitsData);
}

/**
 * Retrieve and reconstruct full dataset state and audit reports from backend by dataset ID.
 * Used for application restoration after browser refresh.
 */
export async function restoreDatasetFromBackend(datasetId) {
  let readinessRes;
  let baseUrl = API_BASE;
  try {
    readinessRes = await fetch(`${API_BASE}/data/${datasetId}/readiness`);
    baseUrl = API_BASE;
  } catch {
    // Vite proxy might not be ready or direct call needed
    try {
      baseUrl = 'http://localhost:8000/api';
      readinessRes = await fetch(`http://localhost:8000/api/data/${datasetId}/readiness`);
    } catch {
      throw new Error('Backend Service Unavailable: Could not connect to backend server.');
    }
  }

  if (readinessRes.status === 404) {
    throw new Error(`Dataset '${datasetId}' not found on backend.`);
  }

  if (!readinessRes.ok) {
    const errData = await readinessRes.json().catch(() => ({ detail: readinessRes.statusText }));
    throw new Error(errData.detail || `Dataset restoration failed with HTTP ${readinessRes.status}`);
  }

  const readinessData = await readinessRes.json();

  const [previewRes, cleaningRes] = await Promise.all([
    fetch(`${baseUrl}/data/${datasetId}/preview`).catch(() => null),
    fetch(`${baseUrl}/data/${datasetId}/clean`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ additive_aggregation: true }),
    }).catch(() => null),
  ]);

  const [qualityRes, splitsRes] = await Promise.all([
    fetch(`${baseUrl}/data/${datasetId}/series-quality`).catch(() => null),
    fetch(`${baseUrl}/data/${datasetId}/splits?test_horizon=28&val_horizon=14`).catch(() => null),
  ]);

  let previewData = { headers: [], rows: [] };
  if (previewRes && previewRes.ok) {
    previewData = await previewRes.json();
  }

  const cleaningData = cleaningRes && cleaningRes.ok ? await cleaningRes.json() : null;
  const qualityData = qualityRes && qualityRes.ok ? await qualityRes.json() : null;
  const splitsData = splitsRes && splitsRes.ok ? await splitsRes.json() : null;

  return formatBackendReportToUI(readinessData, previewData, cleaningData, qualityData, splitsData);
}

/**
 * Trigger cleaning with user-selected options
 */
export async function cleanDatasetInBackend(datasetId, options = { additive_aggregation: true, target_type: 'additive' }) {
  const res = await fetch(`${API_BASE}/data/${datasetId}/clean`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(options),
  });
  if (!res.ok) {
    throw new Error('Failed to clean dataset in backend.');
  }
  return await res.json();
}

/**
 * Format backend ReadinessReport and Phase 3 data into the UI state expected by UploadDatasetPage.
 */
function formatBackendReportToUI(report, previewData, cleaningData, qualityData, splitsData) {
  const prof = report.profile;
  const mapping = report.column_mapping;
  const optionalList = Object.entries(mapping.optional || {}).map(([key, colName]) => ({
    name: colName,
    role: key.replace('feature_', '').replace('_', ' ').toUpperCase()
  }));

  // Pipeline Status mapping
  const pipelineStatus = cleaningData?.pipeline_status || 
    (report.status === 'READY' ? 'READY FOR MODEL TRAINING' : 'NEEDS ATTENTION');

  return {
    dataset_id: report.dataset_id,
    filename: report.filename,
    pipelineStatus: pipelineStatus,
    profile: {
      filename: report.filename,
      rowsCount: prof.rows_count,
      columnsCount: prof.columns_count,
      headers: prof.column_names,
      dateCol: mapping.date,
      seriesCol: mapping.series_id,
      targetCol: mapping.target,
      detectedFrequency: prof.detected_frequency,
      uniqueSeriesCount: prof.unique_series_count,
      dateRange: {
        start: prof.date_range.start_date || 'N/A',
        end: prof.date_range.end_date || 'N/A',
        spanDays: prof.date_range.total_days
      }
    },
    mapping: {
      date: mapping.date,
      series_id: mapping.series_id,
      target: mapping.target,
      composite_series_keys: mapping.composite_series_keys || [],
      candidate_entity_columns: mapping.candidate_entity_columns || [],
      optional: optionalList
    },
    quality: {
      overallStatus: pipelineStatus,
      statusIssues: report.errors || [],
      missingValuesCount: prof.missing_values_total,
      missingPct: prof.missing_values_pct.toFixed(2),
      duplicateRowsCount: prof.duplicate_rows_count,
      conflictingPairsCount: prof.conflicting_records_count,
      invalidDatesCount: (report.errors || []).filter(e => e.toLowerCase().includes('unparseable') || e.toLowerCase().includes('date')).length,
      invalidTargetCount: (report.errors || []).filter(e => e.toLowerCase().includes('non-numeric')).length,
      negativeTargetCount: prof.target_statistics.negative_count,
      featureWarnings: report.warnings || [],
      leakageWarnings: (report.feature_classifications || [])
        .filter(f => f.classification === 'POTENTIAL_LEAKAGE')
        .map(f => `Column "${f.name}": ${f.reason}`)
    },
    cleaning: cleaningData || {
      original_rows: prof.rows_count,
      cleaned_rows: prof.rows_count,
      exact_duplicates_removed: prof.duplicate_rows_count,
      conflicts_detected: prof.conflicting_records_count,
      conflicts_resolved: prof.conflicting_records_count,
      unresolved_conflicts: 0,
      aggregation_rule: 'SUM',
      missing_targets_found: 0,
      missing_targets_handled: 'NONE',
      zero_targets_preserved: prof.target_statistics.zero_count,
      negative_targets_flagged: prof.target_statistics.negative_count,
      negative_series_affected: [],
      optional_imputations_count: 0,
      gaps_detected_count: 0,
      outliers_contextual_count: 0,
      outliers_abnormal_count: 0,
      pipeline_status: pipelineStatus,
      summary_notes: [],
      raw_row_count: prof.rows_count,
      exact_duplicate_rows_removed: prof.duplicate_rows_count,
      invalid_date_rows_excluded: 0,
      conflicting_observation_groups_resolved: 0,
      missing_target_rows_excluded_or_imputed: 0,
      cleaned_row_count: prof.rows_count,
      eligible_for_training_row_count: prof.rows_count,
    },
    seriesQuality: qualityData || null,
    splits: splitsData || null,
    readiness: {
      checklist: report.readiness_checklist || [],
      horizons: report.supported_horizons || {},
      models: report.model_compatibility || []
    },
    featureClassifications: report.feature_classifications || [],
    seriesSummary: report.series_summary || null,
    previewRows: previewData?.rows || []
  };
}

/**
 * Generate real forecast from backend using ARIMA, SARIMA, or Prophet.
 */
export async function generateForecastInBackend(params) {
  const { dataset_id, series_id, model, horizon } = params;

  let url;
  if (model === 'arima') {
    url = `${API_BASE}/forecast/arima?dataset_id=${encodeURIComponent(dataset_id)}&series_id=${encodeURIComponent(series_id)}&horizon=${horizon}&p=1&d=1&q=1`;
  } else if (model === 'sarima') {
    url = `${API_BASE}/forecast/sarima?dataset_id=${encodeURIComponent(dataset_id)}&series_id=${encodeURIComponent(series_id)}&horizon=${horizon}&p=1&d=1&q=1&seasonal_period=7`;
  } else if (model === 'prophet') {
    url = `${API_BASE}/forecast/prophet?dataset_id=${encodeURIComponent(dataset_id)}&series_id=${encodeURIComponent(series_id)}&horizon=${horizon}&weekly_seasonality=true`;
  } else if (model === 'lightgbm' || model === 'lgbm') {
    url = `${API_BASE}/forecast/lightgbm?dataset_id=${encodeURIComponent(dataset_id)}&series_id=${encodeURIComponent(series_id)}&horizon=${horizon}&n_estimators=100&learning_rate=0.05&num_leaves=31`;
  } else if (model === 'deepar') {
    url = `${API_BASE}/forecast/deepar?dataset_id=${encodeURIComponent(dataset_id)}&series_id=${encodeURIComponent(series_id)}&horizon=${horizon}&epochs=15&batch_size=16&hidden_dim=20&num_samples=100`;
  } else if (model === 'tft' || model === 'temporal_fusion_transformer') {
    url = `${API_BASE}/forecast/tft?dataset_id=${encodeURIComponent(dataset_id)}&series_id=${encodeURIComponent(series_id)}&horizon=${horizon}&epochs=15&batch_size=16&hidden_size=16&attention_heads=2`;
  } else {
    // Fallback to unified
    url = `${API_BASE}/forecast/generate`;
    const res = await fetch(url, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        dataset_id,
        series_id,
        model,
        horizon
      })
    });
    if (!res.ok) {
      const err = await res.json().catch(() => ({ detail: res.statusText }));
      throw new Error(err.detail || 'Forecasting failed on backend.');
    }
    return await res.json();
  }

  let res;
  try {
    res = await fetch(url, { method: 'POST' });
  } catch {
    // Try direct port 8000 fallback
    try {
      res = await fetch(`http://localhost:8000${url.replace('/api', '/api')}`, { method: 'POST' });
    } catch {
      throw new Error('Backend forecasting service unavailable at http://localhost:8000.');
    }
  }

  if (!res.ok) {
    const err = await res.json().catch(() => ({ detail: res.statusText }));
    throw new Error(err.detail || `Forecast generation failed with HTTP ${res.status}`);
  }

  return await res.json();
}

/**
 * Execute chronological walk-forward rolling-origin backtest in the backend.
 */
export async function runBacktestInBackend(datasetId, options = {}, signal = null) {
  const fetchOpts = signal ? { signal } : {};
  const payload = {
    dataset_id: datasetId,
    series_ids: options.series_ids || null,
    store_id: options.store_id || null,
    category: options.category || null,
    item_id: options.item_id || null,
    models: options.models || null,
    horizons: options.horizons || [7, 28, 90],
    n_folds: options.n_folds || 2,
  };

  let res;
  try {
    res = await fetch(`${API_BASE}/evaluation/backtest`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(payload),
      ...fetchOpts,
    });
  } catch {
    try {
      res = await fetch(`http://localhost:8000/api/evaluation/backtest`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(payload),
        ...fetchOpts,
      });
    } catch {
      throw new Error('Backend evaluation service unavailable at http://localhost:8000.');
    }
  }

  if (!res.ok) {
    const err = await res.json().catch(() => ({ detail: res.statusText }));
    throw new Error(err.detail || `Backtesting failed with HTTP ${res.status}`);
  }

  return await res.json();
}

/**
 * Fetch cached evaluation results for a dataset.
 */
export async function getEvaluationFromBackend(datasetId) {
  let res;
  try {
    res = await fetch(`${API_BASE}/evaluation/${datasetId}`);
  } catch {
    try {
      res = await fetch(`http://localhost:8000/api/evaluation/${datasetId}`);
    } catch {
      return null;
    }
  }

  if (!res.ok) {
    return null;
  }

  return await res.json();
}

/**
 * Fetch Model x Horizon comparison matrices for a dataset.
 */
export async function getEvaluationComparisonFromBackend(datasetId, options = {}, signal = null) {
  const params = [];
  if (options.store_id) params.push(`store_id=${encodeURIComponent(options.store_id)}`);
  if (options.category) params.push(`category=${encodeURIComponent(options.category)}`);
  if (options.item_id) params.push(`item_id=${encodeURIComponent(options.item_id)}`);
  if (options.series_id) params.push(`series_id=${encodeURIComponent(options.series_id)}`);
  if (options.horizon) params.push(`horizon=${encodeURIComponent(options.horizon)}`);
  const qs = params.length > 0 ? `?${params.join('&')}` : '';

  let res;
  try {
    res = await fetch(`${API_BASE}/evaluation/${datasetId}/comparison${qs}`, { signal });
  } catch (err) {
    if (err.name === 'AbortError') throw err;
    try {
      res = await fetch(`http://localhost:8000/api/evaluation/${datasetId}/comparison${qs}`, { signal });
    } catch (fallbackErr) {
      if (fallbackErr.name === 'AbortError') throw fallbackErr;
      return null;
    }
  }

  if (!res.ok) {
    return null;
  }

  return await res.json();
}

/**
 * Fetch empirically best model from backtesting.
 */
export async function getBestModelFromBackend(datasetId, seriesId = null, horizon = null) {
  let url = `${API_BASE}/evaluation/${datasetId}/best-model`;
  const params = [];
  if (seriesId) params.push(`series_id=${encodeURIComponent(seriesId)}`);
  if (horizon) params.push(`horizon=${horizon}`);
  if (params.length > 0) url += `?${params.join('&')}`;

  let res;
  try {
    res = await fetch(url);
  } catch {
    try {
      res = await fetch(`http://localhost:8000${url}`);
    } catch {
      return null;
    }
  }

  if (!res.ok) {
    return null;
  }

  return await res.json();
}

/**
 * Fetch insights from backend.
 */
export async function getInsightsFromBackend(datasetId, seriesId = null, options = {}, signal = null) {
  let url = seriesId 
    ? `${API_BASE}/insights/${datasetId}/series/${encodeURIComponent(seriesId)}` 
    : `${API_BASE}/insights/${datasetId}`;

  const params = [];
  if (options.store_id) params.push(`store_id=${encodeURIComponent(options.store_id)}`);
  if (options.category) params.push(`category=${encodeURIComponent(options.category)}`);
  if (options.item_id) params.push(`item_id=${encodeURIComponent(options.item_id)}`);
  if (options.model) params.push(`model=${encodeURIComponent(options.model)}`);
  if (options.horizon) params.push(`horizon=${options.horizon}`);
  if (params.length > 0) url += `?${params.join('&')}`;

  let res;
  try {
    res = await fetch(url, { signal });
  } catch (err) {
    if (err.name === 'AbortError') throw err;
    try {
      res = await fetch(`http://localhost:8000${url}`, { signal });
    } catch (fallbackErr) {
      if (fallbackErr.name === 'AbortError') throw fallbackErr;
      return null;
    }
  }

  if (!res.ok) {
    return null;
  }

  return await res.json();
}

/**
 * Generate fresh insights in backend for series/model/horizon.
 */
export async function generateInsightsInBackend(datasetId, seriesId, options = {}, signal = null) {
  const fetchOpts = signal ? { signal } : {};
  const payload = {
    dataset_id: datasetId,
    series_id: seriesId || null,
    store_id: options.store_id || null,
    category: options.category || null,
    item_id: options.item_id || null,
    model: options.model || 'automatic',
    horizon: options.horizon || 28,
  };

  let res;
  try {
    res = await fetch(`${API_BASE}/insights/generate`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(payload),
      ...fetchOpts,
    });
  } catch {
    try {
      res = await fetch(`http://localhost:8000/api/insights/generate`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(payload),
        ...fetchOpts,
      });
    } catch {
      throw new Error('Backend insights service unavailable at http://localhost:8000.');
    }
  }

  if (!res.ok) {
    const err = await res.json().catch(() => ({ detail: res.statusText }));
    throw new Error(err.detail || `Insight generation failed with HTTP ${res.status}`);
  }

  return await res.json();
}

export async function getMonitoringFromBackend(datasetId, options = {}, signal = null) {
  const params = [];
  if (options.series_id) params.push(`series_id=${encodeURIComponent(options.series_id)}`);
  if (options.store_id) params.push(`store_id=${encodeURIComponent(options.store_id)}`);
  if (options.category) params.push(`category=${encodeURIComponent(options.category)}`);
  if (options.item_id) params.push(`item_id=${encodeURIComponent(options.item_id)}`);
  if (options.model) params.push(`model=${encodeURIComponent(options.model)}`);
  if (options.horizon) params.push(`horizon=${encodeURIComponent(options.horizon)}`);

  const qs = params.length > 0 ? `?${params.join('&')}` : '';

  let res;
  try {
    res = await fetch(`${API_BASE}/monitoring/${datasetId}${qs}`, { signal });
  } catch (err) {
    if (err.name === 'AbortError') throw err;
    try {
      res = await fetch(`http://localhost:8000/api/monitoring/${datasetId}${qs}`, { signal });
    } catch (innerErr) {
      if (innerErr.name === 'AbortError') throw innerErr;
      return null;
    }
  }

  if (!res.ok) {
    return null;
  }

  return await res.json();
}

/**
 * Fetch comprehensive Data Explorer analytics calculated from the COMPLETE active dataset.
 */
export async function getExplorerDataFromBackend(datasetId, options = {}, signal = null) {
  const params = [];
  if (options.store_id) params.push(`store_id=${encodeURIComponent(options.store_id)}`);
  if (options.category) params.push(`category=${encodeURIComponent(options.category)}`);
  if (options.item_id) params.push(`item_id=${encodeURIComponent(options.item_id)}`);
  if (options.series_id) params.push(`series_id=${encodeURIComponent(options.series_id)}`);
  if (options.date_range) params.push(`date_range=${encodeURIComponent(options.date_range)}`);

  const qs = params.length > 0 ? `?${params.join('&')}` : '';
  const url = `${API_BASE}/data/${datasetId}/explorer${qs}`;
  const fallbackUrl = `http://localhost:8000/api/data/${datasetId}/explorer${qs}`;

  let res;
  try {
    res = await fetch(url, { signal });
  } catch (err) {
    if (err.name === 'AbortError') throw err;
    try {
      res = await fetch(fallbackUrl, { signal });
    } catch (fallbackErr) {
      if (fallbackErr.name === 'AbortError') throw fallbackErr;
      return null;
    }
  }

  if (!res || !res.ok) {
    return null;
  }

  return await res.json();
}

// ---------------------------------------------------------------------------
// Authentication & Session Management APIs
// ---------------------------------------------------------------------------

/**
 * Register a new user in the backend MongoDB repository.
 */
export async function registerUserInBackend(fullName, email, password) {
  const payload = {
    full_name: fullName.trim(),
    email: email.trim().toLowerCase(),
    password: password
  };

  let res;
  try {
    res = await fetch(`${API_BASE}/auth/register`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      credentials: 'include',
      body: JSON.stringify(payload)
    });
  } catch {
    try {
      res = await fetch(`http://localhost:8000/api/auth/register`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        credentials: 'include',
        body: JSON.stringify(payload)
      });
    } catch {
      throw new Error('Backend Service Unavailable: Could not reach authentication server.');
    }
  }

  const data = await res.json().catch(() => ({}));
  if (!res.ok) {
    throw new Error(data.detail || `Registration failed with HTTP ${res.status}`);
  }

  return data;
}

/**
 * Login with email and password, establishing an authenticated session.
 */
export async function loginUserInBackend(email, password) {
  const payload = {
    email: email.trim().toLowerCase(),
    password: password
  };

  let res;
  try {
    res = await fetch(`${API_BASE}/auth/login`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      credentials: 'include',
      body: JSON.stringify(payload)
    });
  } catch {
    try {
      res = await fetch(`http://localhost:8000/api/auth/login`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        credentials: 'include',
        body: JSON.stringify(payload)
      });
    } catch {
      throw new Error('Backend Service Unavailable: Could not reach authentication server.');
    }
  }

  const data = await res.json().catch(() => ({}));
  if (!res.ok) {
    throw new Error(data.detail || `Login failed with HTTP ${res.status}`);
  }

  return data;
}

/**
 * Retrieve the current authenticated user's profile using the session cookie.
 */
export async function getCurrentUserFromBackend() {
  let res;
  try {
    res = await fetch(`${API_BASE}/auth/me`, {
      method: 'GET',
      credentials: 'include'
    });
  } catch {
    try {
      res = await fetch(`http://localhost:8000/api/auth/me`, {
        method: 'GET',
        credentials: 'include'
      });
    } catch {
      return null;
    }
  }

  if (!res || !res.ok) {
    return null;
  }

  return await res.json();
}

/**
 * Invalidate the active session on the backend and clear session cookies.
 */
export async function logoutUserInBackend() {
  let res;
  try {
    res = await fetch(`${API_BASE}/auth/logout`, {
      method: 'POST',
      credentials: 'include'
    });
  } catch {
    try {
      res = await fetch(`http://localhost:8000/api/auth/logout`, {
        method: 'POST',
        credentials: 'include'
      });
    } catch {
      return { success: true };
    }
  }

  if (!res || !res.ok) {
    return { success: true };
  }

  return await res.json();
}

