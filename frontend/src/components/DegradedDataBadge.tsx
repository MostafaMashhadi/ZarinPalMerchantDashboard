import React from 'react'
import { CloudOff } from 'lucide-react'
import { Badge } from '@/components/ui/badge'

interface DegradedDataBadgeProps {
  message?: string
}

const DegradedDataBadge: React.FC<DegradedDataBadgeProps> = ({ message }) => {
  return (
    <Badge variant="outline" className="w-fit gap-1.5 border-accent/30 bg-accent/10 px-2 py-1 text-xs text-accent" role="status">
      <CloudOff aria-hidden="true" />
      {message ?? 'این اعداد از داده کش‌شده نمایش داده می‌شوند — ممکن است کمی قدیمی باشند'}
    </Badge>
  )
}

export default DegradedDataBadge
