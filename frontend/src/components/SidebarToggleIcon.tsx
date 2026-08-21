import * as React from "react"
import { cn } from "@/lib/utils"

interface SidebarToggleIconProps extends React.SVGProps<SVGSVGElement> {
  /** `true` renders the expanded (two-panel) icon, `false` the collapsed (single-panel) icon. */
  open?: boolean
}

/**
 * Animated sidebar open/closed toggle.
 *
 * The icon is a two-panel layout: a fixed sidebar strip on the left and a
 * content panel on the right. Toggling `open` scales the content panel toward
 * the divider (`scale-x` from `100%` → `0%`), producing a clean morph between
 * the expanded and collapsed states instead of a hard swap.
 */
export function SidebarToggleIcon({
  open = true,
  className,
  ...props
}: SidebarToggleIconProps) {
  return (
    <svg
      viewBox="0 0 24 24"
      width="1em"
      height="1em"
      fill="none"
      stroke="currentColor"
      strokeWidth={2}
      strokeLinecap="round"
      strokeLinejoin="round"
      aria-hidden="true"
      className={cn("shrink-0 rtl:-scale-x-100", className)}
      {...props}
    >
      {/* Sidebar strip — always present */}
      <rect x="3" y="4" width="6.5" height="16" rx="1.5" />

      {/* Content panel — collapses toward the divider when closed */}
      <rect
        x="11"
        y="4"
        width="10"
        height="16"
        rx="1.5"
        data-open={open}
        className={cn(
          "origin-left [transform-box:fill-box]",
          "transition-[transform,opacity] duration-300 ease-[cubic-bezier(0.4,0,0.2,1)]",
          "motion-reduce:transition-none",
          "data-[open=true]:scale-x-100 data-[open=true]:opacity-100",
          "data-[open=false]:scale-x-0 data-[open=false]:opacity-0"
        )}
      />
    </svg>
  )
}

export default SidebarToggleIcon
