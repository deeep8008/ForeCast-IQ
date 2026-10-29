import React from 'react';
import { 
  Home, 
  Search, 
  Upload,
  Zap, 
  BarChart2, 
  CheckCircle2, 
  Briefcase, 
  Layers
} from 'lucide-react';

export default function Sidebar({ activeTab, setActiveTab, mobileOpen, setMobileOpen, uploadedDataset = null }) {
  const navItems = [
    { id: 'home', label: 'Home', icon: Home, badge: null },
    { id: 'explorer', label: 'Data Explorer', icon: Search, badge: null },
    { id: 'upload', label: 'Upload Dataset', icon: Upload, badge: 'Step 1' },
    { id: 'evaluation', label: 'Evaluation & Backtesting', icon: CheckCircle2, badge: 'Step 2' },
    { id: 'comparison', label: 'Model Comparison', icon: BarChart2, badge: 'Step 3' },
    { id: 'forecast', label: 'Generate Forecast', icon: Zap, badge: 'Step 4' },
    { id: 'insights', label: 'Business Insights', icon: Briefcase, badge: 'Step 5' },
  ];

  return (
    <>
      {/* Mobile backdrop */}
      {mobileOpen && (
        <div 
          onClick={() => setMobileOpen(false)}
          className="fixed inset-0 bg-black/20 backdrop-blur-xs z-40 lg:hidden transition-opacity"
        />
      )}

      <aside className={`
        fixed top-0 bottom-0 left-0 z-50 w-64 bg-white border-r border-[#E5D9F2] flex flex-col justify-between
        transition-transform duration-200 ease-in-out lg:translate-x-0
        ${mobileOpen ? 'translate-x-0 shadow-xl' : '-translate-x-full lg:translate-x-0'}
      `}>
        {/* Brand & Header */}
        <div>
          <div className="p-6 border-b border-[#F5EFFF]">
            <div className="flex items-center gap-3">
              <div className="w-10 h-10 rounded-xl bg-gradient-to-br from-[#A294F9] to-[#CDC1FF] flex items-center justify-center text-white shadow-xs">
                <Layers className="w-5 h-5 text-white" />
              </div>
              <div>
                <h1 className="text-xl font-bold font-heading text-[#1F1B2C] tracking-tight leading-none">
                  Forecast<span className="text-[#A294F9]">IQ</span>
                </h1>
                <p className="text-xs text-[#5F5670] mt-1 font-medium">
                  Multi-Horizon Demand Forecasting
                </p>
              </div>
            </div>
          </div>

          {/* Navigation Links */}
          <nav className="p-4 space-y-1.5">
            <div className="px-3 py-1.5 text-[11px] font-semibold text-[#8E83A3] uppercase tracking-wider">
              Navigation
            </div>
            {navItems.map((item) => {
              const Icon = item.icon;
              const isActive = activeTab === item.id;
              return (
                <button
                  key={item.id}
                  onClick={() => {
                    setActiveTab(item.id);
                    if (setMobileOpen) setMobileOpen(false);
                  }}
                  className={`
                    w-full flex items-center justify-between px-3.5 py-2.5 rounded-xl text-sm font-medium transition-all
                    ${isActive 
                      ? 'bg-[#F5EFFF] text-[#1F1B2C] border border-[#CDC1FF] font-semibold shadow-xs' 
                      : 'text-[#5F5670] hover:bg-[#F5EFFF]/60 hover:text-[#1F1B2C]'
                    }
                  `}
                >
                  <div className="flex items-center gap-3">
                    <Icon className={`w-4 h-4 ${isActive ? 'text-[#A294F9]' : 'text-[#8E83A3]'}`} />
                    <span>{item.label}</span>
                  </div>
                  {item.badge && (
                    <span className={`text-[10px] px-2 py-0.5 rounded-full font-medium ${
                      isActive 
                        ? 'bg-[#A294F9] text-white' 
                        : 'bg-[#E5D9F2]/70 text-[#5F5670]'
                    }`}>
                      {item.badge}
                    </span>
                  )}
                </button>
              );
            })}
          </nav>
        </div>

        {/* Bottom Dataset Status Card */}
        <div className="p-4 m-3 rounded-2xl bg-[#F5EFFF] border border-[#E5D9F2] text-[#1F1B2C]">
          <div className="flex items-center justify-between mb-2">
            <span className="text-[11px] font-semibold uppercase tracking-wider text-[#8E83A3]">
              Active Dataset
            </span>
            <span className="inline-flex items-center gap-1.5 text-[11px] font-medium text-emerald-600 bg-white px-2 py-0.5 rounded-full border border-emerald-100 shadow-xs">
              <span className="w-1.5 h-1.5 rounded-full bg-emerald-500 animate-pulse"></span>
              {uploadedDataset ? 'Custom Active' : 'Dataset loaded'}
            </span>
          </div>

          <div className="space-y-1">
            <div className="font-semibold text-xs text-[#1F1B2C] truncate" title={uploadedDataset?.filename || 'M5 Forecasting Accuracy'}>
              {uploadedDataset ? uploadedDataset.filename : 'M5 Forecasting Accuracy'}
            </div>
            <div className="text-[11px] text-[#5F5670] leading-relaxed">
              {uploadedDataset ? (
                <>
                  • {(uploadedDataset.profile?.rowsCount ?? uploadedDataset.cleaning?.raw_rows ?? 0).toLocaleString()} observation rows<br />
                  • {uploadedDataset.profile?.uniqueSeriesCount ?? 1} unique time series<br />
                  • Cadence: {uploadedDataset.profile?.detectedFrequency || 'Daily (D)'}
                </>
              ) : (
                <>
                  • 42,840 product-store series<br />
                  • 10 retail stores (CA, TX, WI)<br />
                  • Daily cadence with calendar & prices
                </>
              )}
            </div>
          </div>

          <div className="mt-3 pt-2 border-t border-[#E5D9F2]/80 flex items-center justify-between text-[11px] text-[#8E83A3]">
            <span>{uploadedDataset ? 'Universal format' : 'Hierarchical sales'}</span>
            <span className="text-[#A294F9] font-medium">Ready</span>
          </div>
        </div>
      </aside>
    </>
  );
}
