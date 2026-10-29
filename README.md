# ForecastIQ — Multi-Horizon Time-Series Forecasting for Enterprise Analytics

ForecastIQ is a dataset-agnostic, production-grade enterprise time-series forecasting, backtesting, and decision-support intelligence platform. Powered by a FastAPI backend and a modern React/Vite/Tailwind frontend, ForecastIQ unifies classical statistical baselines, modern gradient boosted decision trees, and state-of-the-art deep sequence transformers to deliver verifiable multi-horizon demand projections alongside evidence-based operational recommendations.

---

## Key Platform Capabilities

- **Universal Canonical Schema**: Automatically profiles, cleans, and standardizes arbitrary multi-series CSV datasets to the canonical schema (`date`, `series_id`, `target` + optional hierarchy and exogenous covariates).
- **Auditable Data Pipeline**: Detects and handles duplicate records, conflicting observation timestamps, missing targets, unparseable dates, calendar gaps, and contextual vs. abnormal outliers with deterministic audit reports.
- **6 Forecasting Architectures**: Single-series multi-horizon execution across **ARIMA**, **SARIMA**, **Prophet**, **LightGBM**, **DeepAR**, and **Temporal Fusion Transformer (TFT)**.
- **Multi-Horizon Planning**: Purpose-built for **7-Day (Operational)**, **28-Day (Tactical)**, and **90-Day (Strategic)** enterprise horizons.
- **Strict Out-of-Sample Date Alignment**: Future forecast dates are strictly derived from the exact selected series' valid historical cutoff ($T+1$ through $T+H$), eliminating cross-series timestamp skew and data leakage.
- **Authentic Walk-Forward Backtesting**: Chronological rolling-origin evaluation without lookahead bias, generating zero-actual-protected MAPE and RMSE metrics.
- **Empirical Model Selection**: Automated multi-horizon ranking matrix identifying optimal models per horizon and overall without hardcoded heuristics.
- **Evidence-Based Business Insights**: Actionable guidance for inventory replenishment, shift staffing, supplier procurement, and strategic demand buffers derived directly from computed forecast deltas and prediction intervals.
- **Continuous Model Health Monitoring**: Real-time evaluation fold drift tracking (`HEALTHY`, `WATCH`, `ACCURACY DRIFT`) with automated retraining alerts.
- **Dual Persistence Architecture**: High-speed MongoDB storage with gzip CSV compression, coupled with automatic in-memory fallback and browser URL hash/session state restoration.

---

## Architecture Flow

```
Custom Enterprise CSV / M5 Benchmark
                 ↓
     Dataset Profiler & Schema Detection
                 ↓
     Universal Canonical Schema Mapping
       (date, series_id, target + optional)
                 ↓
     Auditable Cleaning & Deduplication Engine
       - Invalid timestamp & missing target exclusion
       - Exact duplicate removal & conflict aggregation
                 ↓
     Chronological Train / Validation / Test Splitting
                 ↓
     Unified Multi-Horizon Forecasting Engine
   (ARIMA, SARIMA, Prophet, LightGBM, DeepAR, TFT)
                 ↓
     Chronological Walk-Forward Backtesting (MAPE + RMSE)
                 ↓
     Empirical Best-Model Matrix & Comparison
                 ↓
     Evidence-Based Business Decision Support
                 ↓
     MongoDB / In-Memory State & Hash Route Restoration
```

---

## Universal Dataset Standard

Every uploaded time-series dataset is validated against the universal canonical schema:

### Mandatory Columns
1. **`date`**: Timestamp / observation date (Daily frequency recommended; ISO-8601 or common date formats).
2. **`series_id`**: Distinct time-series identifier (e.g., store, SKU, warehouse, region, product).
3. **`target`**: Numerical quantity to forecast (e.g., demand, sales, revenue, orders).

### Supported Optional Columns
- **Hierarchy Dimensions**: `store_id`, `item_id`, `category`, `company`, `region`, `state`.
- **Exogenous Covariates**:
  - `price` (historical unit price)
  - `promotion` (binary promotional flag)
  - `holiday` (calendar holiday / event name)
  - `weather`, `temperature`, `customer_segment`, etc.

*Data Quality Rule:* Exogenous features are validated to prevent target leakage. Historical series cutoffs are isolated per series: if a series contains missing target values or invalid dates at the tail, its training cutoff ends at its latest valid observation, and its forecast strictly begins on the subsequent day.

---

## Supported Forecasting Architectures

ForecastIQ supports six distinct models evaluated across **7-Day**, **28-Day**, and **90-Day** planning horizons:

1. **ARIMA** (`statsmodels`): Classical Autoregressive Integrated Moving Average baseline with closed-form 95% confidence bounds.
2. **SARIMA** (`statsmodels`): Seasonal statistical forecasting accounting for weekly recurring seasonality patterns.
3. **Prophet** (`prophet`): Additive trend and seasonal decomposition with Bayesian uncertainty intervals.
4. **LightGBM** (`lightgbm`): High-throughput gradient boosted trees utilizing chronological lag features, rolling statistics, and calendar variables.
5. **DeepAR** (`darts` + `PyTorch`): Probabilistic autoregressive recurrent neural network producing empirical prediction intervals from Monte Carlo simulation.
6. **Temporal Fusion Transformer (TFT)** (`darts` + `PyTorch`): Multi-horizon sequence transformer with multi-head self-attention, interpretable gating mechanisms, and temporal covariate embeddings.

---

## Multi-Horizon Decision Support & Monitoring

