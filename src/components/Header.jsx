import React, { useState, useRef, useEffect } from 'react';
import { Menu, ChevronDown, LogIn, LogOut, ShieldCheck, Database, Zap } from 'lucide-react';
import { useAuth } from '../context/AuthContext';
import { useDataset } from '../context/DatasetContext';

export default function Header({ activeTab, onMobileToggle }) {
  const { user, isAuthenticated, signOut, openAuthModal } = useAuth();
  const { activeDatasetId, datasetSummary, backendOnline } = useDataset();
  const [profileDropdownOpen, setProfileDropdownOpen] = useState(false);
  const dropdownRef = useRef(null);

  useEffect(() => {
    function handleClickOutside(event) {
      if (dropdownRef.current && !dropdownRef.current.contains(event.target)) {
        setProfileDropdownOpen(false);
      }
    }
    document.addEventListener('mousedown', handleClickOutside);
    return () => document.removeEventListener('mousedown', handleClickOutside);
  }, []);

  const getPageInfo = (tab) => {
    if (tab === 'home') {
      return {
        title: 'Dashboard Overview',
        breadcrumb: 'ForecastIQ'
      };
    }
    return {
      title: 'Forecast Studio',
      breadcrumb: 'ForecastIQ / Forecast'
    };
  };

  const { title, breadcrumb } = getPageInfo(activeTab);

  const getInitials = (name) => {
    if (!name) return 'U';
    return name
      .split(' ')
      .map((part) => part[0])
      .join('')
      .slice(0, 2)
      .toUpperCase();
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

          <div>
            <div className="text-xs font-medium text-[#8E83A3]">
              {breadcrumb}
            </div>
            <h2 className="text-xl sm:text-2xl font-bold font-heading text-[#1F1B2C] tracking-tight">
              {title}
            </h2>
          </div>
        </div>

        {/* Right: Controls & Profile */}
        <div className="flex items-center gap-3">
          {/* Active Dataset Badge (Only shown if a real dataset is loaded) */}
          {datasetSummary ? (
            <div className="hidden md:flex items-center gap-2 bg-white px-3.5 py-1.5 rounded-xl border border-[#E5D9F2] shadow-xs text-xs text-[#5F5670]">
              <Database className="w-3.5 h-3.5 text-[#A294F9]" />
              <span className="font-semibold text-[#1F1B2C] max-w-[160px] truncate">
                {datasetSummary.dataset_name || 'Active Dataset'}
              </span>
            </div>
          ) : (
            <div className="hidden md:flex items-center gap-1.5 bg-white/70 px-3 py-1.5 rounded-xl border border-[#E5D9F2] text-xs text-[#8E83A3]">
              <span className="w-2 h-2 rounded-full bg-slate-300"></span>
              <span>No dataset loaded</span>
            </div>
          )}

          {/* Backend Status indicator */}
          <div 
            className={`hidden sm:flex items-center gap-1.5 px-2.5 py-1 rounded-xl text-[11px] font-semibold border ${
              backendOnline ? 'bg-emerald-50 text-emerald-700 border-emerald-200' : 'bg-amber-50 text-amber-700 border-amber-200'
            }`}
          >
            <span className={`w-1.5 h-1.5 rounded-full ${backendOnline ? 'bg-emerald-500' : 'bg-amber-500 animate-pulse'}`} />
            <span>{backendOnline ? 'Online' : 'Connecting...'}</span>
          </div>

          {/* User Profile / Auth Area */}
          {isAuthenticated && user ? (
            <div className="relative" ref={dropdownRef}>
              <button
                onClick={() => setProfileDropdownOpen(!profileDropdownOpen)}
                className="flex items-center gap-2.5 p-1.5 rounded-2xl hover:bg-white border border-transparent hover:border-[#E5D9F2] transition-all cursor-pointer"
              >
                <div className="w-8 h-8 rounded-full bg-[#E5D9F2] text-[#1F1B2C] font-semibold text-xs flex items-center justify-center border border-[#CDC1FF]">
                  {getInitials(user.name)}
                </div>
                <div className="hidden sm:block text-left">
                  <div className="text-xs font-semibold text-[#1F1B2C] leading-none">
                    {user.name}
                  </div>
                  <div className="text-[10px] text-[#8E83A3] mt-0.5">
                    {user.role || 'Member'}
                  </div>
                </div>
                <ChevronDown className="w-3.5 h-3.5 text-[#8E83A3] hidden sm:block" />
              </button>

              {/* Profile Dropdown Menu */}
              {profileDropdownOpen && (
                <div className="absolute right-0 mt-2 w-64 bg-white rounded-2xl shadow-xl border border-[#E5D9F2] p-2 z-50 animate-in fade-in zoom-in-95 duration-100">
                  <div className="p-3 border-b border-[#F5EFFF] bg-[#F5EFFF]/40 rounded-xl mb-1">
                    <p className="text-xs font-bold text-[#1F1B2C]">{user.name}</p>
                    <p className="text-[11px] text-[#8E83A3] truncate">{user.email}</p>
                    <div className="mt-2 inline-flex items-center gap-1.5 px-2 py-0.5 rounded-md bg-[#CDC1FF]/30 text-[#1F1B2C] text-[10px] font-medium">
                      <ShieldCheck className="w-3 h-3 text-[#A294F9]" />
                      <span>{user.role}</span>
                    </div>
                  </div>

                  <button
                    onClick={() => {
                      setProfileDropdownOpen(false);
                      signOut();
                    }}
                    className="w-full flex items-center gap-2.5 px-3 py-2 text-xs font-medium text-rose-600 hover:bg-rose-50 rounded-xl transition-colors cursor-pointer"
                  >
                    <LogOut className="w-4 h-4" />
                    <span>Sign Out</span>
                  </button>
                </div>
              )}
            </div>
          ) : (
            <div className="flex items-center gap-2">
              <button
                onClick={() => openAuthModal('signin')}
                className="flex items-center gap-2 px-3.5 py-1.5 text-xs font-semibold text-[#1F1B2C] bg-white border border-[#CDC1FF] rounded-xl hover:bg-[#F5EFFF] shadow-xs transition-all cursor-pointer"
              >
                <LogIn className="w-3.5 h-3.5 text-[#A294F9]" />
                <span>Sign In</span>
              </button>
            </div>
          )}
        </div>
      </div>
    </header>
  );
}
