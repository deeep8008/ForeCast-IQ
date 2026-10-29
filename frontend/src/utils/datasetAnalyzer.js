/**
 * Universal Dataset Analyzer for ForecastIQ
 * Analyzes CSV datasets for Multi-Horizon Time-Series Forecasting.
 * Mandatory Columns: date, series_id, target
 * Optional Columns: store_id, item_id, category, company, region, state,
 *                   price, promotion, holiday, weather, customer_segment, etc.
 */

// Simple robust CSV parser for browser/client
export function parseCSV(csvText) {
  if (!csvText || typeof csvText !== 'string') {
    throw new Error('CSV content is empty or invalid.');
  }

  const lines = csvText.split(/\r?\n/).filter(line => line.trim().length > 0);
  if (lines.length < 2) {
    throw new Error('CSV must contain at least a header row and one data row.');
  }

  // Parse header
  const headers = parseCSVLine(lines[0]);
  const rows = [];

  for (let i = 1; i < lines.length; i++) {
    const values = parseCSVLine(lines[i]);
    if (values.length === headers.length) {
      const row = {};
      headers.forEach((h, idx) => {
        row[h.trim()] = values[idx];
      });
      rows.push(row);
    }
  }

  return { headers: headers.map(h => h.trim()), rows };
}

function parseCSVLine(text) {
  const result = [];
  let cur = '';
  let inQuotes = false;

  for (let i = 0; i < text.length; i++) {
    const c = text[i];
    if (c === '"') {
      if (inQuotes && text[i + 1] === '"') {
        cur += '"';
        i++;
      } else {
        inQuotes = !inQuotes;
      }
    } else if (c === ',' && !inQuotes) {
      result.push(cur.trim());
      cur = '';
    } else {
      cur += c;
    }
  }
  result.push(cur.trim());
  return result;
}

// Column detection rules
export function detectColumnMappings(headers) {
  const lowerMap = {};
  headers.forEach(h => {
    lowerMap[h.toLowerCase()] = h;
  });

  const findCol = (candidates) => {
    for (const cand of candidates) {
      if (lowerMap[cand.toLowerCase()]) {
        return lowerMap[cand.toLowerCase()];
      }
    }
    return '';
  };

  const dateCol = findCol(['date', 'datetime', 'timestamp', 'ds', 'time', 'd']);
  const seriesCol = findCol(['series_id', 'item_id', 'id', 'series', 'store_item', 'unique_id', 'ts_id']);
  const targetCol = findCol(['target', 'sales', 'demand', 'units', 'y', 'quantity', 'val', 'value']);

  // Detect optional columns
  const optionalDetected = [];
  headers.forEach(h => {
    if (h === dateCol || h === seriesCol || h === targetCol) return;
    const lower = h.toLowerCase();
    let role = 'Other Feature';

    if (lower.includes('store') || lower.includes('branch') || lower.includes('warehouse')) {
      role = 'Store / Location';
    } else if (lower.includes('item') || lower.includes('product') || lower.includes('sku')) {
      role = 'Item / Product';
    } else if (lower.includes('category') || lower.includes('dept') || lower.includes('cat')) {
      role = 'Category Hierarchy';
    } else if (lower.includes('company') || lower.includes('org') || lower.includes('enterprise')) {
      role = 'Company / Enterprise';
    } else if (lower.includes('region') || lower.includes('district') || lower.includes('zone')) {
      role = 'Geographic Region';
    } else if (lower.includes('state') || lower.includes('province')) {
      role = 'State / Territory';
    } else if (lower.includes('price') || lower.includes('cost') || lower.includes('revenue')) {
      role = 'Selling Price / Economic';
    } else if (lower.includes('promo') || lower.includes('discount') || lower.includes('deal')) {
      role = 'Promotion / Marketing';
    } else if (lower.includes('holiday') || lower.includes('event')) {
      role = 'Calendar / Holiday Event';
    } else if (lower.includes('weather') || lower.includes('temp') || lower.includes('rain')) {
      role = 'Weather Covariate';
    } else if (lower.includes('segment') || lower.includes('customer') || lower.includes('channel')) {
      role = 'Customer Segment';
    }

    optionalDetected.push({ name: h, role });
  });

  return {
    date: dateCol,
    series_id: seriesCol,
    target: targetCol,
    optional: optionalDetected
  };
}

