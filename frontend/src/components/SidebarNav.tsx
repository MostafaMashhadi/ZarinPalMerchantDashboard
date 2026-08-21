"use client"

import React from 'react'
import { NavLink, useLocation } from 'react-router-dom'
import {
  BarChart3,
  Lightbulb,
  FlaskConical,
  Receipt,
  Store,
  ChevronsUpDown,
} from 'lucide-react'
import SidebarToggleIcon from './SidebarToggleIcon'
import { useSidebar } from '@/components/ui/sidebar'
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuLabel,
  DropdownMenuSeparator,
  DropdownMenuTrigger,
} from '@/components/ui/dropdown-menu'
import { Tooltip, TooltipContent, TooltipTrigger } from '@/components/ui/tooltip'
import { mockMerchants } from '@/services/mockData'
import { cn } from '@/lib/utils'
import NotificationBell from './NotificationBell'
import type { RootState, AppDispatch } from '@/store/store'
import { useSelector, useDispatch } from 'react-redux'
import { setSelectedMerchant } from '@/store/dashboardSlice'
import { resetInsights } from '@/store/insightsSlice'
import { resetAgent } from '@/store/agentSlice'

interface NavItem {
  id: string
  label: string
  hint: string
  icon: React.ElementType
  path: string
}

const NAV_ITEMS: NavItem[] = [
  {
    id: 'overview',
    label: 'نمای کلی',
    hint: 'عملکرد پذیرنده و خلاصه هوشمند',
    icon: BarChart3,
    path: '/dashboard',
  },
  {
    id: 'insights',
    label: 'بینش‌ها',
    hint: 'فهرست بینش‌ها و ردیابی منشأ',
    icon: Lightbulb,
    path: '/insights',
  },
  {
    id: 'analyses',
    label: 'موتور تحلیلی',
    hint: 'اجرای تحلیل‌های کلاسیک',
    icon: FlaskConical,
    path: '/analyses',
  },
  {
    id: 'ops',
    label: 'هزینه‌ها',
    hint: 'داشبورد هزینه لحظه‌ای و تاریخی',
    icon: Receipt,
    path: '/ops/cost',
  },
]

