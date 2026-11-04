import type { ReactNode } from 'react'

export const PageHeader = ({
  title,
  description,
  actions,
  eyebrow,
}: {
  title: string
  description?: string
  actions?: ReactNode
  eyebrow?: string
}) => (
  <div className="mb-6 flex flex-col gap-4 sm:flex-row sm:items-end sm:justify-between">
    <div>
      {eyebrow && (
        <p className="mb-1 text-xs font-semibold uppercase tracking-[0.12em] text-brand-600">{eyebrow}</p>
      )}
      <h1 className="font-display text-2xl font-bold tracking-tight text-ink-900 sm:text-[28px]">
        {title}
      </h1>
      {description && <p className="mt-1.5 max-w-2xl text-sm text-slate-500">{description}</p>}
    </div>
    {actions && <div className="flex flex-wrap items-center gap-3">{actions}</div>}
  </div>
)
