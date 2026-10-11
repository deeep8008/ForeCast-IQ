# ForecastIQ — Multi-Horizon Demand Forecasting & Model Evaluation Engine

ForecastIQ is a full-stack demand forecasting platform that automates dataset ingestion, chronological 80/20 holdout backtesting across five candidate machine learning models, dynamic leaderboard ranking using MAPE and RMSE, and full-history retraining for multi-horizon demand projections.

---

## ⚡ Quick Start: Running Locally

Follow these steps to run the **FastAPI backend** and **React frontend** locally.

### Prerequisites

- **Python 3.10+** with pip
- **Node.js 18+** with npm
- **Git**

---

### 1. Clone the Repository

Open a terminal and run:

```bash
git clone https://github.com/deeep8008/ForeCast-IQ.git
cd ForeCast-IQ
```

If you have already downloaded the project as a ZIP file, extract it and open the extracted `ForeCast-IQ` folder in your IDE instead.

### 2. Start the Backend

Open a terminal in the project root directory.

```bash
cd backend
```

Install the Python dependencies:

```bash
python -m pip install -r requirements.txt
```

Start the FastAPI development server:

```bash
python -m uvicorn app.main:app --reload --port 8000
```

The backend will be available at:

- **API:** http://127.0.0.1:8000
- **Interactive API documentation:** http://127.0.0.1:8000/docs

Keep this terminal running.

### 3. Start the Frontend

Open a **second terminal** in the project root directory (`ForeCast-IQ`), not inside the `backend` folder.

Install the Node.js dependencies:

```bash
npm install
```

Start the Vite development server:

```bash
npm run dev
```

Open the local URL printed in your terminal, usually:

**http://localhost:5173/**

Keep this terminal running while using the application.

---

## 🔄 How the Application Works

```text
[Upload CSV / Folder / 1-Click M5]
               |
               v
[Standardize Dataset to Canonical Schema]
               |
               v
[Chronological 80/20 Train-Holdout Split]
               |
               v
[Evaluate Candidate Forecasting Models]
               |
               v
[Rank Models by MAPE and RMSE]
               |
               v
[Select Best-Performing Model]
               |
               v
[Retrain on 100% of Historical Data]
               |
               v
[Generate Future Forecasts and Supply Chain Insights]
               |
               v
[Export Forecasts to CSV]
```

### 1. Dataset Ingestion & Preloading

- **Single CSV or multi-CSV folder:** Upload time-series sales data with automatic CSV validation.
- **M5 benchmark:** Preload the Walmart M5 benchmark dataset, if the required dataset files and backend support are available.
- **Column mapping:** Map the date (`timestamp`), sales (`target`), and product/store identifier (`series_id`) to the canonical schema.

### 2. Chronological Backtesting & Model Evaluation

- **Chronological split:** Uses the first 80% of observations for training and reserves the final 20% for holdout evaluation.
- **Candidate models:** ARIMA, Prophet, LightGBM, DeepAR, and Temporal Fusion Transformer (TFT), subject to the configured backend dependencies and implementation.
- **Evaluation metrics:** Calculates MAPE (Mean Absolute Percentage Error) and RMSE (Root Mean Squared Error) against holdout observations.
- **Dynamic leaderboard:** Ranks models by forecasting error, with lower values indicating better performance.
- **Holdout visualization:** Compares actual values against model predictions.

### 3. Future Forecasting

- **Full-history retraining:** Retrains the selected model using all available historical observations.
- **Multiple forecast horizons:** Supports 7-day, 14-day, 28-day, and 90-day forecasts, where implemented.
- **Uncertainty estimates:** Provides 80% and 95% prediction intervals, where supported by the selected model.
- **Supply chain insights:** Can provide safety stock recommendations, peak-demand estimates, and stockout risk indicators based on available inventory data and configured calculations.
- **CSV export:** Exports future forecasts for further analysis and downstream workflows.

---

## 🛠 Tech Stack

### Frontend
- React 19
- Vite
- Tailwind CSS v4
- Lucide Icons
- Custom SVG time-series charts

### Backend
