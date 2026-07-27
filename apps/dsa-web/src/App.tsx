import type React from 'react';
import { lazy, useEffect } from 'react';
import { BrowserRouter as Router, Navigate, Route, Routes, useLocation } from 'react-router-dom';
import { ApiErrorAlert, Shell } from './components/common';
import {
  PageLoadingFallback,
  RouteOutletBoundary,
  StandaloneRouteBoundary,
} from './components/layout/RouteBoundary';
import { AuthProvider, useAuth } from './contexts/AuthContext';
import { UiLanguageProvider, useUiLanguage } from './contexts/UiLanguageContext';
import { useAgentChatStore } from './stores/agentChatStore';
import MainTabs from './components/layout/MainTabs';
import AdminLayout from './components/layout/AdminLayout';
import './App.css';

const HomePage = lazy(() => import('./pages/HomePage'));
const DashboardPage = lazy(() => import('./pages/DashboardPage'));
const BacktestPage = lazy(() => import('./pages/BacktestPage'));
const SettingsPage = lazy(() => import('./pages/SettingsPage'));
const LoginPage = lazy(() => import('./pages/LoginPage'));
const NotFoundPage = lazy(() => import('./pages/NotFoundPage'));
const ChatPage = lazy(() => import('./pages/ChatPage'));
const PortfolioPage = lazy(() => import('./pages/PortfolioPage'));
const DecisionSignalsPage = lazy(() => import('./pages/DecisionSignalsPage'));
const AlertsPage = lazy(() => import('./pages/AlertsPage'));
const TokenUsagePage = lazy(() => import('./pages/TokenUsagePage'));
const StockScreeningPage = lazy(() => import('./pages/StockScreeningPage'));
const StrategyCenterPage = lazy(() => import('./pages/StrategyCenterPage'));
const GameEnginePage = lazy(() => import('./pages/GameEnginePage'));
const ResearchPlatformPage = lazy(() => import('./pages/ResearchPlatformPage'));
const RiskPerformancePage = lazy(() => import('./pages/RiskPerformancePage'));
const FundFlowTopology = lazy(() => import('./pages/visuals/FundFlowTopology'));
const ParticipantGraph = lazy(() => import('./pages/visuals/ParticipantGraph'));
const GeoEventTopology = lazy(() => import('./pages/visuals/GeoEventTopology'));
const DimensionTree = lazy(() => import('./pages/visuals/DimensionTree'));
const IndustryChainTopology = lazy(() => import('./pages/visuals/IndustryChainTopology'));
const MultiConsensusPage = lazy(() => import('./pages/MultiConsensusPage'));
const LegacyHubPage = lazy(() => import('./pages/LegacyHubPage'));

const AppContent: React.FC = () => {
  const location = useLocation();
  const { authEnabled, loggedIn, isLoading, loadError, refreshStatus } = useAuth();
  const { t } = useUiLanguage();

  useEffect(() => {
    useAgentChatStore.getState().setCurrentRoute(location.pathname);
  }, [location.pathname]);

  if (isLoading) {
    return <PageLoadingFallback />;
  }

  if (loadError) {
    return (
      <div className="flex min-h-screen flex-col items-center justify-center gap-4 bg-base px-4">
        <div className="w-full max-w-lg">
          <ApiErrorAlert error={loadError} />
        </div>
        <button
          type="button"
          className="btn-primary"
          onClick={() => void refreshStatus()}
        >
          {t('common.retry')}
        </button>
      </div>
    );
  }

  if (authEnabled && !loggedIn) {
    if (location.pathname === '/login') {
      return (
        <StandaloneRouteBoundary>
          <LoginPage />
        </StandaloneRouteBoundary>
      );
    }
    const redirect = encodeURIComponent(location.pathname + location.search);
    return <Navigate to={`/login?redirect=${redirect}`} replace />;
  }

  if (location.pathname === '/login') {
    return <Navigate to="/" replace />;
  }

  return (
    <Routes>
        <Route element={<AdminLayout />}>
          <Route path="/dashboard" element={<DashboardPage />} />
          <Route path="/visuals/fund-flow" element={<FundFlowTopology />} />
          <Route path="/visuals/participant" element={<ParticipantGraph />} />
          <Route path="/visuals/geo-event" element={<GeoEventTopology />} />
          <Route path="/visuals/dimension-tree" element={<DimensionTree />} />
          <Route path="/visuals/industry-chain" element={<IndustryChainTopology />} />
          <Route path="/multi-consensus" element={<MultiConsensusPage />} />
          <Route path="/auto-strategy" element={<DashboardPage />} />
          <Route path="/old" element={<LegacyHubPage />} />
          <Route path="/strategy-center" element={<StrategyCenterPage />} />
          <Route path="/game-engine" element={<GameEnginePage />} />
          <Route path="/research-platform" element={<ResearchPlatformPage />} />
          <Route path="/risk-performance" element={<RiskPerformancePage />} />
        </Route>
        <Route
          element={(
            <Shell>
              <MainTabs />
              <RouteOutletBoundary />
            </Shell>
          )}
        >
        <Route path="/" element={<HomePage />} />
        <Route path="/chat" element={<ChatPage />} />
        <Route path="/portfolio" element={<PortfolioPage />} />
        <Route path="/decision-signals" element={<DecisionSignalsPage />} />
        <Route path="/screening" element={<StockScreeningPage />} />
        <Route path="/backtest" element={<BacktestPage />} />
        <Route path="/alerts" element={<AlertsPage />} />
        <Route path="/usage" element={<TokenUsagePage />} />
        <Route path="/settings" element={<SettingsPage />} />
        <Route path="*" element={<NotFoundPage />} />
      </Route>
    </Routes>
  );
};

const App: React.FC = () => {
  return (
    <UiLanguageProvider>
      <Router>
        <AuthProvider>
          <AppContent />
        </AuthProvider>
      </Router>
    </UiLanguageProvider>
  );
};

export default App;
