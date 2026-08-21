import { Outlet, Navigate, useNavigate, useLocation } from 'react-router-dom'
import { useSelector, useDispatch } from 'react-redux'
import type { RootState, AppDispatch } from '../store/store'
import { fetchDashboardSummary, setActiveTab } from '../store/dashboardSlice'
import { setDataFreshness } from '../store/uiSlice'
import { useEffect } from 'react'
import DegradedDataBadge from '../components/DegradedDataBadge'
import SidebarNav from '../components/SidebarNav'
import {
  SidebarProvider,
  Sidebar,
  SidebarInset,
} from '@/components/ui/sidebar'
import { Button } from '@/components/ui/button'
import { MessageSquareDashed } from 'lucide-react'

const DashboardShellLayout: React.FC = () => {
  const dispatch = useDispatch<AppDispatch>()
  const navigate = useNavigate()
  const location = useLocation()
  const isAuthenticated = useSelector((state: RootState) => state.auth.isAuthenticated)
  const { selectedMerchant, activeTab, degraded } = useSelector((state: RootState) => state.dashboard)
  const dataFreshness = useSelector((state: RootState) => state.ui.dataFreshness)

  useEffect(() => {
    const derived = ({ '/dashboard': 'overview', '/insights': 'insights', '/analyses': 'analyses', '/ops/cost': 'ops' } as Record<string, string>)[location.pathname]
    if (derived && derived !== activeTab) {
      dispatch(setActiveTab(derived))
    }
  }, [location.pathname, activeTab, dispatch])

  useEffect(() => {
    const authHandler = () => navigate('/login', { replace: true })
    const degradedHandler = () => dispatch(setDataFreshness('cached_fallback'))
    window.addEventListener('auth:logout', authHandler)
    window.addEventListener('ui:data-degraded', degradedHandler)
    return () => {
      window.removeEventListener('auth:logout', authHandler)
      window.removeEventListener('ui:data-degraded', degradedHandler)
    }
  }, [navigate, dispatch])

  useEffect(() => {
    if (isAuthenticated) {
      dispatch(fetchDashboardSummary(selectedMerchant))
    }
  }, [dispatch, isAuthenticated, selectedMerchant])

  if (!isAuthenticated) {
    return <Navigate to="/login" replace />
  }

  return (
    <SidebarProvider defaultOpen={true}>
      <div className="flex min-h-dvh w-full bg-background text-foreground" dir="rtl">
        {/* ── Sidebar ── */}
        <Sidebar side="right" variant="floating" collapsible="icon" className="border-e border-sidebar-border">
          <SidebarNav />
        </Sidebar>

        {/* ── Main Content ── */}
        <SidebarInset className="bg-transparent">
          <header className="flex items-center justify-between gap-4 border-b border-border/70 px-4 py-3 lg:px-8" dir="rtl">
            <div className="min-w-0">
              <p className="text-xs text-muted-foreground">{selectedMerchant}</p>
              <h1 className="truncate text-base font-semibold">Dashboard</h1>
            </div>
            <Button variant="outline" size="sm" disabled aria-label="گفتگوی هوشمند در اسپرینت ۳ فعال می‌شود">
              <MessageSquareDashed data-icon="inline-start" aria-hidden="true" />
              گفتگوی هوشمند
            </Button>
          </header>
          <main className="relative mx-auto w-full flex-1 space-y-6 px-4 py-7 lg:space-y-7 lg:px-8 lg:py-9">
            {(degraded || dataFreshness === 'cached_fallback') && <DegradedDataBadge />}
            <Outlet />
          </main>

          <footer className="relative border-t border-border/50 bg-white/65 px-4 py-4 backdrop-blur-sm" dir="rtl">
            <div className="mx-auto flex max-w-7xl flex-col items-center justify-between gap-3 sm:flex-row">
              <div className="flex items-center gap-2 text-xs text-muted-foreground">
                <span className="hidden sm:inline text-muted-foreground/55">
                  آخرین بروزرسانی: {new Date().toLocaleTimeString('fa-IR')}
                </span>
              </div>
              <div className="flex items-center gap-2 text-xs text-muted-foreground/50">
                <div className="size-5 rounded-md logo-zarin flex items-center justify-center">
                  <span className="text-[9px] font-black text-white">Z</span>
                </div>
                زرین‌پال · پلتفرم هوشمند تحلیل پرداخت
              </div>
            </div>
          </footer>
        </SidebarInset>
      </div>
    </SidebarProvider>
  )
}

export default DashboardShellLayout
