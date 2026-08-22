import React, { useState, useEffect } from 'react'
import { useDispatch, useSelector } from 'react-redux'
import type { RootState, AppDispatch } from '../store/store'
import { login } from '../store/authSlice'
import { Input } from '@/components/ui/input'
import { Label } from '@/components/ui/label'
import { AlertTriangle, ArrowLeft, ShieldCheck, Zap, HeadphonesIcon, Clock } from 'lucide-react'
import { cn } from '@/lib/utils'
import ZarinpalLogo from './ZarinpalLogo'

const LoginScreen: React.FC = () => {
  const dispatch = useDispatch<AppDispatch>()
  const { isLoggingIn, loginError, lockoutRetryAfter } = useSelector((state: RootState) => state.auth)
  const [email, setEmail] = useState('merchant@zarinpal.test')
  const [password, setPassword] = useState('merchant-pass')
  const [countdown, setCountdown] = useState(0)

  useEffect(() => {
    if (lockoutRetryAfter && lockoutRetryAfter > 0) {
      setCountdown(lockoutRetryAfter)
      const timer = setInterval(() => {
        setCountdown((c) => {
          if (c <= 1) {
            clearInterval(timer)
            return 0
          }
          return c - 1
        })
      }, 1000)
      return () => clearInterval(timer)
    }
  }, [lockoutRetryAfter])

  const submit = (e: React.FormEvent) => {
    e.preventDefault()
    dispatch(login({ email, password }))
  }

  return (
    <div className="relative flex min-h-dvh overflow-hidden" dir="rtl">
      {/* ── Left panel: Navy trust sidebar (hidden on mobile) ── */}
      <div className="hidden lg:flex lg:w-2/5 surface-navy relative flex-col items-start justify-between px-10 py-12 overflow-hidden">
        {/* Subtle overlay geometry */}
        <div className="pointer-events-none absolute inset-0">
          <div className="absolute top-0 left-0 w-80 h-80 rounded-full bg-white/[0.03] -translate-x-1/2 -translate-y-1/3" />
          <div className="absolute bottom-0 right-0 w-96 h-96 rounded-full bg-white/[0.03] translate-x-1/3 translate-y-1/3" />
          <div className="absolute top-1/2 left-1/2 w-64 h-64 rounded-full bg-zarin-green/[0.06] -translate-x-1/2 -translate-y-1/2" />
        </div>

        {/* Logo area */}
        <div className="relative z-10">
          <div className="mb-12 flex flex-col items-start gap-2">
            <ZarinpalLogo className="h-24 w-20 rounded-lg bg-white p-1.5 ring-1 ring-white/15 ring-inset" />
            <div>
              <div className="text-white/50 text-xs font-medium">پلتفرم هوشمند پرداخت</div>
            </div>
          </div>

          <h2 className="text-white text-3xl font-black leading-snug mb-4 tracking-tight">
            داشبورد تحلیلی<br />
            <span className="text-zarin-green">پذیرندگان</span>
          </h2>
          <p className="text-white/60 text-sm leading-relaxed max-w-xs">
            مدیریت تراکنش‌ها، تحلیل عملکرد و بینش‌های هوشمند برای کسب‌وکار شما.
          </p>
        </div>

        {/* Trust badges */}
        <div className="relative z-10 space-y-4 w-full">
          {[
            { icon: ShieldCheck, label: 'امنیت پرداخت', desc: 'رمزگذاری کامل اطلاعات بانکی' },
            { icon: Zap,         label: 'مسیردهی هوشمند', desc: 'اتصال به ۶ درگاه معتبر بانکی' },
            { icon: HeadphonesIcon, label: 'پشتیبانی ۲۴/۷', desc: 'همیشه در دسترس هستیم' },
          ].map(({ icon: Icon, label, desc }) => (
            <div key={label} className="flex items-center gap-3">
              <div className="flex size-9 shrink-0 items-center justify-center rounded-xl bg-white/10 ring-1 ring-white/10">
                <Icon className="size-4 text-zarin-green" strokeWidth={2} />
              </div>
              <div>
                <div className="text-white text-sm font-bold leading-tight">{label}</div>
                <div className="text-white/45 text-xs">{desc}</div>
              </div>
            </div>
          ))}
        </div>

        {/* Footer credit */}
        <div className="relative z-10 text-white/25 text-xs">
          © زرین‌پال ۱۴۰۵ — اولین پرداخت‌یار کشور
        </div>
      </div>

      {/* ── Right panel: Login form ── */}
      <div className="flex-1 flex items-center justify-center px-5 py-10 relative">
        {/* Ambient bg */}
        <div className="pointer-events-none absolute inset-0">
          <div className="app-backdrop absolute inset-0" />
          <div className="app-dots absolute inset-0" />
          <div className="app-noise absolute inset-0" />
        </div>

        <div className="relative w-full max-w-md animate-scale-in">
          {/* Mobile logo (visible only below lg) */}
          <div className="lg:hidden mb-8 text-center">
            <ZarinpalLogo className="mx-auto mb-4 h-28 w-22 rounded-lg bg-white p-2 shadow-sm ring-2 ring-zarin-green/20" />
            <h1 className="text-xl font-black tracking-tight text-foreground">داشبورد تحلیلی زرین‌پال</h1>
            <p className="mt-1.5 text-sm text-muted-foreground">ورود به پنل پذیرنده</p>
          </div>

          {/* Desktop heading */}
          <div className="hidden lg:block mb-8">
            <h1 className="text-2xl font-black tracking-tight text-foreground mb-1.5">
              خوش آمدید 👋
            </h1>
            <p className="text-muted-foreground text-sm">برای ادامه وارد پنل پذیرنده شوید.</p>
          </div>

          {/* Card */}
          <div className="card-glass rounded-2xl p-8 border border-white/50">
            <form onSubmit={submit} className="space-y-5">
              {/* Email field */}
              <div className="space-y-2">
                <Label htmlFor="email" className="text-sm font-bold text-foreground">
                  ایمیل
                </Label>
                <Input
                  id="email"
                  name="email"
                  type="email"
                  required
                  value={email}
                  onChange={(e) => setEmail(e.target.value)}
                  className="input-zarin h-12 rounded-xl border-border bg-white/80 text-sm px-4 font-medium placeholder:text-muted-foreground/60"
                  placeholder="merchant@example.com"
                  dir="ltr"
                />
              </div>

              {/* Password field */}
              <div className="space-y-2">
                <div className="flex items-center justify-between">
                  <Label htmlFor="password" className="text-sm font-bold text-foreground">
                    رمز عبور
                  </Label>
                  <button
                    type="button"
                    className="text-xs text-primary font-semibold hover:underline"
                    tabIndex={-1}
                  >
                    فراموشی رمز
                  </button>
                </div>
                <Input
                  id="password"
                  name="password"
                  type="password"
                  required
                  value={password}
                  onChange={(e) => setPassword(e.target.value)}
                  className="input-zarin h-12 rounded-xl border-border bg-white/80 text-sm px-4 font-medium placeholder:text-muted-foreground/60"
                  placeholder="••••••••"
                  dir="ltr"
                />
              </div>

              {/* Error message */}
              {loginError && (
                <div className={cn(
                  "flex items-center gap-2.5 rounded-xl border px-4 py-3 text-sm font-medium animate-fade-in",
                  lockoutRetryAfter && countdown > 0
                    ? "border-amber-200 bg-amber-50 text-amber-700"
                    : "border-destructive/25 bg-destructive/8 text-destructive"
                )}>
                  <AlertTriangle className="size-4 shrink-0" />
                  <span>
                    {loginError}
                    {lockoutRetryAfter && countdown > 0 && (
                      <span className="mr-1.5 inline-flex items-center gap-1 font-black">
                        <Clock className="size-3.5" />
                        {Math.floor(countdown / 60)}:{String(countdown % 60).padStart(2, '0')}
                      </span>
                    )}
                  </span>
                </div>
              )}

              {/* Submit button */}
              <button
                type="submit"
                disabled={isLoggingIn}
                className="btn-zarin-primary w-full h-12 rounded-xl flex items-center justify-center gap-2 text-sm font-bold disabled:opacity-70 disabled:cursor-not-allowed"
              >
                {isLoggingIn ? (
                  <>
                    <span className="size-4 animate-spin rounded-full border-2 border-white border-t-transparent" />
                    در حال ورود...
                  </>
                ) : (
                  <>
                    ورود به پنل
                    <ArrowLeft className="size-4" />
                  </>
                )}
              </button>

              {/* Demo note */}
              <p className="text-center text-xs leading-relaxed text-muted-foreground/60 pt-1">
                حالت نمایشی — با هر اطلاعاتی وارد می‌شوید
              </p>
            </form>
          </div>

          {/* Footer */}
          <p className="mt-6 text-center text-xs text-muted-foreground/45">
            زرین‌پال · اولین پرداخت‌یار ایران · پشتیبانی: ۴۵۶۲۸۰۰۰-۰۲۱
          </p>
        </div>
      </div>
    </div>
  )
}

export default LoginScreen
