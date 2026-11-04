import { AlertCircle, Inbox, Loader2, RefreshCw } from 'lucide-react'
import type { ReactNode } from 'react'

import { cn } from '../../utils/cn'
import { Button } from './Button'

export const Spinner = ({ label = 'Chargement…' }: { label?: string }) => (
  <div className="flex items-center justify-center gap-3 py-12 text-sm text-slate-500" role="status">
    <Loader2 className="h-5 w-5 animate-spin text-brand-600" aria-hidden />
    <span>{label}</span>
  </div>
)

export const EmptyState = ({
  title,
  description,
  action,
  icon,
}: {
  title: string
  description?: string
  action?: ReactNode
  icon?: ReactNode
}) => (
  <div className="flex flex-col items-center justify-center px-6 py-14 text-center">
    <div className="flex h-14 w-14 items-center justify-center rounded-2xl bg-slate-100 text-slate-400">
      {icon ?? <Inbox className="h-7 w-7" />}
    </div>
    <h3 className="mt-4 font-display text-base font-bold text-ink-900">{title}</h3>
    {description && <p className="mt-1 max-w-sm text-sm text-slate-500">{description}</p>}
    {action && <div className="mt-5">{action}</div>}
  </div>
)

export const ErrorState = ({
  message,
  onRetry,
  className,
}: {
  message: string
  onRetry?: () => void
  className?: string
}) => (
  <div className={cn('flex flex-col items-center justify-center px-6 py-12 text-center', className)}>
    <div className="flex h-12 w-12 items-center justify-center rounded-2xl bg-red-50 text-red-500">
      <AlertCircle className="h-6 w-6" />
    </div>
    <p className="mt-3 max-w-md text-sm text-ink-600">{message}</p>
    {onRetry && (
      <Button variant="secondary" size="sm" className="mt-4" onClick={onRetry} icon={<RefreshCw className="h-4 w-4" />}>
        Réessayer
      </Button>
    )}
  </div>
)
