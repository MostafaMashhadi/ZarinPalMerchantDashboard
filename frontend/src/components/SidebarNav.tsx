import React from 'react'
import { NavLink, useLocation } from 'react-router-dom'
import { AnalyticsIcon, ChevronDownIcon, DashboardIcon, InsightsIcon, StorefrontIcon, WalletIcon } from './ZarinpalIcons'
import {
  SidebarContent, SidebarFooter, SidebarGroup, SidebarGroupContent, SidebarGroupLabel,
  SidebarHeader, SidebarMenu, SidebarMenuBadge, SidebarMenuButton, SidebarMenuItem,
  SidebarSeparator, useSidebar,
} from '@/components/ui/sidebar'
import {
  DropdownMenu, DropdownMenuContent, DropdownMenuItem, DropdownMenuLabel,
  DropdownMenuSeparator, DropdownMenuTrigger,
} from '@/components/ui/dropdown-menu'
import { mockMerchants } from '@/services/mockData'
import { cn } from '@/lib/utils'
import NotificationBell from './NotificationBell'
import type { RootState, AppDispatch } from '@/store/store'
import { useSelector, useDispatch } from 'react-redux'
import { setSelectedMerchant } from '@/store/dashboardSlice'
import { resetInsights } from '@/store/insightsSlice'
import { resetAgent } from '@/store/agentSlice'
import ZarinpalLogo from './ZarinpalLogo'

interface NavItem {
  id: string
  label: string
  hint: string
  icon: React.ElementType
  path: string
}

const NAV_ITEMS: NavItem[] = [
  { id: 'overview', label: 'نمای کلی', hint: 'عملکرد پذیرنده و خلاصه هوشمند', icon: DashboardIcon, path: '/dashboard' },
  { id: 'insights', label: 'بینش‌ها', hint: 'فهرست بینش‌ها و ردیابی منشأ', icon: InsightsIcon, path: '/insights' },
  { id: 'analyses', label: 'موتور تحلیلی', hint: 'اجرای تحلیل‌های کلاسیک', icon: AnalyticsIcon, path: '/analyses' },
  { id: 'ops', label: 'هزینه‌ها', hint: 'داشبورد هزینه لحظه‌ای و تاریخی', icon: WalletIcon, path: '/ops/cost' },
]

