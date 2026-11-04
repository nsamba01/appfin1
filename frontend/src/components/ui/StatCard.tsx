import type { ReactNode } from 'react'

import { cn } from '../../utils/cn'

type Tone = 'brand' | 'success' | 'danger' | 'neutral' | 'warning'

const TONES: Record<Tone, { icon: string; value: string; accent: string }> = {
  brand: { icon: 'bg-brand-50 text-brand-600', value: 'text-ink-900', accent: 'from-brand-500' },
  success: { icon: 'bg-emerald-50 text-emerald-600', value: 'text-emerald-700', accent: 'from-emerald-500' },
  danger: { icon: 'bg-red-50 text-red-600', value: 'text-red-700', accent: 'from-red-500' },
  neutral: { icon: 'bg-slate-100 text-slate-600', value: 'text-ink-900', accent: 'from-slate-400' },
  warning: { icon: 'bg-amber-50 text-amber-600', value: 'text-amber-700', accent: 'from-amber-500' },
}

export const StatCard = ({
  label,
  value,
  hint,
  icon,
  tone = 'brand',
  badge,
  loading,
}: {
  label: string
  value: ReactNode
  hint?: ReactNode
  icon: ReactNode
  tone?: Tone
  badge?: ReactNode
  loading?: boolean
}) => {
  const styles = TONES[tone]
  return (
    <div className="card group relative overflow-hidden p-5 transition hover:shadow-lift">
      <div
        className={cn(
          'absolute inset-x-0 top-0 h-0.5 bg-gradient-to-r to-transparent opacity-70',
          styles.accent,
        )}
        aria-hidden
      />
      <div className="flex items-start justify-between gap-3">
        <div className="min-w-0">
          <p className="text-xs font-semibold uppercase tracking-wide text-slate-500">{label}</p>
          {loading ? (
            <div className="skeleton mt-3 h-8 w-32" />
          ) : (
            <p className={cn('mt-2 truncate font-display text-2xl font-bold tabular-nums', styles.value)}>
              {value}
            </p>
          )}
          {hint && <p className="mt-1.5 truncate text-xs text-slate-500">{hint}</p>}
        </div>
        <div className={cn('flex h-11 w-11 shrink-0 items-center justify-center rounded-xl', styles.icon)}>
          {icon}
        </div>
      </div>
      {badge && <div className="mt-3">{badge}</div>}
    </div>
  )
}
