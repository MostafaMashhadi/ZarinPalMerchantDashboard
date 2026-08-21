export type Severity = 'info' | 'warning' | 'critical'

export const severityPresentation: Record<Severity, { label: string; className: string }> = {
  info: { label: 'اطلاع', className: 'border-primary/20 bg-primary/10 text-primary' },
  warning: { label: 'هشدار', className: 'border-accent/20 bg-accent/10 text-accent' },
  critical: { label: 'بحرانی', className: 'border-destructive/20 bg-destructive/10 text-destructive' },
}

export function severityFor(value: unknown): Severity {
  return value === 'critical' || value === 'warning' ? value : 'info'
}
