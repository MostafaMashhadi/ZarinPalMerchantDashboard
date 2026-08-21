import React, { useMemo } from 'react'
import { useSelector } from 'react-redux'
import type { RootState } from '../store/store'
import {
  TrendingUp, TrendingDown, DollarSign, BadgeCheck, XCircle, ShoppingBag,
  ArrowUpRight,
} from 'lucide-react'
import type { ReactNode } from 'react'
import { cn } from '@/lib/utils'
import type { HeadlineCard } from '../services/types'
import {
  ResponsiveContainer,
  RadialBarChart,
  RadialBar,
  AreaChart,
  Area,
  Tooltip,
} from 'recharts'

/* ──────────────────────────────────────────────────────────────────
   Metric visual config
────────────────────────────────────────────────────────────────── */
interface MetricVisual {
  icon: ReactNode
  topBorderClass: string
  iconBg: string
  iconColor: string
  chartColor: string
  chartTrack: string
  badgePos: string
  badgeNeg: string
}

const VISUAL: Record<string, MetricVisual> = {
  gross_volume: {
    icon: <DollarSign className="size-4" />,
    topBorderClass: 'card-zarin-green',
    iconBg: 'rgba(54,179,126,0.12)',
    iconColor: '#2A9065',
    chartColor: '#36B37E',
    chartTrack: 'rgba(54,179,126,0.12)',
    badgePos: 'bg-emerald-50 text-emerald-700',
    badgeNeg: 'bg-red-50 text-red-600',
  },
  success_rate: {
    icon: <BadgeCheck className="size-4" />,
    topBorderClass: 'card-zarin-gold',
    iconBg: 'rgba(245,166,35,0.12)',
    iconColor: '#C8841B',
    chartColor: '#F5A623',
    chartTrack: 'rgba(245,166,35,0.12)',
    badgePos: 'bg-amber-50 text-amber-700',
    badgeNeg: 'bg-red-50 text-red-600',
  },
  failed_volume: {
    icon: <XCircle className="size-4" />,
    topBorderClass: 'card-zarin-red',
    iconBg: 'rgba(229,57,53,0.10)',
    iconColor: '#C62828',
    chartColor: '#E53935',
    chartTrack: 'rgba(229,57,53,0.08)',
    badgePos: 'bg-emerald-50 text-emerald-700',
    badgeNeg: 'bg-red-50 text-red-600',
  },
  avg_basket: {
    icon: <ShoppingBag className="size-4" />,
    topBorderClass: 'card-zarin-navy',
    iconBg: 'rgba(13,27,75,0.08)',
    iconColor: '#0D1B4B',
    chartColor: '#1A2F6B',
    chartTrack: 'rgba(13,27,75,0.07)',
    badgePos: 'bg-blue-50 text-blue-700',
    badgeNeg: 'bg-red-50 text-red-600',
  },
}

const fallbackVisual = VISUAL.gross_volume

/* ──────────────────────────────────────────────────────────────────
   Mini donut – SVG, no lib, animated via CSS class
────────────────────────────────────────────────────────────────── */
interface DonutProps {
  pct: number      // 0-100
  color: string
  track: string
  size?: number
  stroke?: number
  delay?: number
}

const MiniDonut: React.FC<DonutProps> = ({ pct, color, track, size = 56, stroke = 6, delay = 0 }) => {
  const r = (size - stroke) / 2
  const circ = 2 * Math.PI * r
  const offset = circ * (1 - Math.min(pct, 100) / 100)

  return (
    <svg width={size} height={size} viewBox={`0 0 ${size} ${size}`} aria-hidden="true" style={{ transform: 'rotate(-90deg)' }}>
      {/* Track */}
      <circle cx={size / 2} cy={size / 2} r={r} fill="none" stroke={track} strokeWidth={stroke} />
      {/* Fill arc */}
      <circle
        cx={size / 2} cy={size / 2} r={r}
        fill="none"
        stroke={color}
        strokeWidth={stroke}
        strokeLinecap="round"
        strokeDasharray={circ}
        strokeDashoffset={offset}
        className="donut-arc"
        style={{
          '--dash-total': circ,
          '--dash-offset': offset,
          animationDelay: `${delay}ms`,
        } as React.CSSProperties}
      />
    </svg>
  )
}

/* ──────────────────────────────────────────────────────────────────
   Mini sparkline area — uses Recharts AreaChart
────────────────────────────────────────────────────────────────── */
interface SparklineProps {
  data: { v: number }[]
  color: string
  delay?: number
}

