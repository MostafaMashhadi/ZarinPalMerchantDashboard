import { useDispatch, useSelector } from 'react-redux'
import { useEffect } from 'react'
import type { RootState, AppDispatch } from '../store/store'
import { fetchInsights } from '../store/insightsSlice'
import InsightsPanel from '../components/InsightsPanel'

const InsightsListPage: React.FC = () => {
  const dispatch = useDispatch<AppDispatch>()
  const merchantRef = useSelector((state: RootState) => state.dashboard.selectedMerchant)
  const { filters, currentPage } = useSelector((state: RootState) => state.insights)

  useEffect(() => {
    dispatch(fetchInsights(merchantRef))
  }, [dispatch, merchantRef, currentPage, filters])

  return <InsightsPanel />
}

export default InsightsListPage
