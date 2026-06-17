import { BrowserRouter, Navigate, Route, Routes } from "react-router-dom";
import { MarketProvider } from "./market/MarketContext";
import { AdminPage } from "./pages/AdminPage";
import { CycleStrategyPage } from "./pages/CycleStrategyPage";
import { DashboardPage } from "./pages/DashboardPage";
import { VolumeStrategyPage } from "./pages/VolumeStrategyPage";

export default function App() {
  return (
    <MarketProvider>
      <BrowserRouter>
        <Routes>
          <Route path="/" element={<DashboardPage />} />
          <Route path="/volume-strategy" element={<VolumeStrategyPage />} />
          <Route path="/cycle-strategy" element={<CycleStrategyPage />} />
          <Route path="/admin" element={<AdminPage />} />
          <Route path="*" element={<Navigate to="/" replace />} />
        </Routes>
      </BrowserRouter>
    </MarketProvider>
  );
}
