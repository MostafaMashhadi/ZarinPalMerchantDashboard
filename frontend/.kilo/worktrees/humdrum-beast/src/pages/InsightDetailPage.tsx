import { useParams } from 'react-router-dom'
import InsightsPanel from '../components/InsightsPanel'

const InsightDetailPage: React.FC = () => {
  const { insightId } = useParams<{ insightId: string }>()

  return <InsightsPanel preselectedId={insightId ?? null} />
}

export default InsightDetailPage