const SidebarNav: React.FC = () => {
  const dispatch = useDispatch<AppDispatch>()
  const { isMobile, setOpenMobile } = useSidebar()
  const location = useLocation()
  const selectedMerchant = useSelector((state: RootState) => state.dashboard.selectedMerchant)
  const activeMerchant = mockMerchants.find((merchant) => merchant.id === selectedMerchant) ?? mockMerchants[0]
  const activeTab = Object.entries({
    '/dashboard': 'overview', '/insights': 'insights', '/analyses': 'analyses', '/ops/cost': 'ops',
  }).find(([path]) => location.pathname.startsWith(path))?.[1] ?? 'overview'

  const handleMerchantChange = (merchantId: string) => {
    dispatch(setSelectedMerchant(merchantId))
    dispatch(resetInsights())
    dispatch(resetAgent())
    if (isMobile) setOpenMobile(false)
  }

  const closeMobileSidebar = () => {
    if (isMobile) setOpenMobile(false)
  }

  const pageTitleMap: Record<string, string> = {
    overview: 'نمای کلی و مالی', insights: 'بینش‌ها و تحلیل‌های شما', analyses: 'موتور تحلیلی', ops: 'داشبورد هزینه‌ها (Ops)',
  }
  const subtitleMap: Record<string, string> = {
    overview: 'تحلیل عملکرد پرداخت و تصمیم‌سازی هوشمند',
    insights: 'فهرست بینش‌های تولیدشده با جزئیات و Provenance',
    analyses: 'اجرای تحلیل‌های کلاسیک با ردیابی کامل منشأ',
    ops: 'هزینه لحظه‌ای و تاریخی مصرف ایجنت هوشمند',
  }

  return (
    <>
      <SidebarHeader className="zarinpal-sidebar gap-3 p-3 group-data-[collapsible=icon]:items-center group-data-[collapsible=icon]:p-2">
        <div className="flex min-w-0 items-center gap-3 overflow-hidden rounded-xl bg-gradient-to-br from-zarin-navy to-zarin-navy-soft p-2 shadow-lg group-data-[collapsible=icon]:size-10 group-data-[collapsible=icon]:justify-center group-data-[collapsible=icon]:p-0">
            <ZarinpalLogo className="h-12 w-10 rounded-md bg-white p-1 shadow-sm ring-1 ring-white/20 group-data-[collapsible=icon]:size-10 group-data-[collapsible=icon]:p-1.5" />
            <div className="min-w-0 group-data-[collapsible=icon]:hidden">
              <span className="block truncate text-sm font-black tracking-tight text-white">زرین‌پال</span>
              <span className="block truncate text-[10px] font-medium text-white/70">پلتفرم هوشمند</span>
            </div>
        </div>
        <div className="px-1 group-data-[collapsible=icon]:hidden">
          <h2 className="text-sm font-black tracking-tight text-foreground">{pageTitleMap[activeTab] ?? 'داشبورد'}</h2>
          <p className="mt-0.5 truncate text-[11px] text-muted-foreground">{subtitleMap[activeTab] ?? ''}</p>
          <span className="mt-1 inline-flex items-center rounded-full bg-primary/10 px-2 py-0.5 text-[10px] font-black text-primary">{activeMerchant.category}</span>
        </div>
      </SidebarHeader>

      <SidebarSeparator />

      <SidebarContent className="zarinpal-sidebar">
        <SidebarGroup>
          <SidebarGroupLabel>فهرست اصلی</SidebarGroupLabel>
          <SidebarGroupContent>
            <nav aria-label="ناوبری اصلی">
              <SidebarMenu>
                {NAV_ITEMS.map((item) => {
                  const isActive = location.pathname === item.path || (item.path !== '/dashboard' && location.pathname.startsWith(item.path))
                  const Icon = item.icon
                  return (
                    <SidebarMenuItem key={item.id}>
                      <SidebarMenuButton asChild isActive={isActive} tooltip={{ children: item.label, side: 'left' }}>
                        <NavLink to={item.path} onClick={closeMobileSidebar}>
                          <Icon strokeWidth={isActive ? 2.5 : 2} />
                          <span className="font-bold">{item.label}</span>
                        </NavLink>
                      </SidebarMenuButton>
                      {isActive && <SidebarMenuBadge className="bg-primary/10 text-primary">•</SidebarMenuBadge>}
                    </SidebarMenuItem>
                  )
                })}
              </SidebarMenu>
            </nav>
          </SidebarGroupContent>
        </SidebarGroup>
      </SidebarContent>

      <SidebarFooter className="zarinpal-sidebar p-2 group-data-[collapsible=icon]:items-center">
        <div className="flex px-1 group-data-[collapsible=icon]:px-0"><NotificationBell /></div>
        <DropdownMenu>
          <DropdownMenuTrigger asChild>
            <button type="button" className="group flex w-full items-center gap-2.5 rounded-xl border border-sidebar-border/80 bg-white/60 p-2 text-start shadow-sm backdrop-blur-sm transition-all duration-200 hover:border-sidebar-border hover:bg-white hover:shadow-md focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring/40 group-data-[collapsible=icon]:size-9 group-data-[collapsible=icon]:justify-center group-data-[collapsible=icon]:p-0">
              <span className="flex size-8 shrink-0 items-center justify-center rounded-lg text-xs font-black text-white shadow-sm" style={{ background: 'linear-gradient(135deg, #36B37E 0%, #0D1B4B 100%)' }}>{activeMerchant.name.charAt(0)}</span>
              <span className="min-w-0 flex-1 group-data-[collapsible=icon]:hidden">
                <span className="block text-[10px] font-bold leading-tight text-muted-foreground">پذیرنده فعال</span>
                <span className="block max-w-36 truncate text-xs font-extrabold leading-tight text-foreground">{activeMerchant.name}</span>
              </span>
              <ChevronDownIcon className="size-4 shrink-0 text-muted-foreground/70 transition-transform duration-200 group-data-open:rotate-180 group-data-[collapsible=icon]:hidden" />
            </button>
          </DropdownMenuTrigger>
          <DropdownMenuContent align="end" sideOffset={8} className="zarinpal-sidebar-popover w-80 rounded-2xl border-border/60 p-1.5 shadow-xl">
            <DropdownMenuLabel className="flex items-center justify-between px-2 py-1.5 text-xs font-bold text-muted-foreground">
              <span className="flex items-center gap-1.5"><StorefrontIcon className="size-4" />تغییر پذیرنده</span>
              <span className="rounded-full bg-primary/10 px-2 py-0.5 text-[10px] font-black text-primary">{mockMerchants.length} پذیرنده</span>
            </DropdownMenuLabel>
            <DropdownMenuSeparator className="my-1" />
            {mockMerchants.map((merchant) => {
              const isActive = merchant.id === activeMerchant.id
              return (
                <DropdownMenuItem key={merchant.id} onClick={() => handleMerchantChange(merchant.id)} className={cn('flex cursor-pointer items-center gap-3 rounded-xl px-2 py-2.5 transition-all duration-150', isActive ? 'bg-primary/8 text-primary' : 'hover:bg-muted/60')}>
                  <span className={cn('flex size-9 shrink-0 items-center justify-center rounded-xl text-sm font-black', isActive ? 'text-white shadow-sm shadow-primary/20' : 'bg-muted text-muted-foreground')} style={isActive ? { background: 'linear-gradient(135deg, #36B37E 0%, #0D1B4B 100%)' } : {}}>{merchant.name.charAt(0)}</span>
                  <span className="min-w-0 flex-1"><span className="block truncate text-sm font-bold">{merchant.name}</span><span className="block truncate text-xs text-muted-foreground">{merchant.id} · {merchant.category}</span></span>
                  {isActive && <span className="size-4 shrink-0 text-primary">✓</span>}
                </DropdownMenuItem>
              )
            })}
          </DropdownMenuContent>
        </DropdownMenu>
      </SidebarFooter>
    </>
  )
}

export default SidebarNav