// Comprehensive Dataset Analysis Engine
export function analyzeDataset(filename, parsedData, customMapping = null) {
  const { headers, rows } = parsedData;
  const initialMapping = customMapping || detectColumnMappings(headers);

  const dateCol = initialMapping.date;
  const seriesCol = initialMapping.series_id;
  const targetCol = initialMapping.target;

  // Validation: Missing mandatory columns
  const missingMandatory = [];
  if (!dateCol) missingMandatory.push('date');
  if (!seriesCol) missingMandatory.push('series_id');
  if (!targetCol) missingMandatory.push('target');

  // Basic counters
  let missingValuesCount = 0;
  const colMissing = {};
  headers.forEach(h => { colMissing[h] = 0; });

  let invalidDatesCount = 0;
  let invalidTargetCount = 0;
  let negativeTargetCount = 0;
  const uniqueSeriesSet = new Set();
  const validDates = [];
  const seriesDatePairs = new Set();
  let conflictingPairsCount = 0;
  let duplicateRowsCount = 0;
  const rowHashTracker = new Set();

  rows.forEach((row) => {
    // Check duplicate rows
    const rowHash = JSON.stringify(row);
    if (rowHashTracker.has(rowHash)) {
      duplicateRowsCount++;
    } else {
      rowHashTracker.add(rowHash);
    }

    // Check missing values
    headers.forEach(h => {
      const val = row[h];
      if (val === undefined || val === null || val === '' || val === 'NA' || val === 'NaN') {
        missingValuesCount++;
        colMissing[h]++;
      }
    });

    // Check Series ID
    if (seriesCol && row[seriesCol]) {
      uniqueSeriesSet.add(row[seriesCol]);
    }

    // Check Date
    if (dateCol) {
      const dStr = row[dateCol];
      const parsedDate = new Date(dStr);
      if (isNaN(parsedDate.getTime())) {
        invalidDatesCount++;
      } else {
        validDates.push(parsedDate);
        if (seriesCol && row[seriesCol]) {
          const pairKey = `${row[seriesCol]}__${parsedDate.toISOString().split('T')[0]}`;
          if (seriesDatePairs.has(pairKey)) {
            conflictingPairsCount++;
          } else {
            seriesDatePairs.add(pairKey);
          }
        }
      }
    }

    // Check Target
    if (targetCol) {
      const tVal = parseFloat(row[targetCol]);
      if (isNaN(tVal)) {
        invalidTargetCount++;
      } else if (tVal < 0) {
        negativeTargetCount++;
      }
    }
  });

  // Calculate Date Range & Frequency
  let minDateStr = 'N/A';
  let maxDateStr = 'N/A';
  let spanDays = 0;
  let detectedFrequency = 'Daily (D)';

  if (validDates.length > 0) {
    validDates.sort((a, b) => a.getTime() - b.getTime());
    minDateStr = validDates[0].toISOString().split('T')[0];
    maxDateStr = validDates[validDates.length - 1].toISOString().split('T')[0];
    spanDays = Math.round((validDates[validDates.length - 1] - validDates[0]) / (1000 * 60 * 60 * 24));

    // Frequency heuristic
    if (spanDays > 0 && validDates.length > 5) {
      const avgIntervalDays = spanDays / Math.max(1, validDates.length / Math.max(1, uniqueSeriesSet.size));
      if (avgIntervalDays <= 1.2) {
        detectedFrequency = 'Daily (D)';
      } else if (avgIntervalDays > 5 && avgIntervalDays <= 8) {
        detectedFrequency = 'Weekly (W)';
      } else if (avgIntervalDays > 25 && avgIntervalDays <= 32) {
        detectedFrequency = 'Monthly (M)';
      } else {
        detectedFrequency = 'Irregular / Custom Interval';
      }
    }
  }

  // Feature Warnings & Potential Data Leakage
  const featureWarnings = [];
  const leakageWarnings = [];

  headers.forEach(h => {
    const lower = h.toLowerCase();
    if (lower.includes('future') || lower.includes('actual_future') || lower.includes('next_day_demand')) {
      leakageWarnings.push(`Column "${h}" may contain future information (data leakage risk). Verify before training.`);
    }
    if (lower.includes('prediction') || lower.includes('forecast')) {
      leakageWarnings.push(`Column "${h}" appears to be a pre-existing forecast. Confirm it is an input feature.`);
    }

    const missingRatio = (colMissing[h] / Math.max(1, rows.length)) * 100;
    if (missingRatio > 25) {
      featureWarnings.push(`Column "${h}" has ${missingRatio.toFixed(1)}% missing entries.`);
    }
  });

  if (negativeTargetCount > 0) {
    featureWarnings.push(`${negativeTargetCount} negative target value(s) detected. If these represent product returns, verify if model should predict net demand.`);
  }

  if (conflictingPairsCount > 0) {
    featureWarnings.push(`${conflictingPairsCount} duplicate series_id + date record(s) detected. Aggregation will be required.`);
  }

  // Determine Overall Status
  let overallStatus = 'FORECAST READY';
  const statusIssues = [];

  if (missingMandatory.length > 0) {
    overallStatus = 'NEEDS ATTENTION';
    statusIssues.push(`Missing mandatory column(s): ${missingMandatory.join(', ')}.`);
  }
  if (invalidDatesCount > 0) {
    overallStatus = 'NEEDS ATTENTION';
    statusIssues.push(`${invalidDatesCount} unparseable date value(s).`);
  }
  if (invalidTargetCount > 0) {
    overallStatus = 'NEEDS ATTENTION';
    statusIssues.push(`${invalidTargetCount} non-numeric target value(s).`);
  }
  if (conflictingPairsCount > 5) {
    overallStatus = 'NEEDS ATTENTION';
    statusIssues.push(`Multiple conflicting series_id + date entries found.`);
  }

  // Forecast Readiness Checklist
  const readinessChecklist = [
    {
      title: 'Mandatory Columns Mapped',
      passed: missingMandatory.length === 0,
      detail: missingMandatory.length === 0 
        ? `Mapped: date="${dateCol}", series_id="${seriesCol}", target="${targetCol}"` 
        : `Missing: ${missingMandatory.join(', ')}`
    },
    {
      title: 'Valid Chronological Range',
      passed: validDates.length > 0 && invalidDatesCount === 0,
      detail: validDates.length > 0 
        ? `${minDateStr} to ${maxDateStr} (${spanDays} calendar days, ${detectedFrequency})` 
        : 'No valid dates detected'
    },
    {
      title: 'Target Column Numerical Integrity',
      passed: targetCol !== '' && invalidTargetCount === 0,
      detail: targetCol 
        ? `${rows.length - invalidTargetCount} valid numeric values (${negativeTargetCount} negative values)` 
        : 'Target column unmapped'
    },
    {
      title: 'Series Identification',
      passed: uniqueSeriesSet.size > 0,
      detail: `${uniqueSeriesSet.size} unique time-series detected`
    },
    {
      title: 'Uniqueness of Series + Date Timestamp',
      passed: conflictingPairsCount === 0,
      detail: conflictingPairsCount === 0 
        ? 'No duplicate timestamps within any series' 
        : `${conflictingPairsCount} duplicate timestamp conflict(s)`
    }
  ];

  // Horizon Feasibility Assessment
  const horizonReadiness = {
    h7: {
      days: 7,
      label: '7 Days (Short-term)',
      status: spanDays >= 28 ? 'Supported' : 'Limited Data',
      note: spanDays >= 28 ? 'Sufficient historical observations for lag-1 to lag-7 feature construction.' : 'Minimum 28 days of history recommended.'
    },
    h28: {
      days: 28,
      label: '28 Days (Medium-term)',
      status: spanDays >= 90 ? 'Supported' : spanDays >= 45 ? 'Borderline' : 'Insufficient',
      note: spanDays >= 90 ? 'Full monthly cycle coverage with rolling 28-day window support.' : 'At least 90 days recommended for monthly seasonality.'
    },
    h90: {
      days: 90,
      label: '90 Days (Long-term)',
      status: spanDays >= 180 ? 'Supported' : 'Limited',
      note: spanDays >= 180 ? 'Quarterly planning supported across deep multi-horizon models.' : 'Requires at least 180+ days for reliable 90-day multi-horizon training.'
    }
  };

  // Model Compatibility
  const modelCompatibility = [
    {
      model: 'ARIMA',
      type: 'Statistical Baseline',
      ready: uniqueSeriesSet.size > 0 && spanDays >= 30,
      requirement: 'Requires univariate continuous regular cadence per series.'
    },
    {
      model: 'SARIMA',
      type: 'Seasonal Statistical Baseline',
      ready: uniqueSeriesSet.size > 0 && spanDays >= 60,
      requirement: 'Requires regular seasonality and enough historical periods to fit seasonal autoregression.'
    },
    {
      model: 'Prophet',
      type: 'Additive Seasonality',
      ready: spanDays >= 60,
      requirement: 'Requires date + target with seasonal patterns and optional holiday column.'
    },
    {
      model: 'LightGBM',
      type: 'Tabular Machine Learning',
      ready: spanDays >= 45,
      requirement: 'Engineers lag, rolling, and categorical covariates (store, item, price, etc.).'
    },
    {
      model: 'DeepAR',
      type: 'Deep Learning (RNN)',
      ready: uniqueSeriesSet.size >= 1 && spanDays >= 60,
      requirement: 'Cross-series autoregressive training across related product-store series.'
    },
    {
      model: 'Temporal Fusion Transformer (TFT)',
      type: 'Deep Multi-Horizon Attention',
      ready: spanDays >= 90,
      requirement: 'Leverages static metadata + time-varying covariates for multi-horizon attention.'
    }
  ];

  return {
    filename,
    profile: {
      filename,
      rowsCount: rows.length,
      columnsCount: headers.length,
      headers,
      dateCol,
      seriesCol,
      targetCol,
      detectedFrequency,
      uniqueSeriesCount: uniqueSeriesSet.size,
      dateRange: {
        start: minDateStr,
        end: maxDateStr,
        spanDays
      }
    },
    mapping: {
      date: dateCol,
      series_id: seriesCol,
      target: targetCol,
      optional: initialMapping.optional || []
    },
    quality: {
      overallStatus,
      statusIssues,
      missingValuesCount,
      missingPct: ((missingValuesCount / Math.max(1, rows.length * headers.length)) * 100).toFixed(2),
      duplicateRowsCount,
      conflictingPairsCount,
      invalidDatesCount,
      invalidTargetCount,
      negativeTargetCount,
      featureWarnings,
      leakageWarnings
    },
    readiness: {
      checklist: readinessChecklist,
      horizons: horizonReadiness,
      models: modelCompatibility
    },
    previewRows: rows.slice(0, 5)
  };
}

