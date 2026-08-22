import { Outlet, Navigate, useNavigate, useLocation } from 'react-router-dom'
import { useSelector, useDispatch } from 'react-redux'
import type { RootState, AppDispatch } from '../store/store'
import { fetchDashboardSummary, setActiveTab } from '../store/dashboardSlice'
import { setDataFreshness } from '../store/uiSlice'
import { useEffect, useState } from 'react'
import DegradedDataBadge from '../components/DegradedDataBadge'
import SidebarNav from '../components/SidebarNav'
import {
  SidebarProvider,
  Sidebar,
  SidebarInset,
  SidebarTrigger,
} from '@/components/ui/sidebar'
import { Button } from '@/components/ui/button'
import { LogOut, MessageCircle, Sparkles } from 'lucide-react'
import ChatPanel from '../components/ChatPanel'
import SidebarToggleIcon from '../components/SidebarToggleIcon'
import ZarinpalLogo from '../components/ZarinpalLogo'
import { logout } from '../store/authSlice'
const DashboardShellLayout: React.FC = () => {
  const dispatch = useDispatch<AppDispatch>()
  const navigate = useNavigate()
  const location = useLocation()
  const isAuthenticated = useSelector((state: RootState) => state.auth.isAuthenticated)
  const { selectedMerchant, activeTab, degraded } = useSelector((state: RootState) => state.dashboard)
  const dataFreshness = useSelector((state: RootState) => state.ui.dataFreshness)
  const [chatOpen, setChatOpen] = useState(false)

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
      <div className="app-backdrop flex min-h-dvh w-full overflow-x-clip text-foreground" dir="rtl">
        {/* ── Sidebar ── */}
        <Sidebar side="right" variant="sidebar" collapsible="icon" className="border-s border-sidebar-border">
          <SidebarNav />
        </Sidebar>

        {/* ── Main Content ── */}
        <SidebarInset className="min-w-0 bg-transparent">
          <header className="dashboard-header sticky top-0 z-20 flex min-h-16 items-center justify-between gap-3 border-b border-border/70 px-3 py-2 sm:px-4 lg:px-8" dir="rtl">
            <div className="flex min-w-0 items-center gap-2 sm:gap-3">
              <SidebarTrigger
                aria-label="باز یا بستن منو"
                title="باز یا بستن منو (Ctrl+B)"
                className="size-11 shrink-0 rounded-xl border border-border/80 bg-white/70 text-foreground shadow-sm hover:bg-sidebar-accent hover:text-sidebar-accent-foreground"
              >
                <SidebarToggleIcon className="size-5" />
              </SidebarTrigger>
              <div className="min-w-0">
              <p className="text-xs text-muted-foreground">زرین‌پال من · {selectedMerchant}</p>
              <h1 className="truncate text-base font-bold">سلام، خوش آمدید</h1>
              </div>
            </div>
            <div className="flex shrink-0 items-center gap-2 text-xs text-muted-foreground">
              <span className="hidden rounded-full bg-primary/10 px-3 py-1.5 font-semibold text-primary sm:inline">حساب فعال</span>
              <span className="size-2 rounded-full bg-primary" aria-label="سرویس فعال" />
              <Button
                type="button"
                variant="outline"
                aria-label="خروج از حساب"
                title="خروج از حساب"
                onClick={() => void dispatch(logout())}
                className="h-10 rounded-xl border-destructive/20 bg-white/70 px-2.5 text-destructive shadow-sm hover:bg-destructive/5 hover:text-destructive sm:gap-2 sm:px-3"
              >
                <LogOut className="size-4" aria-hidden="true" />
                <span className="hidden font-bold sm:inline">خروج</span>
              </Button>
            </div>
          </header>
          <main className="relative mx-auto flex w-full min-w-0 flex-1 flex-col gap-6 px-3 py-6 sm:px-4 sm:py-7 lg:gap-7 lg:px-8 lg:py-9">
            {(degraded || dataFreshness === 'cached_fallback') && <DegradedDataBadge />}
            <Outlet />
          </main>

          <footer className="relative border-t border-border/50 bg-white/65 px-3 py-4 backdrop-blur-sm sm:px-4" dir="rtl">
            <div className="mx-auto flex max-w-7xl flex-col items-center justify-between gap-3 text-center sm:flex-row sm:text-start">
              <div className="flex items-center gap-2 text-xs text-muted-foreground">
                <span className="hidden sm:inline text-muted-foreground/55">
                  آخرین بروزرسانی: {new Date().toLocaleTimeString('fa-IR')}
                </span>
              </div>
              <div className="flex items-center gap-2 text-xs text-muted-foreground/50">
                <ZarinpalLogo className="h-8 w-6 rounded-sm bg-white p-0.5" />
                زرین‌پال · پلتفرم هوشمند تحلیل پرداخت
              </div>
            </div>
          </footer>
          <Button
            type="button"
            size="lg"
            onClick={() => setChatOpen(true)}
            aria-label="باز کردن گفتگوی دستیار هوشمند"
            aria-expanded={chatOpen}
            className="fixed bottom-5 left-5 z-30 h-14 rounded-full bg-[#1f3b2d] px-4 text-white shadow-[0_12px_28px_rgba(31,59,45,0.25)] hover:bg-[#163324] sm:bottom-7 sm:left-7"
          >
            <span className="relative flex size-8 items-center justify-center rounded-full bg-[#ffd700] text-[#1f3b2d]">
              <MessageCircle aria-hidden="true" />
              <Sparkles className="absolute -right-1 -top-1 size-3 text-[#ffd700]" fill="currentColor" aria-hidden="true" />
            </span>
            <span className="hidden font-bold sm:inline">دستیار هوشمند</span>
          </Button>
          <ChatPanel open={chatOpen} onOpenChange={setChatOpen} merchantRef={selectedMerchant} />
        </SidebarInset>
      </div>
    </SidebarProvider>
  )
}

export default DashboardShellLayout
