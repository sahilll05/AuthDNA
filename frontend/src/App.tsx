// src/App.tsx
import { BrowserRouter as Router, Routes, Route, Navigate } from "react-router-dom";
import { AuthProvider } from "@/context/AuthContext";
import { Toaster } from "@/components/ui/sonner";
import ProtectedRoute from "@/components/ProtectedRoute";

// Layouts
import PublicLayout from "@/components/layouts/PublicLayout";
import AppLayout from "@/components/layouts/AppLayout";

// Public pages (YOUR EXISTING PAGES)
import LandingPage from "@/pages/LandingPage";
import FeaturesPage from "@/pages/FeaturesPage";
import PricingPage from "@/pages/PricingPage";
import DocsPage from "@/pages/DocsPage";
import LoginPage from "@/pages/LoginPage";
import RegisterPage from "@/pages/RegisterPage";
import StatusPage from "@/pages/StatusPage";
import AboutPage from "@/pages/AboutPage";
import ContactPage from "@/pages/ContactPage";
import NotFound from "@/pages/NotFound";

// App pages (NEW dashboard pages)
import DashboardPage from "@/pages/app/DashboardPage";
import ThreatsPage from "@/pages/app/ThreatsPage";
import LogsPage from "@/pages/app/LogsPage";
import UsersPage from "@/pages/app/UsersPage";
import UserDetailPage from "@/pages/app/UserDetailPage";
import ApiKeysPage from "@/pages/app/ApiKeysPage";
import WebhooksPage from "@/pages/app/WebhooksPage";
import UsagePage from "@/pages/app/UsagePage";
import SettingsPage from "@/pages/app/SettingsPage";
import PlaygroundPage from "@/pages/app/PlaygroundPage";
import AdminSecurityDashboard from "@/pages/app/AdminSecurityDashboard";

import { RealtimeLogsProvider } from "@/context/RealtimeLogsContext";

function App() {
  return (
    <AuthProvider>
      <RealtimeLogsProvider>
        <Router>
          <Routes>
            {/* ══════════════════════════════════════════════
                PUBLIC ROUTES — with YOUR Navbar + Footer
                ══════════════════════════════════════════════ */}
            <Route element={<PublicLayout />}>
              <Route path="/" element={<LandingPage />} />
              <Route path="/features" element={<FeaturesPage />} />
              <Route path="/pricing" element={<PricingPage />} />
              <Route path="/docs" element={<DocsPage />} />
              <Route path="/about" element={<AboutPage />} />
              <Route path="/contact" element={<ContactPage />} />
              <Route path="/status" element={<StatusPage />} />
              <Route path="/login" element={<LoginPage />} />
              <Route path="/register" element={<RegisterPage />} />
            </Route>

            {/* ══════════════════════════════════════════════
                PROTECTED APP ROUTES — with Sidebar layout
                ══════════════════════════════════════════════ */}
            <Route
              path="/app"
              element={
                <ProtectedRoute>
                  <AppLayout />
                </ProtectedRoute>
              }
            >
              <Route index element={<Navigate to="/app/dashboard" replace />} />
              <Route path="dashboard" element={<DashboardPage />} />
              <Route path="live-radar" element={<AdminSecurityDashboard />} />
              <Route path="threats" element={<ThreatsPage />} />
              <Route path="logs" element={<LogsPage />} />
              <Route path="users" element={<UsersPage />} />
              <Route path="users/:userId" element={<UserDetailPage />} />
              <Route path="api-keys" element={<ApiKeysPage />} />
              <Route path="webhooks" element={<WebhooksPage />} />
              <Route path="usage" element={<UsagePage />} />
              <Route path="settings" element={<SettingsPage />} />
              <Route path="playground" element={<PlaygroundPage />} />
            </Route>

            {/* ══════════════════════════════════════════════
                404
                ══════════════════════════════════════════════ */}
            <Route path="*" element={<NotFound />} />
          </Routes>
        </Router>
        <Toaster richColors position="top-right" />
      </RealtimeLogsProvider>
    </AuthProvider>
  );
}

export default App;