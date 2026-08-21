import { createBrowserRouter } from 'react-router-dom'
import DashboardShellLayout from '../pages/DashboardShellLayout'
import LoginPage from '../pages/LoginPage'
import DashboardSummaryPage from '../pages/DashboardSummaryPage'
import InsightsListPage from '../pages/InsightsListPage'
import InsightDetailPage from '../pages/InsightDetailPage'
import AnalysesPage from '../pages/AnalysesPage'
import OpsCostPage from '../pages/OpsCostPage'

export const router = createBrowserRouter([
  { path: '/login', element: <LoginPage /> },
  {
    path: '/',
    element: <DashboardShellLayout />,
    children: [
      { index: true, element: <DashboardSummaryPage /> },
      { path: 'dashboard', element: <DashboardSummaryPage /> },
      { path: 'insights', element: <InsightsListPage /> },
      { path: 'insights/:insightId', element: <InsightDetailPage /> },
      { path: 'analyses', element: <AnalysesPage /> },
      { path: 'ops/cost', element: <OpsCostPage /> },
    ],
  },
])