const SidebarNav: React.FC = () => {
  const dispatch = useDispatch<AppDispatch>()
  const { state, toggleSidebar } = useSidebar()
  const location = useLocation()
  const selectedMerchant = useSelector((state: RootState) => state.dashboard.selectedMerchant)
  const activeMerchant = mockMerchants.find((m) => m.id === selectedMerchant) ?? mockMerchants[0]
  const isCollapsed = state === 'collapsed'

  const activeTab = Object.entries({
    '/dashboard': 'overview',
    '/insights': 'insights',
    '/analyses': 'analyses',
    '/ops/cost': 'ops',
  }).find(([path]) => location.pathname.startsWith(path))?.[1] ?? 'overview'

  const handleMerchantChange = (merchantId: string) => {
    dispatch(setSelectedMerchant(merchantId))
    dispatch(resetInsights())
    dispatch(resetAgent())
  }

  const pageTitleMap: Record<string, string> = {
    overview: 'نمای کلی و مالی',
    insights: 'بینش‌ها و تحلیل‌های شما',
    analyses: 'موتور تحلیلی',
    ops: 'داشبورد هزینه‌ها (Ops)',
  }

  const subtitleMap: Record<string, string> = {
    overview: 'تحلیل عملکرد پرداخت و تصمیم‌سازی هوشمند',
    insights: 'فهرست بینش‌های تولیدشده با جزئیات و Provenance',
    analyses: 'اجرای تحلیل‌های کلاسیک با ردیابی کامل منشأ',
    ops: 'هزینه لحظه‌ای و تاریخی مصرف ایجنت هوشمند',
  }

  return (
    <>
      {/* ── Header ── */}
      <div data-slot="sidebar-header" data-sidebar="header" className="relative isolate min-h-11 p-3">
        {/* Toggle — anchored to the corner, always visible, never shifts on state change */}
        <button
          type="button"
          onClick={toggleSidebar}
          aria-label={isCollapsed ? 'باز کردن منو' : 'بستن منو'}
          aria-expanded={!isCollapsed}
          className="absolute end-3 top-3 z-20 flex size-8 items-center justify-center rounded-lg bg-white/10 text-white shadow-sm ring-1 ring-white/20 backdrop-blur transition-colors hover:bg-white/20 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-white/50"
        >
          <SidebarToggleIcon open={!isCollapsed} className="text-base" />
        </button>

        {/* Brand (expanded only — avoids overflow in icon mode) */}
        {!isCollapsed && (
          <div className="flex min-w-0 items-center gap-3 overflow-hidden rounded-xl bg-gradient-to-br from-zarin-navy to-zarin-navy-soft pe-9 shadow-lg">
            <div className="flex size-9 shrink-0 items-center justify-center rounded-lg bg-white/15 shadow-sm ring-1 ring-white/20">
              <span className="text-sm font-black text-white select-none">Z</span>
            </div>
            <div className="min-w-0 flex-1 overflow-hidden">
              <span className="block truncate text-sm font-black text-white tracking-tight">زرین‌پال</span>
              <span className="block truncate text-[10px] font-medium text-white/70">پلتفرم هوشمند</span>
            </div>
          </div>
        )}


        {/* Page context + category */}
        {!isCollapsed && (
          <div className="mt-3 px-1">
            <h2 className="text-sm font-black text-foreground tracking-tight">
              {pageTitleMap[activeTab] ?? 'داشبورد'}
            </h2>
            <p className="mt-0.5 truncate text-[11px] text-muted-foreground">
              {subtitleMap[activeTab] ?? ''}
            </p>
            <span className="mt-1 inline-flex items-center rounded-full bg-primary/10 px-2 py-0.5 text-[10px] font-black text-primary">
              {activeMerchant.category}
            </span>
          </div>
        )}
      </div>

      {/* ── Separator ── */}
      {!isCollapsed && (
        <div data-slot="sidebar-separator" data-sidebar="separator" className="mx-3 w-auto bg-sidebar-border" />
      )}

      {/* ── Navigation ── */}
      <div data-slot="sidebar-content" data-sidebar="content" className="flex min-h-0 flex-1 flex-col gap-0.5 overflow-auto px-2 py-2">
        {!isCollapsed && (
          <div data-slot="sidebar-group-label" data-sidebar="group-label" className="flex h-7 shrink-0 items-center rounded-md px-2 text-[10px] font-bold text-muted-foreground/70">
            فهرست اصلی
          </div>
        )}

        <nav aria-label="ناوبری اصلی" className="mt-1 flex flex-col gap-0.5">
          {NAV_ITEMS.map((item) => {
            const isActive = location.pathname === item.path || (item.path !== '/dashboard' && location.pathname.startsWith(item.path))
            const Icon = item.icon

            const linkClassName = cn(
              'flex w-full items-center gap-2.5 overflow-hidden rounded-lg p-2 text-start text-sm ring-sidebar-ring outline-hidden transition-all duration-200',
              'hover:bg-sidebar-accent hover:text-sidebar-accent-foreground',
              'focus-visible:ring-2',
              'active:bg-sidebar-accent active:text-sidebar-accent-foreground',
              'data-[size=default]:h-9',
              '[&_svg]:size-4 [&_svg]:shrink-0 [&>span:last-child]:truncate',
              isActive && 'bg-sidebar-accent text-sidebar-accent-foreground font-medium',
              isCollapsed && 'justify-center'
            )

            const linkContent = (
              <>
                <Icon
                  className={cn(
                    'size-4 shrink-0 transition-all duration-200',
                    isActive && 'text-primary'
                  )}
                  strokeWidth={isActive ? 2.5 : 2}
                />
                {!isCollapsed && (
                  <span className="truncate text-sm font-bold">{item.label}</span>
                )}
                {isActive && !isCollapsed && (
                  <span className="mr-auto flex size-2 rounded-full bg-primary shadow-sm shadow-primary/40" />
                )}
              </>
            )

            if (isCollapsed) {
              return (
                <Tooltip key={item.id}>
                  <TooltipTrigger asChild>
                    <NavLink to={item.path} className={linkClassName}>
                      {linkContent}
                    </NavLink>
                  </TooltipTrigger>
                  <TooltipContent side="left" align="center" sideOffset={8}>
                    <p className="text-xs font-bold">{item.label}</p>
                    <p className="text-[10px] text-muted-foreground">{item.hint}</p>
                  </TooltipContent>
                </Tooltip>
              )
            }

            return (
              <NavLink key={item.id} to={item.path} className={linkClassName}>
                {linkContent}
              </NavLink>
            )
          })}
        </nav>
      </div>

      {/* ── Footer ── */}
      <div data-slot="sidebar-footer" data-sidebar="footer" className="p-2">
        {/* Notification bell */}
        {!isCollapsed && (
          <div className="mb-2 px-1">
            <NotificationBell />
          </div>
        )}
        {isCollapsed && (
          <div className="mb-2 flex justify-center">
            <NotificationBell />
          </div>
        )}

        {/* Merchant picker */}
        <DropdownMenu>
          <DropdownMenuTrigger asChild>
            <button
              type="button"
              className={cn(
                'group flex w-full items-center gap-2.5 rounded-xl border border-sidebar-border/80 bg-white/60 p-2 shadow-sm backdrop-blur-sm transition-all duration-200',
                'hover:border-sidebar-border hover:bg-white hover:shadow-md',
                'focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring/40',
                isCollapsed && 'justify-center'
              )}
            >
              <span
                className="flex size-8 shrink-0 items-center justify-center rounded-lg text-xs font-black text-white shadow-sm"
                style={{ background: 'linear-gradient(135deg, #36B37E 0%, #0D1B4B 100%)' }}
              >
                {activeMerchant.name.charAt(0)}
              </span>

              {!isCollapsed && (
                <>
                  <span className="min-w-0 flex-1 text-start">
                    <span className="block text-[10px] font-bold leading-tight text-muted-foreground">
                      پذیرنده فعال
                    </span>
                    <span className="block max-w-36 truncate text-xs font-extrabold leading-tight text-foreground">
                      {activeMerchant.name}
                    </span>
                  </span>
                  <ChevronsUpDown className="size-3.5 shrink-0 text-muted-foreground/70 transition-transform duration-200 group-data-open:rotate-180" />
                </>
              )}
            </button>
          </DropdownMenuTrigger>

          <DropdownMenuContent align="end" sideOffset={8} className="w-80 rounded-2xl border-border/60 p-1.5 shadow-xl">
            <DropdownMenuLabel className="flex items-center justify-between px-2 py-1.5 text-xs font-bold text-muted-foreground">
              <span className="flex items-center gap-1.5">
                <Store className="size-3.5" />
                تغییر پذیرنده
              </span>
              <span className="rounded-full bg-primary/10 px-2 py-0.5 text-[10px] font-black text-primary">
                {mockMerchants.length} پذیرنده
              </span>
            </DropdownMenuLabel>
            <DropdownMenuSeparator className="my-1" />

            {mockMerchants.map((merchant) => {
              const isActive = merchant.id === activeMerchant.id
              return (
                <DropdownMenuItem
                  key={merchant.id}
                  onClick={() => handleMerchantChange(merchant.id)}
                  className={cn(
                    'flex cursor-pointer items-center gap-3 rounded-xl px-2 py-2.5 transition-all duration-150',
                    isActive ? 'bg-primary/8 text-primary' : 'hover:bg-muted/60',
                  )}
                >
                  <span
                    className={cn(
                      'flex size-9 shrink-0 items-center justify-center rounded-xl text-sm font-black transition-all duration-150',
                      isActive ? 'text-white shadow-sm shadow-primary/20' : 'bg-muted text-muted-foreground',
                    )}
                    style={isActive ? { background: 'linear-gradient(135deg, #36B37E 0%, #0D1B4B 100%)' } : {}}
                  >
                    {merchant.name.charAt(0)}
                  </span>
                  <span className="min-w-0 flex-1">
                    <span className="block truncate text-sm font-bold">{merchant.name}</span>
                    <span className="block truncate text-xs text-muted-foreground">
                      {merchant.id} · {merchant.category}
                    </span>
                  </span>
                  {isActive && <span className="size-4 shrink-0 text-primary">✓</span>}
                </DropdownMenuItem>
              )
            })}
          </DropdownMenuContent>
        </DropdownMenu>
      </div>
    </>
  )
}

export default SidebarNav