- **Planning Window Consistency**: The forecast period ($[T+1, \dots, T+H]$), average demand, peak, trough, and recommendation evidence are computed from the identical forecast series slice.
- **Peak & Trough Containment**: Peaks and troughs are strictly contained within their respective planning windows (7D, 28D, 90D).
- **Advisory Operational Guidance**:
  - **Inventory**: Replenishment recommendations and stockout risk assessments based on baseline volume shifts.
  - **Staffing**: Floor handling and fulfillment labor shift guidance aligned with anticipated peak demand dates.
  - **Procurement**: Advance vendor purchase order timing tied to supplier lead times.
  - **Strategic Demand Planning**: Multi-horizon executive outlook highlighting aggregate run rates.
- **Model Health Monitoring**:
  - Tracks out-of-sample backtest fold error drift against baseline folds.
  - States: `HEALTHY` (error stable), `WATCH` (moderate drift), and `ACCURACY DRIFT` (significant degradation triggering retraining alerts).

---

## Persistence & Route Restoration

ForecastIQ supports resilient persistence across browser reloads, page navigation, and server restarts:
- **MongoDB Persistence**: Cleaned datasets, metadata, model forecasts, backtest summaries, business insights, and monitoring reports are persisted to MongoDB when connected.
- **Compressed Storage**: Dataset CSVs are compressed with gzip and stored in MongoDB to conserve storage and support full reconstruction.
- **Hash Route Synchronization**: Active route (`#/upload`, `#/explorer`, `#/forecast`, `#/comparison`, `#/evaluation`, `#/insights`) and active dataset IDs synchronize with `window.location.hash` and `localStorage`, restoring the full dataset audit and UI state on browser refresh (`Ctrl+R`).
- **In-Memory Fallback**: When MongoDB is offline, an in-memory cache maintains uninterrupted local development.

---

## Project Structure

```
Major Project/
├── backend/
│   ├── app/
│   │   ├── api/            # FastAPI endpoints & route handlers
│   │   ├── data/           # Loader, cleaner, profiler, splits, and explorer
│   │   ├── db/             # MongoDB connection & repository layer
│   │   ├── evaluation/     # Rolling-origin backtesting & metrics
│   │   ├── forecasting/    # Unified multi-model forecast engine
│   │   ├── insights/       # Business insights & model monitoring engines
│   │   └── models/         # ARIMA, SARIMA, Prophet, LightGBM, DeepAR, TFT
│   ├── tests/              # Comprehensive pytest regression test suite (192 tests)
│   ├── requirements.txt    # Python dependencies
│   └── run_audit_integration.py
├── frontend/
│   ├── src/
│   │   ├── components/     # UI components, layout, and navigation
│   │   ├── pages/          # Upload, Explorer, Forecast, Comparison, Eval, Insights
│   │   ├── services/       # Backend API client integration
│   │   └── test/           # Vitest unit & integration test suites (38 tests)
│   ├── package.json        # Frontend scripts and npm dependencies
│   └── vite.config.js
└── README.md
```

---

## Getting Started

### 1. Prerequisites
- **Python**: 3.10 or 3.11
- **Node.js**: 18+ and npm
- **MongoDB** *(Optional)*: 6.0+ (the system falls back to in-memory storage if MongoDB is not running)

### 2. Backend Installation & Startup
```bash
cd backend
python -m venv venv

# Windows (PowerShell):
.\venv\Scripts\Activate.ps1
# Linux / macOS:
source venv/bin/activate

pip install -r requirements.txt
python -m uvicorn app.main:app --host 127.0.0.1 --port 8000 --reload
```
The FastAPI documentation is available at [http://127.0.0.1:8000/docs](http://127.0.0.1:8000/docs).

### 3. Frontend Installation & Startup
```bash
cd frontend
npm install
npm run dev
```
Open [http://localhost:5173](http://localhost:5173) in your browser.

---

## Verification & Test Suites

ForecastIQ maintains comprehensive automated regression coverage across both backend and frontend.

### Backend Pytest Suite (192 Tests)
Run the full backend test suite:
```bash
cd backend
python -m pytest -q
```
*Current Suite Status:* **192 passed**, 0 failed in ~60s.

To run specific modules:
```bash
python -m pytest tests/test_business_insights.py -v     # Business Insights (41 tests)
python -m pytest tests/test_scope_and_consistency.py -v # Scope & consistency
python -m pytest tests/test_dataset_persistence.py -v   # Route & dataset persistence
```

### Frontend Vitest Suite (38 Tests)
Run frontend integration tests:
```bash
cd frontend
npm test
```
*Current Suite Status:* **38 passed across all 6 test files**, 0 failed.

### Frontend Linter & Build Validation
```bash
cd frontend
npm run lint    # 0 errors
npm run build   # Production bundle successfully compiled
```

---

## Verified Capabilities & Edge Cases Covered

- **Distinct Series Cutoffs**: Supports datasets where individual series end on different historical dates; forecast timestamps start on $T_i + 1$ without cross-series date skew.
- **Corrupted & Missing Rows**: Rows with unparseable timestamps or `NaN` targets are excluded from model training without discarding valid dates.
- **Strict Timestamp Counting**: Daily forecasts contain exactly 7, 28, or 90 daily points matching the requested horizon.
- **Zero Lookahead Leakage**: Future target values and evaluation test sets are strictly inaccessible during feature engineering and model training.
- **Scope Isolation**: Switching stores, categories, products, models, or horizons immediately invalidates stale cached results and drops out-of-order asynchronous payloads.

---

## Known Operational Considerations

- **Deep Learning Training Time**: Multi-horizon training of DeepAR and TFT over hundreds of series simultaneously is compute-intensive; GPU acceleration or selective series filtering is recommended for enterprise scale.
- **Uncertainty Bounds**: Uncertainty intervals are reported only when genuine predictive distributions or prediction intervals are produced by the underlying model; non-probabilistic models report uncertainty as `UNKNOWN` rather than fabricating artificial spreads.
