import type { HTMLAttributes, ReactNode } from 'react'

import { cn } from '../../utils/cn'

interface CardProps extends HTMLAttributes<HTMLDivElement> {
  children: ReactNode
}

export const Card = ({ children, className, ...props }: CardProps) => (
  <div className={cn('card', className)} {...props}>
    {children}
  </div>
)

export const CardHeader = ({
  title,
  subtitle,
  action,
  icon,
}: {
  title: string
  subtitle?: string
  action?: ReactNode
  icon?: ReactNode
}) => (
  <div className="flex flex-wrap items-start justify-between gap-3 border-b border-slate-100 px-5 py-4">
    <div className="flex items-start gap-3">
      {icon && (
        <span className="mt-0.5 flex h-9 w-9 items-center justify-center rounded-xl bg-brand-50 text-brand-600">
          {icon}
        </span>
      )}
      <div>
        <h2 className="font-display text-base font-bold text-ink-900">{title}</h2>
        {subtitle && <p className="mt-0.5 text-sm text-slate-500">{subtitle}</p>}
      </div>
    </div>
    {action}
  </div>
)

export const CardBody = ({ children, className }: { children: ReactNode; className?: string }) => (
  <div className={cn('px-5 py-5', className)}>{children}</div>
)
