import React, { useState, useMemo } from 'react';
import { Eye, EyeOff } from 'lucide-react';

export default function ForecastChart({ 
  history = [], 
  forecast = [], 
  _todayDate = '2016-04-24', 
  horizonDays = 28, 
  onHorizonChange = null,
  showHorizonSwitch = true,
  storeName = 'CA_1',
  productName = 'FOODS_3_090'
}) {
  const [hoverIndex, setHoverIndex] = useState(null);
  const [showCI, setShowCI] = useState(true);

  // Combine visible window: last 45 days of history + forecast
  const visibleHistory = useMemo(() => {
    return history.slice(-45);
  }, [history]);

  const allPoints = useMemo(() => {
    const list = [];
    visibleHistory.forEach(h => {
      list.push({
        date: h.date,
        actual: h.sales,
        forecast: null,
        lower: null,
        upper: null,
        isFuture: false,
        eventName: h.eventName
      });
    });

    forecast.forEach(f => {
      list.push({
        date: f.date,
        actual: null,
        forecast: f.forecast,
        lower: f.lower,
        upper: f.upper,
        isFuture: true,
        eventName: null
      });
    });

    return list;
  }, [visibleHistory, forecast]);

  // Chart dimensions & scales
  const width = 860;
  const height = 340;
  const padding = { top: 25, right: 35, bottom: 45, left: 55 };
  const innerWidth = width - padding.left - padding.right;
  const innerHeight = height - padding.top - padding.bottom;

  const maxVal = useMemo(() => {
    let max = 0;
    allPoints.forEach(p => {
      if (p.actual !== null && p.actual > max) max = p.actual;
      if (p.upper !== null && p.upper > max) max = p.upper;
      if (p.forecast !== null && p.forecast > max) max = p.forecast;
    });
    return Math.ceil((max * 1.15) / 10) * 10 || 100;
  }, [allPoints]);

  const getX = React.useCallback(
    (idx) => padding.left + (idx / (allPoints.length - 1 || 1)) * innerWidth,
    [padding.left, allPoints.length, innerWidth]
  );
  const getY = React.useCallback(
    (val) => padding.top + innerHeight - (val / maxVal) * innerHeight,
    [padding.top, innerHeight, maxVal]
  );

  // Build SVG path for actual sales
  const actualPath = useMemo(() => {
    let d = '';
    visibleHistory.forEach((h, i) => {
      const x = getX(i);
      const y = getY(h.sales);
      d += i === 0 ? `M ${x} ${y}` : ` L ${x} ${y}`;
    });
    return d;
  }, [visibleHistory, getX, getY]);

  // Build SVG path for forecast
  const forecastPath = useMemo(() => {
    if (forecast.length === 0) return '';
    let d = '';
    const startIndex = visibleHistory.length - 1;
    // Connect last actual point to first forecast point for seamless continuity
    const lastActual = visibleHistory[visibleHistory.length - 1];
    if (lastActual) {
      d += `M ${getX(startIndex)} ${getY(lastActual.sales)}`;
    }
    forecast.forEach((f, i) => {
      const globalIdx = visibleHistory.length + i;
      const x = getX(globalIdx);
      const y = getY(f.forecast);
      d += !lastActual && i === 0 ? `M ${x} ${y}` : ` L ${x} ${y}`;
    });
    return d;
  }, [visibleHistory, forecast, getX, getY]);

  // Confidence Interval polygon area
  const ciAreaPath = useMemo(() => {
    if (!showCI || forecast.length === 0) return '';
    const hasValidCI = forecast.some(f => f.upper != null && f.lower != null);
    if (!hasValidCI) return '';

    const upperPoints = [];
    const lowerPoints = [];

    // Anchor to last actual
    const startIndex = visibleHistory.length - 1;
    const lastActual = visibleHistory[visibleHistory.length - 1];
    if (lastActual) {
      upperPoints.push(`${getX(startIndex)},${getY(lastActual.sales)}`);
      lowerPoints.push(`${getX(startIndex)},${getY(lastActual.sales)}`);
    }

    forecast.forEach((f, i) => {
      const globalIdx = visibleHistory.length + i;
      const x = getX(globalIdx);
      const upperVal = f.upper != null ? f.upper : f.forecast;
      const lowerVal = f.lower != null ? f.lower : f.forecast;
      upperPoints.push(`${x},${getY(upperVal)}`);
      lowerPoints.push(`${x},${getY(lowerVal)}`);
    });

    return `M ${upperPoints.join(' L ')} L ${lowerPoints.reverse().join(' L ')} Z`;
  }, [showCI, forecast, visibleHistory, getX, getY]);

  // Cutoff marker x position
  const cutoffX = getX(visibleHistory.length - 1);

  // Active hover point
  const activePoint = hoverIndex !== null ? allPoints[hoverIndex] : null;

  return (
    <div className="w-full">
      {/* Top Controls / Horizon Tabs */}
      {showHorizonSwitch && (
        <div className="flex flex-wrap items-center justify-between gap-3 mb-4">
          <div className="flex items-center gap-2">
            <span className="text-xs font-semibold uppercase tracking-wider text-[#5F5670]">
              Horizon:
            </span>
            <div className="inline-flex p-1 rounded-xl bg-[#F5EFFF] border border-[#E5D9F2]">
              {[7, 28, 90].map((days) => {
                const isActive = horizonDays === days;
                return (
                  <button
                    key={days}
                    onClick={() => onHorizonChange && onHorizonChange(days)}
                    className={`
                      px-3.5 py-1.5 rounded-lg text-xs font-medium transition-all
                      ${isActive 
                        ? 'bg-[#A294F9] text-white shadow-xs font-semibold' 
                        : 'text-[#5F5670] hover:text-[#1F1B2C]'
                      }
                    `}
                  >
                    {days} Days {days === 7 ? '(Short)' : days === 28 ? '(Medium)' : '(Long)'}
                  </button>
                );
              })}
            </div>
          </div>

          {/* Toggle Confidence Intervals */}
          <button
            onClick={() => setShowCI(!showCI)}
            className="flex items-center gap-1.5 text-xs text-[#5F5670] bg-[#F5EFFF] hover:bg-[#E5D9F2]/60 px-3 py-1.5 rounded-xl border border-[#E5D9F2] transition-colors"
          >
            {showCI ? <Eye className="w-3.5 h-3.5 text-[#A294F9]" /> : <EyeOff className="w-3.5 h-3.5" />}
            <span>Confidence Interval {showCI ? 'Visible' : 'Hidden'}</span>
          </button>
        </div>
      )}

      {/* SVG Chart Container */}
      <div className="relative w-full overflow-hidden rounded-2xl bg-white border border-[#E5D9F2] p-2 shadow-xs">
        <svg 
          viewBox={`0 0 ${width} ${height}`} 
          className="w-full h-auto select-none"
          onMouseLeave={() => setHoverIndex(null)}
        >
          {/* Subtle grid lines */}
          {[0, 0.25, 0.5, 0.75, 1].map((ratio) => {
            const y = padding.top + innerHeight * (1 - ratio);
            const val = Math.round(maxVal * ratio);
            return (
              <g key={ratio}>
                <line 
                  x1={padding.left} 
                  y1={y} 
                  x2={width - padding.right} 
                  y2={y} 
                  stroke="#F5EFFF" 
                  strokeDasharray="4 4"
                  strokeWidth="1"
                />
                <text 
                  x={padding.left - 10} 
                  y={y + 4} 
                  textAnchor="end" 
                  className="text-[10px] fill-[#8E83A3] font-medium"
                >
                  {val}
                </text>
              </g>
            );
          })}

          {/* Shaded Forecast Interval Polygon */}
          {ciAreaPath && (
            <path 
              d={ciAreaPath} 
              fill="#E5D9F2" 
              fillOpacity="0.45" 
            />
          )}

          {/* Historical Actuals Line */}
          <path 
            d={actualPath} 
            fill="none" 
            stroke="#5F5670" 
            strokeWidth="2" 
            strokeLinecap="round" 
            strokeLinejoin="round" 
          />

          {/* Forecast Prediction Line */}
          {forecastPath && (
            <path 
              d={forecastPath} 
              fill="none" 
              stroke="#A294F9" 
              strokeWidth="2.5" 
              strokeDasharray="none"
              strokeLinecap="round" 
              strokeLinejoin="round" 
            />
          )}

          {/* Historical vs Forecast Cutoff Boundary */}
          <line 
            x1={cutoffX} 
            y1={padding.top} 
            x2={cutoffX} 
            y2={height - padding.bottom} 
            stroke="#A294F9" 
            strokeWidth="1.5" 
            strokeDasharray="4 4" 
          />
          <text 
            x={cutoffX + 6} 
            y={padding.top + 12} 
            className="text-[10px] font-semibold fill-[#A294F9]"
          >
            Today / Cutoff
          </text>

          {/* Date Axis Ticks */}
          {[0, 0.25, 0.5, 0.75, 1].map((ratio) => {
            const idx = Math.min(
              allPoints.length - 1, 
              Math.floor((allPoints.length - 1) * ratio)
            );
            const pt = allPoints[idx];
            if (!pt) return null;
            const x = getX(idx);
            return (
              <text 
                key={ratio} 
                x={x} 
                y={height - padding.bottom + 20} 
                textAnchor="middle" 
                className="text-[10px] fill-[#8E83A3] font-medium"
              >
                {pt.date.slice(5)}
              </text>
            );
          })}

          {/* Hover hit detection zones */}
          {allPoints.map((pt, i) => {
            const x = getX(i);
            return (
              <rect
                key={i}
                x={x - (innerWidth / allPoints.length) / 2}
                y={padding.top}
                width={innerWidth / allPoints.length}
                height={innerHeight}
                fill="transparent"
                onMouseEnter={() => setHoverIndex(i)}
                className="cursor-pointer"
              />
            );
          })}

          {/* Active Hover Crosshair & Dots */}
          {hoverIndex !== null && activePoint && (
            <g>
              <line 
                x1={getX(hoverIndex)} 
                y1={padding.top} 
                x2={getX(hoverIndex)} 
                y2={height - padding.bottom} 
                stroke="#CDC1FF" 
                strokeWidth="1" 
              />
              {activePoint.actual !== null && (
                <circle 
                  cx={getX(hoverIndex)} 
                  cy={getY(activePoint.actual)} 
                  r="4.5" 
                  fill="#5F5670" 
                  stroke="#FFFFFF" 
                  strokeWidth="2" 
                />
              )}
              {activePoint.forecast !== null && (
                <circle 
                  cx={getX(hoverIndex)} 
                  cy={getY(activePoint.forecast)} 
                  r="5" 
                  fill="#A294F9" 
                  stroke="#FFFFFF" 
                  strokeWidth="2" 
                />
              )}
            </g>
          )}
        </svg>

        {/* Floating Tooltip */}
        {hoverIndex !== null && activePoint && (
          <div 
            className="absolute top-4 right-4 bg-white/95 backdrop-blur-xs border border-[#CDC1FF] rounded-xl p-3 shadow-md text-xs pointer-events-none min-w-[170px]"
          >
            <div className="font-semibold text-[#1F1B2C] border-b border-[#F5EFFF] pb-1.5 mb-2 flex items-center justify-between">
              <span>{activePoint.date}</span>
              <span className={`text-[10px] px-1.5 py-0.5 rounded-full font-medium ${
                activePoint.isFuture ? 'bg-[#E5D9F2] text-[#A294F9]' : 'bg-gray-100 text-[#5F5670]'
              }`}>
                {activePoint.isFuture ? 'Forecasted' : 'Historical'}
              </span>
            </div>

            {activePoint.actual !== null && (
              <div className="flex items-center justify-between text-[#5F5670] mb-1">
                <span>Actual Demand:</span>
                <span className="font-bold text-[#1F1B2C]">{activePoint.actual} units</span>
              </div>
            )}

            {activePoint.forecast !== null && (
              <>
                <div className="flex items-center justify-between text-[#A294F9] font-medium mb-1">
                  <span>Forecast:</span>
                  <span className="font-bold text-[#1F1B2C]">{activePoint.forecast} units</span>
                </div>
                {showCI && (
                  <div className="flex items-center justify-between text-[#8E83A3] text-[11px]">
                    <span>Interval (90%):</span>
                    <span>[{activePoint.lower} – {activePoint.upper}]</span>
                  </div>
                )}
              </>
            )}

            {activePoint.eventName && (
              <div className="mt-1.5 pt-1.5 border-t border-[#F5EFFF] text-[11px] text-[#A294F9] font-medium">
                ★ {activePoint.eventName}
              </div>
            )}
          </div>
        )}
      </div>

      {/* Chart Legend */}
      <div className="flex flex-wrap items-center justify-between gap-4 mt-3 px-2 text-xs text-[#5F5670]">
        <div className="flex items-center gap-5">
          <div className="flex items-center gap-2">
            <span className="w-3.5 h-0.5 bg-[#5F5670] rounded-full inline-block"></span>
            <span>Historical Sales (Daily)</span>
          </div>
          <div className="flex items-center gap-2">
            <span className="w-3.5 h-0.5 bg-[#A294F9] rounded-full inline-block"></span>
            <span className="font-medium text-[#1F1B2C]">Predicted Forecast</span>
          </div>
          {showCI && (
            <div className="flex items-center gap-2">
              <span className="w-3 h-3 bg-[#E5D9F2] rounded-xs inline-block border border-[#CDC1FF]/50"></span>
              <span>Forecast Interval (Uncertainty Range)</span>
            </div>
          )}
        </div>

        <div className="text-[11px] text-[#8E83A3]">
          Series: <span className="font-semibold text-[#1F1B2C]">{storeName}</span> / {productName}
        </div>
      </div>
    </div>
  );
}
