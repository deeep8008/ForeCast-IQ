import React, { useState, useRef, useEffect } from 'react';
import { Menu, Bell, Calendar, LogIn, UserPlus, LogOut, User, ChevronDown } from 'lucide-react';
import { useAuth } from '../context/AuthContext';

export default function Header({ 
  activeTab, 
  onMobileToggle, 
  uploadedDataset = null, 
  isRestoringDataset = false, 
  restorationError = null,
  onNavigate = null
}) {
  const { user, isAuthenticated, logout } = useAuth();
  const [accountMenuOpen, setAccountMenuOpen] = useState(false);
  const accountMenuRef = useRef(null);

  // Close account menu on outside click
  useEffect(() => {
    function handleClickOutside(event) {
      if (accountMenuRef.current && !accountMenuRef.current.contains(event.target)) {
        setAccountMenuOpen(false);
      }
    }
    document.addEventListener('mousedown', handleClickOutside);
    return () => document.removeEventListener('mousedown', handleClickOutside);
  }, []);

  const getPageInfo = (tab) => {
    switch (tab) {
      case 'home':
        return {
          title: 'Forecast-IQ',
          breadcrumb: 'Enterprise Demand Planning'
        };
      case 'explorer':
        return {
          title: 'Data Explorer',
          breadcrumb: 'ForecastIQ / M5 Dataset Understanding'
        };
      case 'upload':
        return {
          title: 'Upload Dataset',
          breadcrumb: 'ForecastIQ / Universal Data Ingestion'
        };
      case 'forecast':
        return {
          title: 'Generate Forecast',
          breadcrumb: 'ForecastIQ / Multi-Horizon Inference'
        };
      case 'comparison':
        return {
          title: 'Model Comparison',
          breadcrumb: 'ForecastIQ / Benchmark Across Horizons'
        };
      case 'evaluation':
        return {
          title: 'Evaluation & Backtesting',
          breadcrumb: 'ForecastIQ / Error Diagnostics (MAPE & RMSE)'
        };
      case 'insights':
        return {
          title: 'Business Insights',
          breadcrumb: 'ForecastIQ / Decision Support & Planning'
        };
      case 'login':
        return {
          title: 'Sign In',
          breadcrumb: 'ForecastIQ / Account Access'
        };
      case 'register':
        return {
          title: 'Register',
          breadcrumb: 'ForecastIQ / Account Creation'
        };
      default:
        return {
          title: 'ForecastIQ',
          breadcrumb: 'Multi-Horizon Time-Series Forecasting'
        };
    }
  };

  const { title, breadcrumb } = getPageInfo(activeTab);

  // Compute cutoff display based on active dataset state
  const renderCutoff = () => {
    if (isRestoringDataset) {
      return (
        <div 
          data-testid="header-cutoff-badge"
          className="hidden md:flex items-center gap-2 bg-white px-3 py-1.5 rounded-xl border border-[#E5D9F2] shadow-xs text-xs text-[#5F5670]"
        >
          <div className="w-3 h-3 border-2 border-[#A294F9] border-t-transparent rounded-full animate-spin"></div>
          <span className="font-medium text-[#1F1B2C]">Cutoff:</span>
          <span>Resolving...</span>
        </div>
      );
    }

    if (restorationError) {
      return (
        <div 
          data-testid="header-cutoff-badge"
          className="hidden md:flex items-center gap-2 bg-white px-3 py-1.5 rounded-xl border border-rose-200 shadow-xs text-xs text-rose-600"
        >
          <Calendar className="w-3.5 h-3.5 text-rose-400" />
          <span className="font-medium">Cutoff:</span>
          <span>Unavailable</span>
        </div>
      );
    }

    if (!uploadedDataset) {
      // Default M5 Benchmark
      return (
        <div 
          data-testid="header-cutoff-badge"
          className="hidden md:flex items-center gap-2 bg-white px-3 py-1.5 rounded-xl border border-[#E5D9F2] shadow-xs text-xs text-[#5F5670]"
        >
          <Calendar className="w-3.5 h-3.5 text-[#A294F9]" />
          <span className="font-medium text-[#1F1B2C]">Cutoff: Day 1913</span>
          <span className="text-[#CDC1FF]">•</span>
          <span>2016-04-24</span>
        </div>
      );
    }

    const dateRangeEnd = uploadedDataset.profile?.dateRange?.end;
    const splitTestEnd = uploadedDataset.splits?.test?.end_date;
    const cutoffDate = (dateRangeEnd && dateRangeEnd !== 'N/A') ? dateRangeEnd : (splitTestEnd || 'N/A');
    const dayIndex = uploadedDataset.benchmarkDayIndex || uploadedDataset.profile?.dayIndex || null;

    return (
      <div 
        data-testid="header-cutoff-badge"
        className="hidden md:flex items-center gap-2 bg-white px-3 py-1.5 rounded-xl border border-[#E5D9F2] shadow-xs text-xs text-[#5F5670]"
      >
        <Calendar className="w-3.5 h-3.5 text-[#A294F9]" />
        {dayIndex ? (
          <>
            <span className="font-medium text-[#1F1B2C]">Cutoff: Day {dayIndex}</span>
            <span className="text-[#CDC1FF]">•</span>
            <span>{cutoffDate}</span>
          </>
        ) : (
          <>
            <span className="font-medium text-[#1F1B2C]">Cutoff:</span>
            <span>{cutoffDate}</span>
          </>
        )}
      </div>
    );
  };

  const getInitials = (name) => {
    if (!name) return 'EP';
    const parts = name.trim().split(/\s+/);
    if (parts.length >= 2) {
      return (parts[0][0] + parts[1][0]).toUpperCase();
    }
    return name.slice(0, 2).toUpperCase();
  };

  return (
    <header className="sticky top-0 z-30 bg-[#F5EFFF]/90 backdrop-blur-md border-b border-[#E5D9F2]/60 px-6 py-4">
      <div className="flex items-center justify-between gap-4">
        {/* Left: Mobile trigger & Titles */}
        <div className="flex items-center gap-3">
          <button
            onClick={onMobileToggle}
            className="p-2 -ml-2 rounded-xl text-[#5F5670] hover:bg-white hover:text-[#1F1B2C] lg:hidden transition-colors"
            aria-label="Toggle Navigation"
          >
            <Menu className="w-5 h-5" />
          </button>

          {activeTab !== 'home' && (
            <div>
              <div className="text-xs font-medium text-[#8E83A3]">
                {breadcrumb}
              </div>
              <h2 className="text-xl sm:text-2xl font-bold font-heading text-[#1F1B2C] tracking-tight">
                {title}
              </h2>
            </div>
          )}
        </div>

        {/* Right: Controls & Profile / Auth */}
        <div className="flex items-center gap-3">
          {/* Baseline Context selector */}
          {renderCutoff()}

          {/* Quick Notification */}
          <button 
            className="relative p-2 rounded-xl bg-white border border-[#E5D9F2] text-[#5F5670] hover:text-[#1F1B2C] hover:border-[#CDC1FF] shadow-xs transition-colors"
            title="System alerts: 0 critical, models validated"
          >
            <Bell className="w-4 h-4" />
            <span className="absolute top-1.5 right-1.5 w-2 h-2 rounded-full bg-[#A294F9]"></span>
          </button>

          {/* Authentication State: Logged In vs Logged Out */}
          {isAuthenticated && user ? (
            <div className="relative pl-2" ref={accountMenuRef}>
              <button
                type="button"
                data-testid="user-account-menu-button"
                onClick={() => setAccountMenuOpen(!accountMenuOpen)}
                className="flex items-center gap-2.5 p-1.5 rounded-2xl hover:bg-white/80 border border-transparent hover:border-[#E5D9F2] transition-all cursor-pointer"
              >
                <div className="w-8 h-8 rounded-full bg-gradient-to-br from-[#A294F9] to-[#CDC1FF] text-white font-semibold text-xs flex items-center justify-center border border-[#CDC1FF] shadow-xs">
                  {getInitials(user.full_name)}
                </div>
                <div className="hidden sm:block text-left">
                  <div className="text-xs font-semibold text-[#1F1B2C] leading-none">
                    {user.full_name}
                  </div>
                  <div className="text-[10px] text-[#8E83A3] mt-0.5 truncate max-w-[130px]">
                    {user.email}
                  </div>
                </div>
                <ChevronDown className="w-3.5 h-3.5 text-[#8E83A3]" />
              </button>

              {/* Account Dropdown Menu */}
              {accountMenuOpen && (
                <div 
                  data-testid="user-account-dropdown"
                  className="absolute right-0 mt-2 w-56 bg-white rounded-2xl border border-[#E5D9F2] shadow-lg py-2 z-50 animate-in fade-in zoom-in-95 duration-100"
                >
                  <div className="px-4 py-2.5 border-b border-[#F5EFFF]">
                    <div className="text-xs font-bold text-[#1F1B2C] truncate">
                      {user.full_name}
                    </div>
                    <div className="text-[11px] text-[#8E83A3] truncate mt-0.5">
                      {user.email}
                    </div>
                  </div>

                  <div className="p-1">
                    <button
                      type="button"
                      data-testid="logout-button"
                      onClick={async () => {
                        setAccountMenuOpen(false);
                        await logout();
                        if (onNavigate) onNavigate('home');
                      }}
                      className="w-full flex items-center gap-2.5 px-3 py-2 text-xs font-medium text-rose-600 hover:bg-rose-50 rounded-xl transition-colors text-left cursor-pointer"
                    >
                      <LogOut className="w-4 h-4" />
                      <span>Sign Out</span>
                    </button>
                  </div>
                </div>
              )}
            </div>
          ) : (
            <div className="flex items-center gap-2 pl-2">
              <button
                type="button"
                data-testid="header-login-button"
                onClick={() => onNavigate && onNavigate('login')}
                className="flex items-center gap-1.5 px-3.5 py-1.5 rounded-xl border border-[#CDC1FF] bg-white hover:bg-[#F5EFFF] text-[#1F1B2C] text-xs font-semibold shadow-xs transition-colors cursor-pointer"
              >
                <LogIn className="w-3.5 h-3.5 text-[#A294F9]" />
                <span>Sign In</span>
              </button>

              <button
                type="button"
                data-testid="header-register-button"
                onClick={() => onNavigate && onNavigate('register')}
                className="flex items-center gap-1.5 px-3.5 py-1.5 rounded-xl bg-[#A294F9] hover:bg-[#8F7EF7] text-white text-xs font-semibold shadow-xs transition-colors cursor-pointer"
              >
                <UserPlus className="w-3.5 h-3.5" />
                <span>Register</span>
              </button>
            </div>
          )}
        </div>
      </div>
    </header>
  );
}

