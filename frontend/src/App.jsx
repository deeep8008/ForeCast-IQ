import React, { useState, useEffect, useCallback } from 'react';
import Sidebar from './components/Sidebar';
import Header from './components/Header';
import HomePage from './pages/HomePage';
import DataExplorerPage from './pages/DataExplorerPage';
import UploadDatasetPage from './pages/UploadDatasetPage';
import GenerateForecastPage from './pages/GenerateForecastPage';
import ModelComparisonPage from './pages/ModelComparisonPage';
import EvaluationPage from './pages/EvaluationPage';
import BusinessInsightsPage from './pages/BusinessInsightsPage';
import LoginPage from './pages/LoginPage';
import RegisterPage from './pages/RegisterPage';
import { AuthProvider } from './context/AuthContext';
import { restoreDatasetFromBackend } from './services/api';
import { AlertCircle, RefreshCw, RotateCcw } from 'lucide-react';

const VALID_TABS = ['home', 'explorer', 'upload', 'forecast', 'comparison', 'evaluation', 'insights', 'login', 'register'];
const STORAGE_ROUTE_KEY = 'forecastiq_active_tab';
const STORAGE_DATASET_ID_KEY = 'forecastiq_active_dataset_id';
const STORAGE_DATASET_META_KEY = 'forecastiq_active_dataset_meta';

