import { CheckCircle2, Info, X, XCircle } from 'lucide-react'
import {
  createContext,
  useCallback,
  useContext,
  useEffect,
  useMemo,
  useRef,
  useState,
  type ReactNode,
} from 'react'

import { cn } from '../utils/cn'

type ToastVariant = 'success' | 'error' | 'info'

interface Toast {
  id: number
  title: string
  description?: string
  variant: ToastVariant
}

interface ToastContextValue {
  notify: (variant: ToastVariant, title: string, description?: string) => void
  success: (title: string, description?: string) => void
  error: (title: string, description?: string) => void
  info: (title: string, description?: string) => void
}

const ToastContext = createContext<ToastContextValue | undefined>(undefined)

const ICONS = {
  success: CheckCircle2,
  error: XCircle,
  info: Info,
}

const STYLES: Record<ToastVariant, string> = {
  success: 'border-emerald-200 bg-emerald-50 text-emerald-900',
  error: 'border-red-200 bg-red-50 text-red-900',
  info: 'border-blue-200 bg-blue-50 text-blue-900',
}

const ICON_STYLES: Record<ToastVariant, string> = {
  success: 'text-emerald-600',
  error: 'text-red-600',
  info: 'text-blue-600',
}

export function ToastProvider({ children }: { children: ReactNode }) {
  const [toasts, setToasts] = useState<Toast[]>([])
  const counter = useRef(0)
  const timers = useRef<number[]>([])

  const dismiss = useCallback((id: number) => {
    setToasts((current) => current.filter((toast) => toast.id !== id))
  }, [])

  const notify = useCallback(
    (variant: ToastVariant, title: string, description?: string) => {
      counter.current += 1
      const id = counter.current
      setToasts((current) => [...current, { id, title, description, variant }])
      const timer = window.setTimeout(() => dismiss(id), variant === 'error' ? 7000 : 4500)
      timers.current.push(timer)
    },
    [dismiss],
  )

  useEffect(() => {
    return () => {
      timers.current.forEach((timer) => window.clearTimeout(timer))
    }
  }, [])

  const value = useMemo<ToastContextValue>(
    () => ({
      notify,
      success: (title, description) => notify('success', title, description),
      error: (title, description) => notify('error', title, description),
      info: (title, description) => notify('info', title, description),
    }),
    [notify],
  )

  return (
    <ToastContext.Provider value={value}>
      {children}
      <div
        className="pointer-events-none fixed inset-x-4 top-4 z-[100] flex flex-col items-end gap-3 sm:inset-x-auto sm:right-6 sm:top-6"
        role="region"
        aria-label="Notifications"
        aria-live="polite"
      >
        {toasts.map((toast) => {
          const Icon = ICONS[toast.variant]
          return (
            <div
              key={toast.id}
              role="status"
              className={cn(
                'pointer-events-auto flex w-full max-w-sm items-start gap-3 rounded-xl border p-4 shadow-lift animate-slide-in',
                STYLES[toast.variant],
              )}
            >
              <Icon className={cn('mt-0.5 h-5 w-5 shrink-0', ICON_STYLES[toast.variant])} />
              <div className="flex-1">
                <p className="text-sm font-semibold">{toast.title}</p>
                {toast.description && (
                  <p className="mt-1 text-sm opacity-80">{toast.description}</p>
                )}
              </div>
              <button
                type="button"
                onClick={() => dismiss(toast.id)}
                className="rounded-md p-1 opacity-60 transition hover:bg-black/5 hover:opacity-100 focus:outline-none focus-visible:ring-2 focus-visible:ring-brand-500"
                aria-label="Fermer la notification"
              >
                <X className="h-4 w-4" />
              </button>
            </div>
          )
        })}
      </div>
    </ToastContext.Provider>
  )
}

export const useToast = (): ToastContextValue => {
  const context = useContext(ToastContext)
  if (!context) throw new Error('useToast must be used inside <ToastProvider>')
  return context
}
