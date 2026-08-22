import type { HTMLAttributes } from 'react'
import { cn } from '@/lib/utils'
import logoSrc from '@/assets/dybug_payment_zarinpal.svg'

type ZarinpalLogoProps = HTMLAttributes<HTMLSpanElement>

const ZarinpalLogo = ({ className, ...props }: ZarinpalLogoProps) => (
  <span
    className={cn('inline-flex shrink-0 items-center justify-center overflow-hidden', className)}
    {...props}
  >
    <img src={logoSrc} alt="" aria-hidden="true" className="h-full w-full object-contain" />
  </span>
)

export default ZarinpalLogo
