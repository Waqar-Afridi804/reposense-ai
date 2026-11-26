import { lazy, Suspense } from "react";
import { BrowserRouter, Navigate, Route, Routes } from "react-router-dom";
import Layout from "./components/Layout";
import { LoadingSpinner } from "./components/StatusAlert";
import { AuthProvider, useAuth } from "./context/AuthContext";
import { RepoProvider } from "./context/RepoContext";
import LandingPage from "./pages/LandingPage";
import LoginPage from "./pages/LoginPage";

const AuthCallbackPage = lazy(() => import("./pages/AuthCallbackPage"));
const DashboardPage = lazy(() => import("./pages/DashboardPage"));
const AnalysisReportPage = lazy(() => import("./pages/AnalysisReportPage"));
const FileExplorerPage = lazy(() => import("./pages/FileExplorerPage"));
const DependencyGraphPage = lazy(() => import("./pages/DependencyGraphPage"));
const SemanticSearchPage = lazy(() => import("./pages/SemanticSearchPage"));
const AiAssistantPage = lazy(() => import("./pages/AiAssistantPage"));

function ProtectedLayout({ children }) {
  const { isAuthenticated, loading } = useAuth();

  if (loading) {
    return (
      <div className="flex min-h-screen items-center justify-center bg-[#09090b]">
        <LoadingSpinner label="Verifying session..." />
      </div>
    );
  }

  if (!isAuthenticated) {
    return <Navigate to="/login" replace />;
  }

  return <Layout>{children}</Layout>;
}

export default function App() {
  return (
    <BrowserRouter>
      <AuthProvider>
        <RepoProvider>
          <Suspense
            fallback={
              <div className="flex min-h-screen items-center justify-center bg-[#09090b]">
                <LoadingSpinner label="Loading view..." />
              </div>
            }
          >
            <Routes>
              <Route path="/login" element={<LoginPage />} />
              <Route path="/auth/callback" element={<AuthCallbackPage />} />
              <Route
                path="/"
                element={
                  <ProtectedLayout>
                    <LandingPage />
                  </ProtectedLayout>
                }
              />
              <Route
                path="/dashboard"
                element={
                  <ProtectedLayout>
                    <DashboardPage />
                  </ProtectedLayout>
                }
              />
              <Route
                path="/report"
                element={
                  <ProtectedLayout>
                    <AnalysisReportPage />
                  </ProtectedLayout>
                }
              />
              <Route
                path="/explorer"
                element={
                  <ProtectedLayout>
                    <FileExplorerPage />
                  </ProtectedLayout>
                }
              />
              <Route
                path="/dependencies"
                element={
                  <ProtectedLayout>
                    <DependencyGraphPage />
                  </ProtectedLayout>
                }
              />
              <Route
                path="/search"
                element={
                  <ProtectedLayout>
                    <SemanticSearchPage />
                  </ProtectedLayout>
                }
              />
              <Route
                path="/assistant"
                element={
                  <ProtectedLayout>
                    <AiAssistantPage />
                  </ProtectedLayout>
                }
              />
              <Route path="*" element={<Navigate to="/" replace />} />
            </Routes>
          </Suspense>
        </RepoProvider>
      </AuthProvider>
    </BrowserRouter>
  );
}
