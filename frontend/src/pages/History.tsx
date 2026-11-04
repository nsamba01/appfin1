import { Activity, Search } from 'lucide-react'
import { useCallback, useEffect, useState } from 'react'

import { Badge } from '../components/ui/Badge'
import { Card } from '../components/ui/Card'
import { EmptyState, ErrorState, Spinner } from '../components/ui/Feedback'
import { Input } from '../components/ui/Field'
import { PageHeader } from '../components/ui/PageHeader'
import { Pagination } from '../components/ui/Pagination'
import { extractErrorMessage } from '../services/api'
import { adminService } from '../services/admin'
import type { AuditEntry } from '../types'
import { formatDateTime } from '../utils/format'

const PAGE_SIZE = 25

const TONES: Record<string, 'success' | 'danger' | 'warning' | 'info' | 'neutral' | 'brand'> = {
  OPERATION_CREATED: 'success',
  OPERATION_UPDATED: 'info',
  OPERATION_DELETED: 'danger',
  EXPORT_GENERATED: 'brand',
}

export const HistoryPage = () => {
  const [entries, setEntries] = useState<AuditEntry[]>([])
  const [count, setCount] = useState(0)
  const [page, setPage] = useState(1)
  const [search, setSearch] = useState('')
  const [debounced, setDebounced] = useState('')
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState('')

  useEffect(() => {
    const timer = window.setTimeout(() => {
      setDebounced(search.trim())
      setPage(1)
    }, 350)
    return () => window.clearTimeout(timer)
  }, [search])

  const load = useCallback(async () => {
    setLoading(true)
    setError('')
    try {
      const data = await adminService.financeHistory({ search: debounced || undefined, page })
      setEntries(data.results)
      setCount(data.count)
    } catch (err) {
      setError(extractErrorMessage(err, "Impossible de charger l'historique financier."))
    } finally {
      setLoading(false)
    }
  }, [debounced, page])

  useEffect(() => {
    void load()
  }, [load])

  return (
    <div className="animate-fade-in">
      <PageHeader
        eyebrow="Traçabilité"
        title="Historique financier"
        description="Toutes les créations, modifications et archivages d'opérations sont conservés."
        actions={
          <div className="w-full sm:w-72">
            <Input
              aria-label="Rechercher dans l'historique"
              placeholder="Rechercher…"
              value={search}
              onChange={(event) => setSearch(event.target.value)}
              icon={<Search className="h-4 w-4" />}
            />
          </div>
        }
      />

      <Card>
        {loading ? (
          <Spinner label="Chargement de l'historique…" />
        ) : error ? (
          <ErrorState message={error} onRetry={() => void load()} />
        ) : entries.length === 0 ? (
          <EmptyState
            title="Aucun évènement"
            description="Les évènements apparaîtront dès la première opération financière."
            icon={<Activity className="h-7 w-7" />}
          />
        ) : (
          <>
            <ul className="divide-y divide-slate-100">
              {entries.map((entry) => (
                <li key={entry.id} className="flex flex-wrap items-start gap-4 px-5 py-4 hover:bg-slate-50/60">
                  <span className="mt-0.5 flex h-10 w-10 shrink-0 items-center justify-center rounded-xl bg-slate-100 text-slate-500">
                    <Activity className="h-5 w-5" />
                  </span>
                  <div className="min-w-0 flex-1">
                    <div className="flex flex-wrap items-center gap-2">
                      <Badge tone={TONES[entry.action] ?? 'neutral'}>{entry.action_label}</Badge>
                      <span className="text-xs text-slate-400">#{entry.entity_id}</span>
                    </div>
                    <p className="mt-1.5 text-sm text-ink-800">{entry.description}</p>
                    <p className="mt-0.5 text-xs text-slate-500">
                      {entry.actor_username || 'système'} · {formatDateTime(entry.created_at)}
                      {entry.ip_address ? ` · ${entry.ip_address}` : ''}
                    </p>
                  </div>
                </li>
              ))}
            </ul>
            <Pagination page={page} pageSize={PAGE_SIZE} count={count} onPageChange={setPage} />
          </>
        )}
      </Card>
    </div>
  )
}
