import { Outlet, Navigate, useLocation } from 'react-router-dom'
import { useSelector } from 'react-redux'
import type { RootState } from '../store/store'
import Header from '../components/Header'
import DashboardSidebar from '../components/DashboardSidebar'
import { useEffect } from 'react'
import { useDispatch } from 'react-redux'
import type { AppDispatch } from '../store/store'
import { fetchDashboardSummary, setSelectedMerchant, setActiveTab } from '../store/dashboardSlice'
import { resetInsights } from '../store/insightsSlice'
import { resetAgent } from '../store/agentSlice'
import { setDataFreshness } from '../store/uiSlice'
import DegradedDataBadge from '../components/DegradedDataBadge'
import {
  SidebarProvider,
  SidebarInset,
  SidebarTrigger,
} from '@/components/ui/sidebar'

const ROUTE_TO_TAB: Record<string, string> = {
  '/dashboard': 'overview',
  '/insights': 'insights',
  '/analyses': 'analyses',
  '/ops/cost': 'ops',
}

const DashboardShellLayout: React.FC = () => {
  const dispatch = useDispatch<AppDispatch>()
  const location = useLocation()
  const isAuthenticated = useSelector((state: RootState) => state.auth.isAuthenticated)
  const { selectedMerchant, activeTab, degraded } = useSelector((state: RootState) => state.dashboard)
  const dataFreshness = useSelector((state: RootState) => state.ui.dataFreshness)

  useEffect(() => {
    const derived = ROUTE_TO_TAB[location.pathname]
    if (derived && derived !== activeTab) {
      dispatch(setActiveTab(derived))
    }
  }, [location.pathname, activeTab, dispatch])

  useEffect(() => {
    const authHandler = () => dispatch(setActiveTab('overview'))
    const degradedHandler = () => dispatch(setDataFreshness('cached_fallback'))
    window.addEventListener('auth:logout', authHandler)
    window.addEventListener('ui:data-degraded', degradedHandler)
    return () => {
      window.removeEventListener('auth:logout', authHandler)
      window.removeEventListener('ui:data-degraded', degradedHandler)
    }
  }, [dispatch])

  useEffect(() => {
    if (isAuthenticated) {
      dispatch(fetchDashboardSummary(selectedMerchant))
    }
  }, [dispatch, isAuthenticated, selectedMerchant])

  if (!isAuthenticated) {
    return <Navigate to="/login" replace />
  }

  const handleMerchantChange = (merchantId: string) => {
    dispatch(setSelectedMerchant(merchantId))
    dispatch(resetInsights())
    dispatch(resetAgent())
  }

  return (
    <SidebarProvider defaultOpen>
      <div className="flex min-h-dvh w-full bg-background text-foreground" dir="rtl">
        <DashboardSidebar />
        <SidebarInset className="flex flex-col">
          <div className="sticky top-0 z-30 border-b border-border/50 bg-white/72 shadow-sm backdrop-blur-2xl">
            <div className="flex items-center gap-3 px-4 py-3 lg:px-6">
              <SidebarTrigger className="size-8" />
              <Header
                pageTitle={
                  activeTab === 'overview'
                    ? 'نمای کلی و مالی'
                    : activeTab === 'insights'
                      ? 'بینش‌ها و تحلیل‌های شما'
                      : activeTab === 'analyses'
                        ? 'موتور تحلیلی'
                        : 'داشبورد هزینه‌ها (Ops)'
                }
                subtitle={
                  activeTab === 'overview'
                    ? 'تحلیل عملکرد پرداخت و تصمیم‌سازی هوشمند'
                    : activeTab === 'insights'
                      ? 'فهرست بینش‌های تولیدشده با جزئیات و Provenance'
                      : activeTab === 'analyses'
                        ? 'اجرای تحلیل‌های کلاسیک با ردیابی کامل منشأ'
                        : 'هزینه لحظه‌ای و تاریخی مصرف ایجنت هوشمند'
                }
                selectedMerchant={selectedMerchant}
                onMerchantChange={handleMerchantChange}
              />
            </div>
          </div>

          <main className="relative flex-1 overflow-auto">
            <div className="relative mx-auto w-full max-w-7xl px-4 py-6 lg:px-8 lg:py-8">
              {(degraded || dataFreshness === 'cached_fallback') && <DegradedDataBadge />}
              <Outlet />
            </div>
          </main>
        </SidebarInset>
      </div>
    </SidebarProvider>
  )
}

export default DashboardShellLayout