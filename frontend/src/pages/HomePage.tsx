import { ArrowLeft, ChartNoAxesCombined, Sparkles } from 'lucide-react'
import { Link } from 'react-router-dom'
import { Button } from '@/components/ui/button'
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card'

export default function HomePage() {
  return (
    <main className="dashboard-home grid min-h-dvh place-items-center px-5 py-10" dir="rtl">
      <section className="grid w-full max-w-5xl gap-5 lg:grid-cols-[1.2fr_0.8fr]" aria-labelledby="dashboard-title">
        <div className="flex flex-col justify-between gap-12 rounded-3xl border border-border bg-card/80 p-8 shadow-2xl backdrop-blur-xl sm:p-12">
          <div className="flex flex-col gap-6">
            <div className="flex size-12 items-center justify-center rounded-2xl bg-primary text-primary-foreground shadow-lg shadow-primary/20">
              <ChartNoAxesCombined aria-hidden="true" />
            </div>
            <div className="flex flex-col gap-3">
              <p className="text-sm font-semibold text-primary">زرین‌پال برای پذیرندگان</p>
              <h1 id="dashboard-title" className="text-balance text-4xl font-bold tracking-tight text-foreground sm:text-5xl">
                ZarinPal Merchant Dashboard
              </h1>
              <p className="max-w-xl text-base leading-8 text-muted-foreground">
                نمایی روشن از پرداخت‌ها، بینش‌های هوشمند و هزینه‌های عملیاتی شما؛ در یک فضای متمرکز و سریع.
              </p>
            </div>
          </div>
          <div className="flex flex-wrap gap-3">
            <Button asChild size="lg">
              <Link to="/login">
                ورود به داشبورد
                <ArrowLeft data-icon="inline-end" aria-hidden="true" />
              </Link>
            </Button>
            <Button asChild variant="outline" size="lg">
              <Link to="/dashboard">مشاهده نمونه</Link>
            </Button>
          </div>
        </div>

        <Card className="border-primary/20 bg-card/70 shadow-2xl backdrop-blur-xl">
          <CardHeader>
            <div className="flex size-10 items-center justify-center rounded-xl bg-muted text-primary">
              <Sparkles aria-hidden="true" />
            </div>
            <CardTitle className="mt-5 text-2xl">بستر آماده‌ی رشد</CardTitle>
            <CardDescription>زیرساخت رابط کاربری از روز اول برای داده و گفتگو آماده است.</CardDescription>
          </CardHeader>
          <CardContent>
            <dl className="grid gap-4 text-sm">
              <div className="rounded-xl bg-muted/60 p-4"><dt className="text-muted-foreground">دریافت داده</dt><dd className="mt-1 font-semibold">React Query + API layer</dd></div>
              <div className="rounded-xl bg-muted/60 p-4"><dt className="text-muted-foreground">گفتگو</dt><dd className="mt-1 font-semibold">SSE streaming seam</dd></div>
              <div className="rounded-xl bg-muted/60 p-4"><dt className="text-muted-foreground">ظاهر</dt><dd className="mt-1 font-semibold">Dark-first design tokens</dd></div>
            </dl>
          </CardContent>
        </Card>
      </section>
    </main>
  )
}
