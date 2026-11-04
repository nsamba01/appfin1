import { ChevronLeft, ChevronRight } from 'lucide-react'

import { Button } from './Button'

export const Pagination = ({
  page,
  pageSize,
  count,
  onPageChange,
}: {
  page: number
  pageSize: number
  count: number
  onPageChange: (page: number) => void
}) => {
  const totalPages = Math.max(1, Math.ceil(count / pageSize))
  if (count === 0) return null
  const from = (page - 1) * pageSize + 1
  const to = Math.min(page * pageSize, count)

  return (
    <div className="flex flex-wrap items-center justify-between gap-3 border-t border-slate-100 px-5 py-3.5">
      <p className="text-sm text-slate-500">
        <span className="font-semibold text-ink-700">{from}</span>–
        <span className="font-semibold text-ink-700">{to}</span> sur{' '}
        <span className="font-semibold text-ink-700">{count}</span>
      </p>
      <div className="flex items-center gap-2">
        <Button
          variant="secondary"
          size="sm"
          onClick={() => onPageChange(page - 1)}
          disabled={page <= 1}
          icon={<ChevronLeft className="h-4 w-4" />}
          aria-label="Page précédente"
        >
          Précédent
        </Button>
        <span className="px-1 text-sm text-slate-500">
          {page} / {totalPages}
        </span>
        <Button
          variant="secondary"
          size="sm"
          onClick={() => onPageChange(page + 1)}
          disabled={page >= totalPages}
          aria-label="Page suivante"
        >
          Suivant
          <ChevronRight className="h-4 w-4" />
        </Button>
      </div>
    </div>
  )
}
