import React, { useEffect, useMemo } from 'react'
import { useDispatch, useSelector } from 'react-redux'
import { Bell, Check, BellOff } from 'lucide-react'
import type { RootState, AppDispatch } from '../store/store'
import {
  fetchNotifications,
  markNotificationRead,
  unreadCount,
  setOpen,
  markReadLocal,
} from '../store/notificationsSlice'
import { Button } from '@/components/ui/button'
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuLabel,
  DropdownMenuItem,
  DropdownMenuSeparator,
  DropdownMenuTrigger,
} from '@/components/ui/dropdown-menu'
import { cn } from '@/lib/utils'

const SEVERITY_LABEL: Record<string, string> = {
  critical: 'بحرانی',
  warning:  'هشدار',
  info:     'اطلاع',
}

/* Map severity to ZarinPal palette */
const SEVERITY_BADGE: Record<string, string> = {
  critical: 'bg-red-50 text-red-700 border border-red-200',
  warning:  'bg-amber-50 text-amber-700 border border-amber-200',
  info:     'badge-green',
}

const NotificationBell: React.FC = () => {
  const dispatch = useDispatch<AppDispatch>()
  const merchantRef = useSelector((state: RootState) => state.dashboard.selectedMerchant)
  const { items, loading, open } = useSelector((state: RootState) => state.notifications)

  useEffect(() => {
    dispatch(fetchNotifications(merchantRef))
  }, [dispatch, merchantRef])

  const unread = useMemo(() => unreadCount(items), [items])

  return (
    <DropdownMenu open={open} onOpenChange={(o) => dispatch(setOpen(o))}>
      <DropdownMenuTrigger asChild>
        <Button
          variant="ghost"
          size="icon"
          title="اعلان‌ها"
          aria-label={`اعلان‌ها${unread > 0 ? ` — ${unread} نخوانده` : ''}`}
          className={cn(
            'relative rounded-xl text-muted-foreground',
            'transition-all duration-200',
            'hover:bg-white hover:text-foreground hover:shadow-sm',
            open && 'bg-white shadow-sm text-foreground',
          )}
        >
          <Bell className="size-5" strokeWidth={2} />
          {unread > 0 && (
            <span
              aria-hidden="true"
              className="absolute -top-1 -end-1 flex size-[18px] items-center justify-center rounded-full bg-destructive text-[9px] font-black text-white shadow-sm shadow-destructive/25 font-numeric"
            >
              {unread > 9 ? '۹+' : unread}
            </span>
          )}
        </Button>
      </DropdownMenuTrigger>

      <DropdownMenuContent
        align="end"
        sideOffset={8}
        className="w-80 rounded-2xl border-border/60 p-1.5 shadow-xl"
      >
        {/* Header */}
        <DropdownMenuLabel className="flex items-center justify-between px-2 py-1.5 text-xs font-bold text-muted-foreground">
          <span className="flex items-center gap-1.5">
            <Bell className="size-3.5" />
            اعلان‌ها
          </span>
          {unread > 0 && (
            <span className="rounded-full bg-destructive/10 px-2 py-0.5 text-[10px] font-black text-destructive font-numeric">
              {unread} نخوانده
            </span>
          )}
        </DropdownMenuLabel>
        <DropdownMenuSeparator className="my-1" />

        {/* Loading state */}
        {loading && items.length === 0 && (
          <div className="flex items-center justify-center gap-2 py-8 text-xs text-muted-foreground">
            <span className="size-3 animate-spin rounded-full border-2 border-primary border-t-transparent" />
            در حال بارگذاری...
          </div>
        )}

        {/* Empty state */}
        {!loading && items.length === 0 && (
          <div className="flex flex-col items-center gap-2 py-8 text-xs text-muted-foreground">
            <div className="flex size-10 items-center justify-center rounded-full bg-muted/50">
              <BellOff className="size-4 opacity-50" />
            </div>
            <span>اعلانی وجود ندارد</span>
          </div>
        )}

        {/* Notifications list */}
        <div className="custom-scrollbar max-h-80 overflow-y-auto space-y-0.5">
          {items.map((item) => {
            const isUnread = item.read_at === null
            const badgeClass = SEVERITY_BADGE[item.severity] ?? 'badge-green'

            return (
              <DropdownMenuItem
                key={item.id}
                onClick={() => {
                  if (isUnread) {
                    dispatch(markReadLocal(item.id))
                    dispatch(markNotificationRead({ merchantRef, id: item.id }))
                  }
                }}
                className={cn(
                  'flex cursor-pointer items-start gap-2.5 rounded-xl px-2 py-2.5',
                  'transition-colors duration-150',
                  !isUnread && 'opacity-55',
                  isUnread && 'bg-primary/[0.02]',
                )}
              >
                {/* Severity badge pill */}
                <span
                  className={cn(
                    'mt-0.5 flex h-7 w-12 shrink-0 items-center justify-center rounded-lg text-[9px] font-black',
                    badgeClass,
                  )}
                >
                  {SEVERITY_LABEL[item.severity] ?? item.severity}
                </span>

                {/* Content */}
                <span className="min-w-0 flex-1">
                  <span className="block truncate text-sm font-bold text-foreground">
                    {item.title}
                  </span>
                  <span className="mt-0.5 block text-xs leading-relaxed text-muted-foreground line-clamp-2">
                    {item.body}
                  </span>
                </span>

                {/* Unread dot */}
                {isUnread && (
                  <span className="mt-1 shrink-0 flex size-5 items-center justify-center rounded-md text-primary">
                    <Check className="size-3.5" />
                  </span>
                )}
              </DropdownMenuItem>
            )
          })}
        </div>
      </DropdownMenuContent>
    </DropdownMenu>
  )
}

export default NotificationBell
