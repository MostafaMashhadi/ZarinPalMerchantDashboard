import { useDispatch, useSelector } from 'react-redux'
import type { RootState, AppDispatch } from '../store/store'
import { fetchDashboardSummary } from '../store/dashboardSlice'
import DashboardSummaryCards from '../components/DashboardSummaryCards'
import AgenticDigest from '../components/AgenticDigest'
import RecentInsightsWidget from '../components/RecentInsightsWidget'
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card'
import { Button } from '@/components/ui/button'
import { RotateCw } from 'lucide-react'

const DashboardSummaryPage: React.FC = () => {
  const dispatch = useDispatch<AppDispatch>()
  const { error, selectedMerchant } = useSelector((state: RootState) => state.dashboard)

  const handleRetry = () => {
    dispatch(fetchDashboardSummary(selectedMerchant))
  }

  return (
    <div className="space-y-6 lg:space-y-8 animate-fade-in">
      {error && (
        <Card className="border-destructive/25 bg-white shadow-sm rounded-2xl">
          <CardHeader className="pb-2">
            <CardTitle className="text-sm font-bold text-destructive">خطا در دریافت اطلاعات داشبورد</CardTitle>
            <CardDescription>{error}</CardDescription>
          </CardHeader>
          <CardContent>
            <Button size="sm" onClick={handleRetry} className="btn-zarin-primary gap-2 rounded-xl h-9 px-4 text-xs">
              <RotateCw className="size-3.5" />
              تلاش مجدد
            </Button>
          </CardContent>
        </Card>
      )}

      <DashboardSummaryCards />

      <div className="grid grid-cols-1 gap-6 lg:grid-cols-12">
        <div className="lg:col-span-4">
          <RecentInsightsWidget />
        </div>
        <div className="lg:col-span-8">
          <AgenticDigest />
        </div>
      </div>
    </div>
  )
}

export default DashboardSummaryPage