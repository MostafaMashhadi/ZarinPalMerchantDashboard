import { createBrowserRouter } from 'react-router-dom'
import DashboardShellLayout from '../pages/DashboardShellLayout'
import LoginPage from '../pages/LoginPage'
import DashboardSummaryPage from '../pages/DashboardSummaryPage'
import InsightsListPage from '../pages/InsightsListPage'
import InsightDetailPage from '../pages/InsightDetailPage'
import AnalysesPage from '../pages/AnalysesPage'
import OpsCostPage from '../pages/OpsCostPage'
import HomePage from '../pages/HomePage'

export const router = createBrowserRouter([
  { path: '/', element: <HomePage /> },
  { path: '/login', element: <LoginPage /> },
  {
    path: '/dashboard',
    element: <DashboardShellLayout />,
    children: [
      { index: true, element: <DashboardSummaryPage /> },
    ],
  },
  {
    path: '/',
    element: <DashboardShellLayout />,
    children: [
      { path: 'insights', element: <InsightsListPage /> },
      { path: 'insights/:insightId', element: <InsightDetailPage /> },
      { path: 'analyses', element: <AnalysesPage /> },
      { path: 'ops/cost', element: <OpsCostPage /> },
    ],
  },
])