function getInitialTab() {
  if (typeof window !== 'undefined') {
    const hash = window.location.hash.replace(/^#\/?/, '').toLowerCase();
    if (VALID_TABS.includes(hash)) {
      return hash;
    }
    const saved = localStorage.getItem(STORAGE_ROUTE_KEY);
    if (saved && VALID_TABS.includes(saved)) {
      return saved;
    }
  }
  return 'home';
}

function getStoredDatasetMeta() {
  if (typeof window !== 'undefined') {
    try {
      const raw = localStorage.getItem(STORAGE_DATASET_META_KEY);
      if (raw) return JSON.parse(raw);
    } catch {
      // Ignore parse error
    }
  }
  return null;
}

function AppContent() {
  const [activeTab, setActiveTabState] = useState(getInitialTab);
  const [mobileOpen, setMobileOpen] = useState(false);
  const [uploadedDataset, setUploadedDatasetState] = useState(getStoredDatasetMeta);
  const [isRestoringDataset, setIsRestoringDataset] = useState(false);
  const [restorationError, setRestorationError] = useState(null);

  // Sync activeTab with URL hash and localStorage
  const setActiveTab = useCallback((tab) => {
    if (!VALID_TABS.includes(tab)) return;
    setActiveTabState(tab);
    if (typeof window !== 'undefined') {
      localStorage.setItem(STORAGE_ROUTE_KEY, tab);
      if (window.location.hash.replace(/^#\/?/, '') !== tab) {
        window.history.pushState(null, '', `#/${tab}`);
      }
    }
  }, []);

  // Listen to browser Back/Forward navigation
  useEffect(() => {
    const handlePopState = () => {
      const hash = window.location.hash.replace(/^#\/?/, '').toLowerCase();
      if (VALID_TABS.includes(hash)) {
        setActiveTabState(hash);
        localStorage.setItem(STORAGE_ROUTE_KEY, hash);
      }
    };
    window.addEventListener('popstate', handlePopState);
    return () => window.removeEventListener('popstate', handlePopState);
  }, []);

  // Set initial hash if not set
  useEffect(() => {
    const currentHash = window.location.hash.replace(/^#\/?/, '').toLowerCase();
    if (!VALID_TABS.includes(currentHash)) {
      window.history.replaceState(null, '', `#/${activeTab}`);
    }
  }, [activeTab]);

  // Set and persist uploaded dataset
  const setUploadedDataset = useCallback((ds) => {
    setUploadedDatasetState(ds);
    setRestorationError(null);
    if (typeof window !== 'undefined') {
      if (ds && ds.dataset_id) {
        localStorage.setItem(STORAGE_DATASET_ID_KEY, ds.dataset_id);
        try {
          localStorage.setItem(STORAGE_DATASET_META_KEY, JSON.stringify(ds));
        } catch {
          // In case metadata exceeds quota, stored ID remains
        }
      } else {
        localStorage.removeItem(STORAGE_DATASET_ID_KEY);
        localStorage.removeItem(STORAGE_DATASET_META_KEY);
      }
    }
  }, []);

  // Restore custom dataset on initial load / refresh
  const restoreActiveDataset = useCallback(async (targetId) => {
    if (!targetId) return;
    setIsRestoringDataset(true);
    setRestorationError(null);
    try {
      const restored = await restoreDatasetFromBackend(targetId);
      setUploadedDatasetState(restored);
      try {
        localStorage.setItem(STORAGE_DATASET_META_KEY, JSON.stringify(restored));
      } catch {
        // Ignore quota error
      }
    } catch (err) {
      setRestorationError(err.message || `Failed to restore dataset '${targetId}' from server.`);
    } finally {
      setIsRestoringDataset(false);
    }
  }, []);

  useEffect(() => {
    const savedId = typeof window !== 'undefined' ? localStorage.getItem(STORAGE_DATASET_ID_KEY) : null;
    if (savedId) {
      restoreActiveDataset(savedId);
    }
  }, [restoreActiveDataset]);

  const handleClearCustomDataset = () => {
    setUploadedDataset(null);
    setRestorationError(null);
  };

  const renderActivePage = () => {
    // If we are actively restoring custom dataset, show loading state
    if (isRestoringDataset) {
      return (
        <div className="flex flex-col items-center justify-center p-16 space-y-4 bg-white rounded-3xl border border-[#E5D9F2] shadow-xs text-center" data-testid="restoring-dataset-spinner">
          <div className="w-10 h-10 border-3 border-[#A294F9] border-t-transparent rounded-full animate-spin"></div>
          <div className="text-sm font-bold text-[#1F1B2C]">Restoring Active Dataset...</div>
          <div className="text-xs text-[#5F5670]">Reconnecting with persistence engine and loading verified artifacts.</div>
        </div>
      );
    }

    switch (activeTab) {
      case 'home':
        return <HomePage onNavigate={setActiveTab} />;
      case 'explorer':
        return <DataExplorerPage onNavigate={setActiveTab} uploadedDataset={uploadedDataset} />;
      case 'upload':
        return (
          <UploadDatasetPage 
            onNavigate={setActiveTab} 
            uploadedDataset={uploadedDataset}
            onDatasetReady={(ds) => setUploadedDataset(ds)} 
            onClearDataset={handleClearCustomDataset}
          />
        );
      case 'forecast':
        return (
          <GenerateForecastPage 
            onNavigate={setActiveTab} 
            uploadedDataset={uploadedDataset} 
          />
        );
      case 'comparison':
        return (
          <ModelComparisonPage 
            onNavigate={setActiveTab} 
            uploadedDataset={uploadedDataset} 
          />
        );
      case 'evaluation':
        return (
          <EvaluationPage 
            onNavigate={setActiveTab} 
            uploadedDataset={uploadedDataset} 
          />
        );
      case 'insights':
        return (
          <BusinessInsightsPage 
            onNavigate={setActiveTab} 
            uploadedDataset={uploadedDataset} 
          />
        );
      case 'login':
        return <LoginPage onNavigate={setActiveTab} />;
      case 'register':
        return <RegisterPage onNavigate={setActiveTab} />;
      default:
        return <HomePage onNavigate={setActiveTab} />;
    }
  };

  return (
    <div className="min-h-screen bg-[#F5EFFF] text-[#1F1B2C] flex">
      {/* Fixed Sidebar */}
      <Sidebar 
        activeTab={activeTab} 
        setActiveTab={setActiveTab} 
        mobileOpen={mobileOpen} 
        setMobileOpen={setMobileOpen} 
        uploadedDataset={uploadedDataset}
      />

      {/* Main Content Area (Offset by sidebar width on large screens) */}
      <div className="flex-1 lg:pl-64 flex flex-col min-h-screen">
        {/* Top Header */}
        <Header 
          activeTab={activeTab} 
          onMobileToggle={() => setMobileOpen(true)} 
          uploadedDataset={uploadedDataset}
          isRestoringDataset={isRestoringDataset}
          restorationError={restorationError}
          onNavigate={setActiveTab}
        />

        {/* Page Content Container with generous padding */}
        <main className="flex-1 p-6 sm:p-8 lg:p-10">
          {restorationError && (
            <div 
              data-testid="dataset-restoration-error-banner"
              className="mb-6 p-4 rounded-2xl bg-[#FFF0F2] border border-[#F5B5BA] text-[#841922] flex flex-col sm:flex-row sm:items-center justify-between gap-4"
            >
              <div className="flex items-start gap-3">
                <span className="text-xl">⚠️</span>
                <div>
                  <div className="font-semibold text-sm">Failed to restore active custom dataset</div>
                  <div className="text-xs text-[#9E343E] mt-0.5">{restorationError}</div>
                  <div className="text-[11px] text-[#A64550] mt-1">
                    Your previous dataset could not be retrieved from the server. You can retry connecting or switch back to the M5 benchmark dataset.
                  </div>
                </div>
              </div>
              <div className="flex items-center gap-2 shrink-0">
                <button
                  type="button"
                  data-testid="retry-restore-btn"
                  onClick={() => {
                    const savedId = typeof window !== 'undefined' ? localStorage.getItem(STORAGE_DATASET_ID_KEY) : null;
                    if (savedId) restoreActiveDataset(savedId);
                  }}
                  className="px-3 py-1.5 bg-[#841922] text-white text-xs font-medium rounded-lg hover:bg-[#6A121A] transition-colors"
                >
                  Retry
                </button>
                <button
                  type="button"
                  data-testid="reset-to-benchmark-btn"
                  onClick={handleClearCustomDataset}
                  className="px-3 py-1.5 bg-white text-[#841922] border border-[#F5B5BA] text-xs font-medium rounded-lg hover:bg-[#FFF5F6] transition-colors"
                >
                  Reset to M5 Benchmark
                </button>
              </div>
            </div>
          )}
          {renderActivePage()}
        </main>

        {/* Minimal Footer */}
        <footer className="px-8 py-5 border-t border-[#E5D9F2]/70 text-xs text-[#8E83A3] flex flex-col sm:flex-row items-center justify-between gap-3">
          <div>
            <strong>ForecastIQ</strong> — Multi-Horizon Time-Series Forecasting for Enterprise Analytics
          </div>
          <div className="flex items-center gap-4 text-[11px]">
            <span>M5 Accuracy Benchmark</span>
            <span>•</span>
            <span>Darts + PyTorch Engine</span>
            <span>•</span>
            <span className="text-[#A294F9] font-medium">Enterprise Ready</span>
          </div>
        </footer>
      </div>
    </div>
  );
}

export default function App() {
  return (
    <AuthProvider>
      <AppContent />
    </AuthProvider>
  );
}

