import { BrowserRouter, Navigate, Route, Routes } from "react-router-dom";
import { MarketProvider } from "./market/MarketContext";
import { AdminPage } from "./pages/AdminPage";
import { DashboardPage } from "./pages/DashboardPage";

export default function App() {
  return (
    <MarketProvider>
      <BrowserRouter>
        <Routes>
          <Route path="/" element={<DashboardPage />} />
          <Route path="/admin" element={<AdminPage />} />
          <Route path="*" element={<Navigate to="/" replace />} />
        </Routes>
      </BrowserRouter>
    </MarketProvider>
  );
}
