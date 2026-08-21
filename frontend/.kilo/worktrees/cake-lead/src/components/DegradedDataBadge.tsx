import React from 'react'
import { CloudOff } from 'lucide-react'

interface DegradedDataBadgeProps {
  message?: string
}

const DegradedDataBadge: React.FC<DegradedDataBadgeProps> = ({ message }) => {
  return (
    <div className="flex items-center gap-2 rounded-2xl border border-amber-200 bg-amber-50 px-4 py-2.5 text-[11px] font-bold text-amber-700" role="status">
      <CloudOff className="size-3.5 shrink-0" />
      {message ?? 'این اعداد از داده کش‌شده نمایش داده می‌شوند — ممکن است کمی قدیمی باشند'}
    </div>
  )
}

export default DegradedDataBadge
