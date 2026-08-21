import type React from 'react'

type IconProps = React.SVGProps<SVGSVGElement>

function IconFrame({ children, ...props }: IconProps) {
  return (
    <svg
      viewBox="0 0 24 24"
      fill="none"
      stroke="currentColor"
      strokeWidth="1.5"
      strokeLinecap="round"
      strokeLinejoin="round"
      aria-hidden="true"
      {...props}
    >
      {children}
    </svg>
  )
}

// Zarinpal's public UI uses compact 24px inline SVGs with a 1.5px rounded stroke.
export const DashboardIcon = (props: IconProps) => <IconFrame {...props}><rect x="3.5" y="3.5" width="7" height="7" rx="1" /><rect x="13.5" y="3.5" width="7" height="7" rx="1" /><rect x="3.5" y="13.5" width="7" height="7" rx="1" /><path d="M14 19.5v-3.2a1.8 1.8 0 0 1 3.6 0v3.2" /><path d="M13.5 20.5h7" /></IconFrame>

export const InsightsIcon = (props: IconProps) => <IconFrame {...props}><path d="M9.4 18.5h5.2" /><path d="M10 21h4" /><path d="M8.4 15.8C6.9 14.7 6 12.9 6 10.8a6 6 0 1 1 12 0c0 2.1-.9 3.9-2.4 5" /><path d="M8.4 15.8h7.2" /></IconFrame>

export const AnalyticsIcon = (props: IconProps) => <IconFrame {...props}><path d="M4 19.5V4.5" /><path d="M4 19.5h16" /><path d="m7.5 15 3-3 2.7 1.8 4.3-5.3" /><circle cx="7.5" cy="15" r=".75" fill="currentColor" stroke="none" /><circle cx="10.5" cy="12" r=".75" fill="currentColor" stroke="none" /><circle cx="13.2" cy="13.8" r=".75" fill="currentColor" stroke="none" /><circle cx="17.5" cy="8.5" r=".75" fill="currentColor" stroke="none" /></IconFrame>

export const WalletIcon = (props: IconProps) => <IconFrame {...props}><path d="M4.5 7.5h14a1.5 1.5 0 0 1 1.5 1.5v9a1.5 1.5 0 0 1-1.5 1.5h-14A1.5 1.5 0 0 1 3 18V6a1.5 1.5 0 0 1 1.5-1.5h12" /><path d="M16.5 13.5h3.5" /><circle cx="16.5" cy="13.5" r=".75" fill="currentColor" stroke="none" /></IconFrame>

export const StorefrontIcon = (props: IconProps) => <IconFrame {...props}><path d="M4 10.5h16" /><path d="M5.5 10.5v8.8a1.2 1.2 0 0 0 1.2 1.2h10.6a1.2 1.2 0 0 0 1.2-1.2v-8.8" /><path d="m5 10.5 1.3-5h11.4l1.3 5" /><path d="M9 20.5v-5h6v5" /></IconFrame>

export const ChevronDownIcon = (props: IconProps) => <IconFrame {...props}><path d="m16 10-4 4-4-4" /></IconFrame>

export const SidebarPanelIcon = ({ open = true, ...props }: IconProps & { open?: boolean }) => <IconFrame {...props}><rect x="3.5" y="4" width="17" height="16" rx="1.5" /><path d="M10 4v16" /><path d={open ? 'm15 9-3 3 3 3' : 'm13 9 3 3-3 3'} /></IconFrame>