const Sparkline: React.FC<SparklineProps> = ({ data, color, delay = 0 }) => (
  <div style={{ animationDelay: `${delay}ms` }} className="animate-fade-in">
    <ResponsiveContainer width="100%" height={36}>
      <AreaChart data={data} margin={{ top: 2, right: 0, bottom: 0, left: 0 }}>
        <defs>
          <linearGradient id={`sg-${color.replace('#','')}`} x1="0" y1="0" x2="0" y2="1">
            <stop offset="0%" stopColor={color} stopOpacity={0.35} />
            <stop offset="100%" stopColor={color} stopOpacity={0.02} />
          </linearGradient>
        </defs>
        <Area
          type="monotone"
          dataKey="v"
          stroke={color}
          strokeWidth={1.8}
          fill={`url(#sg-${color.replace('#','')})`}
          dot={false}
          isAnimationActive={true}
          animationDuration={700}
          animationEasing="ease-out"
        />
        <Tooltip
          content={() => null}
          cursor={false}
        />
      </AreaChart>
    </ResponsiveContainer>
  </div>
)

/* ──────────────────────────────────────────────────────────────────
   Deterministic sparkline data seeded from card value
────────────────────────────────────────────────────────────────── */
function makeSparkData(seed: number, delta: number): { v: number }[] {
  const pts = 12
  const arr: { v: number }[] = []
  let v = 50 + (seed % 20)
  for (let i = 0; i < pts; i++) {
    // last few points trend in delta direction
    const trend = i > pts - 4 ? delta / 4 : 0
    v = Math.max(5, Math.min(95, v + (((seed * (i + 1) * 7919) % 17) - 8) + trend))
    arr.push({ v })
  }
  return arr
}

/* ──────────────────────────────────────────────────────────────────
   Radial progress gauge (success_rate card only)
────────────────────────────────────────────────────────────────── */
interface RadialGaugeProps {
  value: number   // 0-100
  color: string
}

const RadialGauge: React.FC<RadialGaugeProps> = ({ value, color }) => {
  const data = [{ name: 'rate', value, fill: color }]
  return (
    <div style={{ width: 56, height: 56 }}>
      <RadialBarChart
        width={56}
        height={56}
        innerRadius={18}
        outerRadius={28}
        data={data}
        startAngle={225}
        endAngle={-45}
      >
        <RadialBar background={{ fill: 'rgba(245,166,35,0.10)' }} dataKey="value" isAnimationActive animationDuration={800} />
      </RadialBarChart>
    </div>
  )
}

/* ──────────────────────────────────────────────────────────────────
   Skeleton
────────────────────────────────────────────────────────────────── */
const SkeletonCard: React.FC = () => (
  <div className="flex h-52 animate-pulse flex-col gap-3 rounded-[20px] border border-border/50 bg-white p-5 shadow-sm">
    <div className="flex items-center gap-2.5">
      <div className="size-8 rounded-xl bg-muted" />
      <div className="h-3 w-24 rounded-full bg-muted" />
    </div>
    <div className="mt-auto space-y-2">
      <div className="h-7 w-28 rounded-lg bg-muted" />
      <div className="h-9 w-full rounded-lg bg-muted/60" />
      <div className="h-1.5 w-full rounded-full bg-muted/40" />
    </div>
  </div>
)

/* ──────────────────────────────────────────────────────────────────
   Hero stat (shown in gradient banner at top of section)
────────────────────────────────────────────────────────────────── */
interface HeroStatProps { label: string; value: string; positive: boolean; delta: number }

const HeroStat: React.FC<HeroStatProps> = ({ label, value, positive, delta }) => (
  <div className="flex flex-col gap-0.5">
    <div className="text-[10px] font-semibold text-white/55 uppercase tracking-wider">{label}</div>
    <div dir="ltr" className="text-xl font-black text-white tabular-nums">{value}</div>
    <div className={cn(
      'flex items-center gap-0.5 text-[10px] font-black tabular-nums',
      positive ? 'text-emerald-300' : 'text-red-300',
    )}>
      {positive ? <TrendingUp className="size-3" /> : <TrendingDown className="size-3" />}
      {positive ? '+' : ''}{delta.toFixed(1)}٪
    </div>
  </div>
)

