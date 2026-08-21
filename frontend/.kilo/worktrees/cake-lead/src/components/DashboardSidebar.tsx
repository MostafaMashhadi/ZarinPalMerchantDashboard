import React from 'react'
import { useDispatch, useSelector } from 'react-redux'
import { useNavigate, useLocation } from 'react-router-dom'
import { BarChart3, Lightbulb, FlaskConical, Coins } from 'lucide-react'
import type { RootState, AppDispatch } from '../store/store'
import { setActiveTab } from '../store/dashboardSlice'
import {
  Sidebar,
  SidebarContent,
  SidebarFooter,
  SidebarGroup,
  SidebarGroupContent,
  SidebarHeader,
  SidebarMenu,
  SidebarMenuButton,
  SidebarMenuItem,
} from '@/components/ui/sidebar'
import { Separator } from '@/components/ui/separator'

const NAV_ITEMS = [
  { id: 'overview', label: 'نمای کلی', icon: BarChart3, path: '/dashboard' },
  { id: 'insights', label: 'بینش‌ها', icon: Lightbulb, path: '/insights' },
  { id: 'analyses', label: 'موتور تحلیلی', icon: FlaskConical, path: '/analyses' },
  { id: 'ops', label: 'هزینه‌ها', icon: Coins, path: '/ops/cost' },
]

const DashboardSidebar: React.FC = () => {
  const dispatch = useDispatch<AppDispatch>()
  const navigate = useNavigate()
  const location = useLocation()
  const activeTab = useSelector((state: RootState) => state.dashboard.activeTab)

  const handleNav = (path: string, tabId: string) => {
    dispatch(setActiveTab(tabId))
    navigate(path, { replace: false })
  }

  return (
    <Sidebar collapsible="icon" variant="floating" className="border-border/60">
      <SidebarHeader>
        <div className="flex items-center gap-2 px-2 py-1.5">
          <div className="flex size-8 shrink-0 items-center justify-center rounded-lg logo-zarin shadow-sm">
            <span className="text-sm font-black text-white">Z</span>
          </div>
          <div className="min-w-0 flex-1">
            <div className="truncate text-sm font-black text-foreground">زرین‌پال</div>
            <div className="truncate text-[10px] font-bold text-muted-foreground">داشبورد تحلیل پرداخت</div>
          </div>
        </div>
      </SidebarHeader>

      <Separator className="mx-2" />

      <SidebarContent>
        <SidebarGroup>
          <SidebarGroupContent>
            <SidebarMenu>
              {NAV_ITEMS.map((item) => {
                const Icon = item.icon
                const isActive = activeTab === item.id || location.pathname === item.path
                return (
                  <SidebarMenuItem key={item.id}>
                    <SidebarMenuButton
                      tooltip={item.label}
                      isActive={isActive}
                      onClick={() => handleNav(item.path, item.id)}
                    >
                      <Icon className="size-4" />
                      <span>{item.label}</span>
                    </SidebarMenuButton>
                  </SidebarMenuItem>
                )
              })}
            </SidebarMenu>
          </SidebarGroupContent>
        </SidebarGroup>
      </SidebarContent>

      <SidebarFooter>
        <div className="px-2 py-1.5 text-center">
          <span className="text-[10px] font-bold text-muted-foreground">© زرین‌پال</span>
        </div>
      </SidebarFooter>
    </Sidebar>
  )
}

export default DashboardSidebar