// Built-in Demo Datasets for instant testing & evaluation
export const DEMO_DATASETS = {
  universalRetail: {
    filename: 'enterprise_retail_branch_sales.csv',
    description: 'Compliant Universal CSV with mandatory columns (date, series_id, target) plus store, category, and price.',
    csv: `date,series_id,target,store_id,item_id,category,price,promotion
2024-01-01,STORE_01_PROD_101,42,STORE_01,PROD_101,Beverages,2.49,0
2024-01-02,STORE_01_PROD_101,38,STORE_01,PROD_101,Beverages,2.49,0
2024-01-03,STORE_01_PROD_101,45,STORE_01,PROD_101,Beverages,2.49,0
2024-01-04,STORE_01_PROD_101,52,STORE_01,PROD_101,Beverages,2.49,0
2024-01-05,STORE_01_PROD_101,68,STORE_01,PROD_101,Beverages,1.99,1
2024-01-06,STORE_01_PROD_101,75,STORE_01,PROD_101,Beverages,1.99,1
2024-01-07,STORE_01_PROD_101,60,STORE_01,PROD_101,Beverages,2.49,0
2024-01-08,STORE_01_PROD_101,41,STORE_01,PROD_101,Beverages,2.49,0
2024-01-09,STORE_01_PROD_101,43,STORE_01,PROD_101,Beverages,2.49,0
2024-01-10,STORE_01_PROD_101,49,STORE_01,PROD_101,Beverages,2.49,0
2024-01-11,STORE_01_PROD_101,53,STORE_01,PROD_101,Beverages,2.49,0
2024-01-12,STORE_01_PROD_101,70,STORE_01,PROD_101,Beverages,1.99,1
2024-01-13,STORE_01_PROD_101,79,STORE_01,PROD_101,Beverages,1.99,1
2024-01-14,STORE_01_PROD_101,58,STORE_01,PROD_101,Beverages,2.49,0
2024-01-15,STORE_01_PROD_101,44,STORE_01,PROD_101,Beverages,2.49,0
2024-01-16,STORE_01_PROD_101,46,STORE_01,PROD_101,Beverages,2.49,0
2024-01-17,STORE_01_PROD_101,50,STORE_01,PROD_101,Beverages,2.49,0
2024-01-18,STORE_01_PROD_101,54,STORE_01,PROD_101,Beverages,2.49,0
2024-01-19,STORE_01_PROD_101,72,STORE_01,PROD_101,Beverages,1.99,1
2024-01-20,STORE_01_PROD_101,84,STORE_01,PROD_101,Beverages,1.99,1
2024-01-21,STORE_01_PROD_101,62,STORE_01,PROD_101,Beverages,2.49,0
2024-01-22,STORE_01_PROD_101,40,STORE_01,PROD_101,Beverages,2.49,0
2024-01-23,STORE_01_PROD_101,42,STORE_01,PROD_101,Beverages,2.49,0
2024-01-24,STORE_01_PROD_101,48,STORE_01,PROD_101,Beverages,2.49,0
2024-01-25,STORE_01_PROD_101,55,STORE_01,PROD_101,Beverages,2.49,0
2024-01-26,STORE_01_PROD_101,76,STORE_01,PROD_101,Beverages,1.99,1
2024-01-27,STORE_01_PROD_101,88,STORE_01,PROD_101,Beverages,1.99,1
2024-01-28,STORE_01_PROD_101,65,STORE_01,PROD_101,Beverages,2.49,0
2024-01-29,STORE_01_PROD_101,47,STORE_01,PROD_101,Beverages,2.49,0
2024-01-30,STORE_01_PROD_101,51,STORE_01,PROD_101,Beverages,2.49,0
2024-01-31,STORE_01_PROD_101,56,STORE_01,PROD_101,Beverages,2.49,0
2024-01-01,STORE_02_PROD_202,18,STORE_02,PROD_202,Packaged,4.99,0
2024-01-02,STORE_02_PROD_202,21,STORE_02,PROD_202,Packaged,4.99,0
2024-01-03,STORE_02_PROD_202,19,STORE_02,PROD_202,Packaged,4.99,0
2024-01-04,STORE_02_PROD_202,24,STORE_02,PROD_202,Packaged,4.99,0
2024-01-05,STORE_02_PROD_202,32,STORE_02,PROD_202,Packaged,4.49,1
2024-01-06,STORE_02_PROD_202,35,STORE_02,PROD_202,Packaged,4.49,1
2024-01-07,STORE_02_PROD_202,28,STORE_02,PROD_202,Packaged,4.99,0
2024-01-08,STORE_02_PROD_202,17,STORE_02,PROD_202,Packaged,4.99,0
2024-01-09,STORE_02_PROD_202,20,STORE_02,PROD_202,Packaged,4.99,0
2024-01-10,STORE_02_PROD_202,22,STORE_02,PROD_202,Packaged,4.99,0`
  },
  needsAttention: {
    filename: 'branch_sales_unverified_audit.csv',
    description: 'Test CSV with quality flags: duplicate timestamps, negative return items, and missing value entries.',
    csv: `date,series_id,target,store_id,price
2024-01-01,BRANCH_NORTH_01,30,NORTH,12.50
2024-01-02,BRANCH_NORTH_01,-5,NORTH,12.50
2024-01-02,BRANCH_NORTH_01,25,NORTH,12.50
2024-01-03,BRANCH_NORTH_01,,NORTH,12.50
2024-01-04,BRANCH_NORTH_01,34,NORTH,
INVALID_DATE,BRANCH_NORTH_01,28,NORTH,12.50
2024-01-06,BRANCH_NORTH_01,40,NORTH,12.50`
  },
  m5Sample: {
    filename: 'm5_universal_format_sample.csv',
    description: 'M5 series converted into standard universal schema: date, series_id, target, state, store_id.',
    csv: `date,series_id,target,state,store_id,category
2016-01-01,FOODS_3_090_CA_1,108,CA,CA_1,FOODS
2016-01-02,FOODS_3_090_CA_1,142,CA,CA_1,FOODS
2016-01-03,FOODS_3_090_CA_1,135,CA,CA_1,FOODS
2016-01-04,FOODS_3_090_CA_1,98,CA,CA_1,FOODS
2016-01-05,FOODS_3_090_CA_1,102,CA,CA_1,FOODS
2016-01-06,FOODS_3_090_CA_1,115,CA,CA_1,FOODS
2016-01-07,FOODS_3_090_CA_1,120,CA,CA_1,FOODS
2016-01-08,FOODS_3_090_CA_1,130,CA,CA_1,FOODS
2016-01-09,FOODS_3_090_CA_1,154,CA,CA_1,FOODS
2016-01-10,FOODS_3_090_CA_1,148,CA,CA_1,FOODS`
  }
};
