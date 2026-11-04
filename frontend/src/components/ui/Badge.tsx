import type { ReactNode } from 'react'

import { cn } from '../../utils/cn'

type Tone = 'neutral' | 'success' | 'danger' | 'warning' | 'info' | 'brand'

const TONES: Record<Tone, string> = {
  neutral: 'bg-slate-100 text-slate-700 ring-slate-200',
  success: 'bg-emerald-50 text-emerald-700 ring-emerald-200',
  danger: 'bg-red-50 text-red-700 ring-red-200',
  warning: 'bg-amber-50 text-amber-800 ring-amber-200',
  info: 'bg-sky-50 text-sky-700 ring-sky-200',
  brand: 'bg-brand-50 text-brand-700 ring-brand-200',
}

export const Badge = ({
  children,
  tone = 'neutral',
  className,
  dot = false,
}: {
  children: ReactNode
  tone?: Tone
  className?: string
  dot?: boolean
}) => (
  <span
    className={cn(
      'inline-flex items-center gap-1.5 rounded-full px-2.5 py-1 text-xs font-semibold ring-1 ring-inset',
      TONES[tone],
      className,
    )}
  >
    {dot && <span className="h-1.5 w-1.5 rounded-full bg-current" aria-hidden />}
    {children}
  </span>
)
