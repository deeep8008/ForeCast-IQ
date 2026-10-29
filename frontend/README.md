# ForecastIQ — Multi-Horizon Time-Series Forecasting Frontend

A modern, human-friendly AI analytics web interface for **Multi-Horizon Time-Series Forecasting for Enterprise Analytics**.

Built using **Vite, React 19, Tailwind CSS v4, Lucide Icons, and custom SVG time-series visualizers**.

---

## 🎨 Visual Identity & Lavender Palette
The interface strictly adheres to the requested palette tokens:
- **`#F5EFFF`** — Background page & subtle container tint (Very light lavender)
- **`#E5D9F2`** — Soft lavender for confidence interval shading, borders, and secondary controls
- **`#CDC1FF`** — Medium lavender for badges, boundary outlines, and active tags
- **`#A294F9`** — Primary purple for primary CTAs, forecast trajectory lines, and active states
- **`#FFFFFF`** — Surface cards with soft rounded corners (`12px–24px`) and thin borders

Status colors are subtle and purposeful:
- 🟢 **Green (`#10B981`)** for healthy validation & dataset loaded status
- 🟡 **Amber (`#F59E0B`)** for strategic quarterly warnings
- 🔴 **Red (`#EF4444`)** for critical stockout / large error alerts

---

## 🧭 Page Architecture & User Journey
1. **Home (`Overview`)**:
   - Multi-horizon Hero ("See what demand looks like next.")
   - 4 Clean KPI cards (7D/28D/90D Horizons, 6 Models, 42,840 Series, MAPE & RMSE)
   - Interactive *Actual vs Forecast* chart with store, product, model, and horizon controls
   - Plain-language *"What changed?"* driver cards (Seasonal pattern, Calendar/SNAP events, Price elasticity)
2. **Data Explorer**:
   - Hierarchical filtering: State → Store → Category → Product → Date Window
   - Section A: Historical Sales Trend with 7-Day Rolling Moving Average toggle
   - Section B: Sales by Store comparison
   - Section C: Sales by Category distribution
   - Section D: Shelf price movement and discount spikes
   - Section E: Calendar & External Event Timeline (SNAP, SuperBowl, Easter)
   - Section F: Series Summary card
3. **Generate Forecast & Forecast Results**:
   - 4-Step Selection: Store → Product → 3 Large Horizon Cards (7D, 28D, 90D) → Model Architecture
   - Sequential progress simulation:
     - *Preparing data...*
     - *Preparing forecasting features...*
     - *Generating forecast...*
     - *Preparing results...*
   - Results view with top summary metrics (Horizon, Forecasted Demand, MAPE, RMSE)
   - Direct horizon tabs (`[7 Days]` `[28 Days]` `[90 Days]`) above the chart for smooth switching without restarting
4. **Model Comparison**:
   - Objective comparison of **ARIMA / SARIMA, Prophet, LightGBM, DeepAR, and TFT**
   - Metric Table 1: 7D, 28D, 90D MAPE (Percentage Error)
   - Metric Table 2: 7D, 28D, 90D RMSE (Magnitude Error)
   - Grouped visual bar charts comparing error across models
   - Horizon consistency degradation curves
5. **Evaluation & Backtesting**:
   - Plain-language tooltips explaining MAPE and RMSE without complex math jargon
   - Walk-forward chronological rolling window backtesting visual (Folds 1 to 5)
   - Horizon consistency analysis (Short vs Medium vs Long stability)
6. **Business Insights**:
   - Advisory decision support for store and supply chain planners:
     - Demand Outlook
     - Inventory Planning (Safety buffers, reorder points, stockout risk)
     - Staffing Planning (Shift allocations, weekend workload surges)
     - Strategic 90-Day Planning (Lead-time windows, DC pallet bay allocation)

---

## 🚀 Running the Frontend
The development server is currently running at:
```
http://localhost:5173/
```

To run manually at any time:
```powershell
cd "c:\Major Project\frontend"
npm run dev
```
Or double-click `start_frontend.bat` in the project root.
