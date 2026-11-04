export const formatMoney = (
  value: string | number | null | undefined,
  currency = 'USD',
  options: Intl.NumberFormatOptions = {},
): string => {
  if (value === null || value === undefined || value === '') return '—'
  const numeric = typeof value === 'number' ? value : Number(value)
  if (Number.isNaN(numeric)) return '—'
  return new Intl.NumberFormat('fr-FR', {
    style: 'currency',
    currency: currency || 'USD',
    minimumFractionDigits: 2,
    maximumFractionDigits: 2,
    ...options,
  }).format(numeric)
}

export const formatNumber = (value: string | number | null | undefined): string => {
  if (value === null || value === undefined || value === '') return '—'
  const numeric = typeof value === 'number' ? value : Number(value)
  if (Number.isNaN(numeric)) return '—'
  return new Intl.NumberFormat('fr-FR', {
    minimumFractionDigits: 2,
    maximumFractionDigits: 2,
  }).format(numeric)
}

export const formatDate = (value: string | null | undefined): string => {
  if (!value) return '—'
  const date = new Date(value)
  if (Number.isNaN(date.getTime())) return '—'
  return new Intl.DateTimeFormat('fr-FR', {
    day: '2-digit',
    month: '2-digit',
    year: 'numeric',
  }).format(date)
}

export const formatDateTime = (value: string | null | undefined): string => {
  if (!value) return '—'
  const date = new Date(value)
  if (Number.isNaN(date.getTime())) return '—'
  return new Intl.DateTimeFormat('fr-FR', {
    day: '2-digit',
    month: 'short',
    year: 'numeric',
    hour: '2-digit',
    minute: '2-digit',
  }).format(date)
}

export const formatMonth = (period: string): string => {
  const [year, month] = period.split('-')
  if (!year || !month) return period
  const date = new Date(Number(year), Number(month) - 1, 1)
  return new Intl.DateTimeFormat('fr-FR', { month: 'short', year: 'numeric' }).format(date)
}

export const relativeTime = (value: string | null | undefined): string => {
  if (!value) return 'jamais'
  const date = new Date(value).getTime()
  if (Number.isNaN(date)) return '—'
  const diff = Math.round((date - Date.now()) / 1000)
  const units: [Intl.RelativeTimeFormatUnit, number][] = [
    ['year', 31536000],
    ['month', 2592000],
    ['day', 86400],
    ['hour', 3600],
    ['minute', 60],
    ['second', 1],
  ]
  const formatter = new Intl.RelativeTimeFormat('fr-FR', { numeric: 'auto' })
  for (const [unit, seconds] of units) {
    if (Math.abs(diff) >= seconds || unit === 'second') {
      return formatter.format(Math.round(diff / seconds), unit)
    }
  }
  return '—'
}

export const todayISO = (): string => new Date().toISOString().slice(0, 10)

export const getInitials = (name: string): string =>
  name
    .split(/[\s._-]+/)
    .filter(Boolean)
    .slice(0, 2)
    .map((part) => part[0]?.toUpperCase() ?? '')
    .join('') || '?'