/* ──────────────────────────────────────────────────────────────────
   Main component
────────────────────────────────────────────────────────────────── */
const DashboardSummaryCards: React.FC = () => {
  const { summary, isLoading } = useSelector((state: RootState) => state.dashboard)

  const cards: HeadlineCard[] = useMemo(() => summary?.headline_cards ?? [], [summary])

  if (isLoading && !summary) {
    return (
      <section>
        <div className="mb-5 flex items-center justify-between">
          <div className="h-4 w-44 animate-pulse rounded-full bg-muted" />
          <div className="h-6 w-36 animate-pulse rounded-full bg-muted" />
        </div>
        <div className="grid grid-cols-2 gap-4 lg:grid-cols-4 lg:gap-5">
          {Array.from({ length: 4 }).map((_, i) => <SkeletonCard key={i} />)}
        </div>
      </section>
    )
  }

  return (
    <section className="space-y-5">

      {/* ── Gradient Hero Banner ──────────────────────────────── */}
      <div className="overview-hero p-6 sm:p-8">
        {/* Inner glass overlay for depth */}
        <div className="absolute inset-0 rounded-3xl overflow-hidden pointer-events-none">
          <div className="absolute inset-0 bg-gradient-to-br from-white/[0.06] via-transparent to-transparent" />
          {/* Dot grid */}
          <div
            className="absolute inset-0 opacity-[0.12]"
            style={{
              backgroundImage: 'radial-gradient(rgba(255,255,255,0.5) 1px, transparent 1.5px)',
              backgroundSize: '22px 22px',
            }}
          />
        </div>

        <div className="relative z-10 flex flex-col gap-5 sm:flex-row sm:items-center sm:justify-between">
          {/* Heading */}
          <div>
            <div className="flex items-center gap-2.5 mb-2">
              <div className="size-8 rounded-xl logo-zarin flex items-center justify-center ring-1 ring-white/20">
                <span className="text-sm font-black text-white">Z</span>
              </div>
              <h2 className="text-sm font-black text-white tracking-tight">نمای کلی عملکرد پذیرنده</h2>
            </div>
            {summary && (
              <p className="text-xs text-white/55">
                دوره: {new Date(summary.period.start).toLocaleDateString('fa-IR')} تا {new Date(summary.period.end).toLocaleDateString('fa-IR')}
              </p>
            )}
          </div>

          {/* Hero stats row */}
          <div className="flex flex-wrap items-center gap-6 sm:gap-8">
            {cards.slice(0, 3).map((c) => (
              <HeroStat
                key={c.key}
                label={c.label}
                value={c.formatted.replace(/ تومان$/, '')}
                positive={c.delta >= 0}
                delta={c.delta}
              />
            ))}
          </div>

          {/* CTA link */}
          <a
            href="#"
            className="hidden lg:flex items-center gap-1.5 rounded-xl border border-white/20 bg-white/10 px-4 py-2 text-xs font-bold text-white backdrop-blur-sm transition-all hover:bg-white/20"
          >
            مشاهده گزارش کامل
            <ArrowUpRight className="size-3.5" />
          </a>
        </div>
      </div>

      {/* ── Cards grid ────────────────────────────────────────── */}
      <div className="grid grid-cols-2 gap-4 lg:grid-cols-4 lg:gap-5">
        {cards.map((card, index) => {
          const visual = VISUAL[card.key] ?? fallbackVisual
          const positive = card.delta >= 0
          const pct = Math.min(100, Math.abs(card.delta) * 7 + 45)
          const sparkData = makeSparkData(Math.round(card.value * 100), card.delta)
          const animDelay = index * 90

          return (
            <div
              key={card.key}
              className={cn(
                'card-zarin group relative flex flex-col overflow-hidden animate-fade-in',
                visual.topBorderClass,
              )}
              style={{ animationDelay: `${animDelay}ms`, padding: '18px 18px 16px' }}
            >
              {/* ── Header: icon + label + donut ── */}
              <div className="flex items-start justify-between gap-2 mb-3">
                <div className="flex items-center gap-2">
                  <div
                    className="flex size-8 shrink-0 items-center justify-center rounded-xl"
                    style={{ background: visual.iconBg, color: visual.iconColor }}
                  >
                    {visual.icon}
                  </div>
                  <span className="text-[11px] font-bold text-muted-foreground leading-tight">
                    {card.label}
                  </span>
                </div>

                {/* Donut or Radial gauge */}
                {card.key === 'success_rate' ? (
                  <RadialGauge value={card.value} color={visual.chartColor} />
                ) : (
                  <MiniDonut
                    pct={pct}
                    color={visual.chartColor}
                    track={visual.chartTrack}
                    delay={animDelay + 150}
                  />
                )}
              </div>

              {/* ── Value + delta ── */}
              <div className="flex items-end justify-between gap-2 mb-3">
                <div>
                  <div
                    dir="ltr"
                    className="text-[1.45rem] font-black tracking-tight tabular-nums text-foreground lg:text-3xl leading-none"
                  >
                    {card.formatted.replace(/ تومان$/, '')}
                  </div>
                  <div className="mt-0.5 text-[10px] font-semibold text-muted-foreground/80">
                    {card.unit === 'Rial' ? 'تومان' : card.unit === '%' ? 'درصد موفقیت' : card.unit}
                  </div>
                </div>

                <span
                  title="نسبت به دوره قبل"
                  className={cn(
                    'flex shrink-0 items-center gap-0.5 rounded-full px-2 py-0.5 text-[10px] font-black tabular-nums',
                    positive ? visual.badgePos : visual.badgeNeg,
                  )}
                >
                  {positive ? <TrendingUp className="size-3" /> : <TrendingDown className="size-3" />}
                  {positive ? '+' : ''}{card.delta.toFixed(1)}٪
                </span>
              </div>

              {/* ── Mini sparkline ── */}
              <div className="mt-auto -mx-1">
                <Sparkline data={sparkData} color={visual.chartColor} delay={animDelay + 200} />
              </div>
            </div>
          )
        })}
      </div>
    </section>
  )
}

export default DashboardSummaryCards
