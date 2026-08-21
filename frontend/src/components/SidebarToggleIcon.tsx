import * as React from "react"
import { cn } from "@/lib/utils"
import { SidebarPanelIcon } from './ZarinpalIcons'

interface SidebarToggleIconProps extends React.SVGProps<SVGSVGElement> {
  /** `true` renders the expanded (two-panel) icon, `false` the collapsed (single-panel) icon. */
  open?: boolean
}

export function SidebarToggleIcon({
  open = true,
  className,
  ...props
}: SidebarToggleIconProps) {
  return <SidebarPanelIcon open={open} className={cn("shrink-0 rtl:-scale-x-100", className)} {...props} />
}

export default SidebarToggleIcon
