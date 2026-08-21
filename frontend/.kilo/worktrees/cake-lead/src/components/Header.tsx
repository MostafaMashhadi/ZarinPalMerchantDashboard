import React from 'react'
import { Check, ChevronsUpDown, Store } from 'lucide-react'
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuLabel,
  DropdownMenuSeparator,
  DropdownMenuTrigger,
} from '@/components/ui/dropdown-menu'
import { mockMerchants } from '@/services/mockData'
import { cn } from '@/lib/utils'
import NotificationBell from './NotificationBell'

interface HeaderProps {
  pageTitle: string
  subtitle: string
  selectedMerchant: string
  onMerchantChange: (merchantId: string) => void
}

const Header: React.FC<HeaderProps> = ({ pageTitle, subtitle, selectedMerchant, onMerchantChange }) => {
  const activeMerchant = mockMerchants.find((m) => m.id === selectedMerchant) ?? mockMerchants[0]

  return (
    <header className="flex items-center justify-between gap-4">
      {/* ── Brand + Page title ── */}
      <div className="flex min-w-0 items-center gap-3">
        {/* Z Logo mark – ZarinPal green/navy gradient */}
        <div className="flex size-10 shrink-0 items-center justify-center rounded-xl logo-zarin ring-1 ring-white/25 ring-inset shadow-md">
          <span className="text-base font-black text-white select-none">Z</span>
        </div>
        <div className="min-w-0">
          <h1 className="truncate text-base font-black tracking-tight text-foreground lg:text-lg">
            {pageTitle}
          </h1>
          <p className="truncate text-xs text-muted-foreground">{subtitle}</p>
        </div>
      </div>

      {/* ── Actions ── */}
      <div className="flex items-center gap-2.5">
        <NotificationBell />

        {/* Merchant picker */}
        <DropdownMenu>
          <DropdownMenuTrigger asChild>
            <button
              type="button"
              className={cn(
                'group flex items-center gap-2.5 rounded-xl border border-border/70',
                'bg-white/70 py-2 pe-3 ps-2.5 shadow-sm backdrop-blur-lg',
                'transition-all duration-200',
                'hover:border-border hover:bg-white hover:shadow-md',
                'focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring/40',
              )}
            >
              {/* Avatar */}
              <span
                className="flex size-8 shrink-0 items-center justify-center rounded-lg font-black text-sm text-white shadow-sm"
                style={{ background: 'linear-gradient(135deg, #36B37E 0%, #0D1B4B 100%)' }}
              >
                {activeMerchant.name.charAt(0)}
              </span>

              {/* Label (tablet+) */}
              <span className="hidden min-w-0 text-start sm:block">
                <span className="block text-[10px] font-bold leading-tight text-muted-foreground">
                  پذیرنده فعال
                </span>
                <span className="block max-w-36 truncate text-sm font-extrabold leading-tight text-foreground">
                  {activeMerchant.name}
                </span>
              </span>

              <ChevronsUpDown
                className="size-3.5 shrink-0 text-muted-foreground/70 transition-transform duration-200 group-data-open:rotate-180"
              />
            </button>
          </DropdownMenuTrigger>

          <DropdownMenuContent align="end" sideOffset={8} className="w-80 rounded-2xl border-border/60 p-1.5 shadow-xl">
            <DropdownMenuLabel className="flex items-center justify-between px-2 py-1.5 text-xs font-bold text-muted-foreground">
              <span className="flex items-center gap-1.5">
                <Store className="size-3.5" />
                تغییر پذیرنده
              </span>
              <span className="badge-green rounded-full px-2 py-0.5 text-[10px] font-black">
                {mockMerchants.length} پذیرنده
              </span>
            </DropdownMenuLabel>
            <DropdownMenuSeparator className="my-1" />

            {mockMerchants.map((merchant) => {
              const isActive = merchant.id === activeMerchant.id
              return (
                <DropdownMenuItem
                  key={merchant.id}
                  onClick={() => onMerchantChange(merchant.id)}
                  className={cn(
                    'flex cursor-pointer items-center gap-3 rounded-xl px-2 py-2.5 transition-all duration-150',
                    isActive
                      ? 'bg-primary/8 text-primary'
                      : 'hover:bg-muted/60',
                  )}
                >
                  <span
                    className={cn(
                      'flex size-9 shrink-0 items-center justify-center rounded-xl text-sm font-black transition-all duration-150',
                      isActive
                        ? 'text-white shadow-sm shadow-primary/20'
                        : 'bg-muted text-muted-foreground',
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
                  {isActive && <Check className="size-4 shrink-0 text-primary" />}
                </DropdownMenuItem>
              )
            })}
          </DropdownMenuContent>
        </DropdownMenu>
      </div>
    </header>
  )
}

export default Header
