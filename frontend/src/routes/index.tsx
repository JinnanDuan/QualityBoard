import { useRoutes, Navigate } from "react-router-dom";
import MainLayout from "../layouts/MainLayout";
import DashboardPage from "../pages/dashboard/DashboardPage";
import OverviewPage from "../pages/overview/OverviewPage";
import HistoryPage from "../pages/history/HistoryPage";
import CasesPage from "../pages/cases/CasesPage";
import ReportPage from "../pages/report/ReportPage";
import UsersPage from "../pages/admin/UsersPage";
import ModulesPage from "../pages/admin/ModulesPage";
import FailedTypesPage from "../pages/admin/FailedTypesPage";
import OfflineTypesPage from "../pages/admin/OfflineTypesPage";
import NotificationPage from "../pages/admin/NotificationPage";
import LoginPage from "../pages/auth/LoginPage";

export default function AppRoutes() {
  return useRoutes([
    {
      path: "/login",
      element: <LoginPage />,
    },
    {
      path: "/",
      element: <MainLayout />,
      children: [
        { index: true, element: <DashboardPage /> },
        { path: "overview", element: <OverviewPage /> },
        { path: "history", element: <HistoryPage /> },
        { path: "cases", element: <CasesPage /> },
        { path: "report/:id?", element: <ReportPage /> },
        { path: "admin/users", element: <UsersPage /> },
        { path: "admin/modules", element: <ModulesPage /> },
        { path: "admin/dict/failed-types", element: <FailedTypesPage /> },
        { path: "admin/dict/offline-types", element: <OfflineTypesPage /> },
        { path: "admin/notification", element: <NotificationPage /> },
      ],
    },
    { path: "*", element: <Navigate to="/" replace /> },
  ]);
}
