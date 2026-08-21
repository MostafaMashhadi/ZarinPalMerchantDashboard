import React from 'react'
import { BarChart3, Lightbulb, FlaskConical } from 'lucide-react'
import type { LucideIcon } from 'lucide-react'
import { cn } from '@/lib/utils'

interface NavItem {
  id: string
  label: string
  hint: string
  icon: LucideIcon
}

// Tab order: نمای کلی → بینش‌ها (was موتور تحلیلی) → موتور تحلیلی (was بینش‌ها)
const ITEMS: NavItem[] = [
  { id: 'overview',  label: 'نمای کلی',    hint: 'عملکرد پذیرنده و خلاصه هوشمند', icon: BarChart3    },
  { id: 'insights',  label: 'بینش‌ها',      hint: 'فهرست بینش‌ها و ردیابی منشأ',   icon: Lightbulb   },
  { id: 'analyses',  label: 'موتور تحلیلی', hint: 'اجرای تحلیل‌های کلاسیک',        icon: FlaskConical },
]

interface TopNavProps {
  activeTab: string
  onTabChange: (tab: string) => void
}

const TopNav: React.FC<TopNavProps> = ({ activeTab, onTabChange }) => {
  return (
    <nav aria-label="ناوبری اصلی">
      <div className="flex w-full items-center gap-1 rounded-2xl border border-border/60 bg-white/60 p-1 shadow-inner backdrop-blur-lg">
        {ITEMS.map((item) => {
          const isActive = activeTab === item.id
          const Icon = item.icon
          return (
            <button
              key={item.id}
              type="button"
              onClick={() => onTabChange(item.id)}
              aria-pressed={isActive}
              aria-label={item.hint}
              title={item.hint}
              className={cn(
                'group relative flex flex-1 items-center justify-center gap-2 rounded-xl px-3 py-2.5 text-sm font-bold whitespace-nowrap',
                'transition-all duration-200 ease-out',
                'focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring/50',
                'active:scale-[0.97]',
                isActive
                  ? 'nav-pill-active text-white shadow-sm'
                  : 'text-muted-foreground hover:bg-white hover:text-foreground hover:shadow-sm',
              )}
            >
              <Icon
                className={cn(
                  'size-4 transition-transform duration-200 shrink-0',
                  isActive ? 'scale-105' : 'group-hover:-translate-y-px group-hover:scale-105',
                )}
                strokeWidth={isActive ? 2.5 : 2}
              />
              <span className="hidden sm:inline">{item.label}</span>

              {isActive && (
                <span className="absolute inset-x-0 -bottom-px h-px bg-gradient-to-r from-transparent via-white/40 to-transparent" />
              )}
            </button>
          )
        })}
      </div>
    </nav>
  )
}

export default TopNav
