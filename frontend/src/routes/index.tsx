import { useRoutes, Navigate, useLocation } from "react-router-dom";
import type { ReactNode } from "react";
import MainLayout from "../layouts/MainLayout";
import { useAuth } from "../contexts/AuthContext";
import DashboardPage from "../pages/dashboard/DashboardPage";
import OverviewPage from "../pages/overview/OverviewPage";
import HistoryPage from "../pages/history/HistoryPage";
import CaseExecutionsHistoryPage from "../pages/history/CaseExecutionsHistoryPage";
import CasesPage from "../pages/cases/CasesPage";
import ReportPage from "../pages/report/ReportPage";
import UsersPage from "../pages/admin/UsersPage";
import ModulesPage from "../pages/admin/ModulesPage";
import FailedTypesPage from "../pages/admin/FailedTypesPage";
import OfflineTypesPage from "../pages/admin/OfflineTypesPage";
import NotificationPage from "../pages/admin/NotificationPage";
import LoginPage from "../pages/auth/LoginPage";

function RequireAuth({ children }: { children: ReactNode }) {
  const token = localStorage.getItem("token");
  const location = useLocation();
  if (!token) {
    const redirect = encodeURIComponent(`${location.pathname}${location.search}`);
    return <Navigate to={`/login?redirect=${redirect}`} replace />;
  }
  return <>{children}</>;
}

function RequireAdmin({ children }: { children: ReactNode }) {
  const user = useAuth();
  if (!user || user.role !== "admin") {
    return <Navigate to="/" replace />;
  }
  return <>{children}</>;
}

export default function AppRoutes() {
  return useRoutes([
    {
      path: "/login",
      element: <LoginPage />,
    },
    {
      path: "/",
      element: (
        <RequireAuth>
          <MainLayout />
        </RequireAuth>
      ),
      children: [
        { index: true, element: <DashboardPage /> },
        { path: "overview", element: <OverviewPage /> },
        { path: "history", element: <HistoryPage /> },
        { path: "history/case-executions", element: <CaseExecutionsHistoryPage /> },
        {
          path: "cases",
          element: (
            <RequireAdmin>
              <CasesPage />
            </RequireAdmin>
          ),
        },
        {
          path: "report/:id?",
          element: (
            <RequireAdmin>
              <ReportPage />
            </RequireAdmin>
          ),
        },
        {
          path: "admin/users",
          element: (
            <RequireAdmin>
              <UsersPage />
            </RequireAdmin>
          ),
        },
        {
          path: "admin/modules",
          element: (
            <RequireAdmin>
              <ModulesPage />
            </RequireAdmin>
          ),
        },
        {
          path: "admin/dict/failed-types",
          element: (
            <RequireAdmin>
              <FailedTypesPage />
            </RequireAdmin>
          ),
        },
        {
          path: "admin/dict/offline-types",
          element: (
            <RequireAdmin>
              <OfflineTypesPage />
            </RequireAdmin>
          ),
        },
        {
          path: "admin/notification",
          element: (
            <RequireAdmin>
              <NotificationPage />
            </RequireAdmin>
          ),
        },
      ],
    },
    { path: "*", element: <Navigate to="/" replace /> },
  ]);
}
