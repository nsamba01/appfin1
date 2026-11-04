import { KeyRound, ScrollText, Search, ShieldAlert, ShieldCheck } from 'lucide-react'
import { useCallback, useEffect, useState } from 'react'

import { Badge } from '../../components/ui/Badge'
import { Card, CardBody, CardHeader } from '../../components/ui/Card'
import { EmptyState, ErrorState, Spinner } from '../../components/ui/Feedback'
import { Input, Select } from '../../components/ui/Field'
import { PageHeader } from '../../components/ui/PageHeader'
import { Pagination } from '../../components/ui/Pagination'
import { extractErrorMessage } from '../../services/api'
import { adminService } from '../../services/admin'
import type { AuditEntry, LoginAttemptEntry } from '../../types'
import { formatDateTime } from '../../utils/format'

const PAGE_SIZE = 25

const ACTIONS = [
  { value: '', label: 'Toutes les actions' },
  { value: 'LOGIN_SUCCESS', label: 'Connexions réussies' },
  { value: 'LOGIN_FAILED', label: 'Connexions échouées' },
  { value: 'OPERATION_CREATED', label: 'Opérations créées' },
  { value: 'OPERATION_UPDATED', label: 'Opérations modifiées' },
  { value: 'OPERATION_DELETED', label: 'Opérations archivées' },
  { value: 'USER_CREATED', label: 'Utilisateurs créés' },
  { value: 'USER_UPDATED', label: 'Utilisateurs modifiés' },
  { value: 'PASSWORD_RESET', label: 'Mots de passe réinitialisés' },
  { value: 'BANK_CONFIG_UPDATED', label: 'Configuration bancaire' },
  { value: 'BANK_SYNC', label: 'Synchronisations bancaires' },
  { value: 'EXPORT_GENERATED', label: 'Exports' },
]

export const AdminAuditPage = () => {
  const [tab, setTab] = useState<'audit' | 'login'>('audit')
  const [entries, setEntries] = useState<AuditEntry[]>([])
  const [attempts, setAttempts] = useState<LoginAttemptEntry[]>([])
  const [count, setCount] = useState(0)
  const [page, setPage] = useState(1)
  const [search, setSearch] = useState('')
  const [action, setAction] = useState('')
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState('')

  const load = useCallback(async () => {
    setLoading(true)
    setError('')
    try {
      if (tab === 'audit') {
        const data = await adminService.auditLogs({
          search: search.trim() || undefined,
          action: action || undefined,
          page,
        })
        setEntries(data.results)
        setCount(data.count)
      } else {
        const data = await adminService.loginLogs({
          username: search.trim() || undefined,
          page,
        })
        setAttempts(data.results)
        setCount(data.count)
      }
    } catch (err) {
      setError(extractErrorMessage(err, 'Impossible de charger les journaux.'))
    } finally {
      setLoading(false)
    }
  }, [tab, search, action, page])

  useEffect(() => {
    const timer = window.setTimeout(() => void load(), 300)
    return () => window.clearTimeout(timer)
  }, [load])

  return (
    <div className="animate-fade-in">
      <PageHeader
        eyebrow="Espace administrateur"
        title="Journaux & audit"
        description="Traçabilité complète des connexions et des actions sensibles."
        actions={
          <div className="flex rounded-xl border border-slate-200 bg-white p-1 shadow-sm">
            {[
              { id: 'audit' as const, label: 'Journal d’audit', icon: ScrollText },
              { id: 'login' as const, label: 'Connexions', icon: ShieldCheck },
            ].map((item) => (
              <button
                key={item.id}
                type="button"
                onClick={() => {
                  setTab(item.id)
                  setPage(1)
                }}
                className={`inline-flex items-center gap-1.5 rounded-lg px-3 py-1.5 text-sm font-medium transition ${
                  tab === item.id ? 'bg-brand-600 text-white' : 'text-slate-600 hover:bg-slate-50'
                }`}
              >
                <item.icon className="h-4 w-4" />
                {item.label}
              </button>
            ))}
          </div>
        }
      />

      <Card className="mb-5 p-4">
        <div className="grid gap-3 sm:grid-cols-3">
          <div className={tab === 'audit' ? 'sm:col-span-2' : 'sm:col-span-3'}>
            <Input
              aria-label="Rechercher"
              placeholder={tab === 'audit' ? 'Rechercher une action, un acteur…' : 'Rechercher un identifiant…'}
              value={search}
              onChange={(event) => {
                setSearch(event.target.value)
                setPage(1)
              }}
              icon={<Search className="h-4 w-4" />}
            />
          </div>
          {tab === 'audit' && (
            <Select
              aria-label="Filtrer par action"
              value={action}
              onChange={(event) => {
                setAction(event.target.value)
                setPage(1)
              }}
              options={ACTIONS}
            />
          )}
        </div>
      </Card>

      {tab === 'login' && (
        <div className="mb-5 grid gap-4 sm:grid-cols-3">
          <Card className="px-5 py-4">
            <p className="text-[11px] font-semibold uppercase tracking-wide text-slate-400">
              Tentatives affichées
            </p>
            <p className="mt-1 font-display text-2xl font-bold text-ink-900">{count}</p>
          </Card>
          <Card className="px-5 py-4">
            <p className="text-[11px] font-semibold uppercase tracking-wide text-slate-400">
              Échecs récents
            </p>
            <p className="mt-1 font-display text-2xl font-bold text-red-600">
              {attempts.filter((attempt) => !attempt.successful).length}
            </p>
          </Card>
          <Card className="px-5 py-4">
            <p className="text-[11px] font-semibold uppercase tracking-wide text-slate-400">
              Adresses IP distinctes
            </p>
            <p className="mt-1 font-display text-2xl font-bold text-ink-900">
              {new Set(attempts.map((attempt) => attempt.ip_address)).size}
            </p>
          </Card>
        </div>
      )}

      <Card>
        {loading ? (
          <Spinner label="Chargement des journaux…" />
        ) : error ? (
          <ErrorState message={error} onRetry={() => void load()} />
        ) : tab === 'audit' ? (
          entries.length === 0 ? (
            <EmptyState title="Aucune entrée" description="Aucune action ne correspond aux filtres." />
          ) : (
            <>
              <div className="table-shell">
                <table className="min-w-full divide-y divide-slate-100" data-testid="audit-table">
                  <thead className="bg-slate-50/70">
                    <tr>
                      <th className="th">Date</th>
                      <th className="th">Action</th>
                      <th className="th">Acteur</th>
                      <th className="th">Description</th>
                      <th className="th">IP</th>
                    </tr>
                  </thead>
                  <tbody className="divide-y divide-slate-100">
                    {entries.map((entry) => (
                      <tr key={entry.id} className="hover:bg-slate-50/70">
                        <td className="td whitespace-nowrap text-slate-500">
                          {formatDateTime(entry.created_at)}
                        </td>
                        <td className="td">
                          <Badge
                            tone={
                              entry.action.includes('FAILED') || entry.action.includes('DELETED')
                                ? 'danger'
                                : entry.action.includes('LOGIN')
                                  ? 'info'
                                  : 'brand'
                            }
                          >
                            {entry.action_label}
                          </Badge>
                        </td>
                        <td className="td font-medium text-ink-800">{entry.actor_username || 'système'}</td>
                        <td className="td max-w-[420px] truncate text-slate-600">{entry.description}</td>
                        <td className="td font-mono text-xs text-slate-400">{entry.ip_address ?? '—'}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
              <Pagination page={page} pageSize={PAGE_SIZE} count={count} onPageChange={setPage} />
            </>
          )
        ) : attempts.length === 0 ? (
          <EmptyState title="Aucune connexion enregistrée" icon={<KeyRound className="h-7 w-7" />} />
        ) : (
          <>
            <div className="table-shell">
              <table className="min-w-full divide-y divide-slate-100">
                <thead className="bg-slate-50/70">
                  <tr>
                    <th className="th">Date</th>
                    <th className="th">Identifiant</th>
                    <th className="th">Résultat</th>
                    <th className="th">Motif</th>
                    <th className="th">IP</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-slate-100">
                  {attempts.map((attempt) => (
                    <tr key={attempt.id} className="hover:bg-slate-50/70">
                      <td className="td whitespace-nowrap text-slate-500">
                        {formatDateTime(attempt.created_at)}
                      </td>
                      <td className="td font-medium text-ink-800">{attempt.username_attempted}</td>
                      <td className="td">
                        <Badge tone={attempt.successful ? 'success' : 'danger'}>
                          {attempt.successful ? 'Succès' : 'Échec'}
                        </Badge>
                      </td>
                      <td className="td text-slate-500">{attempt.reason || '—'}</td>
                      <td className="td font-mono text-xs text-slate-400">
                        {attempt.ip_address ?? '—'}
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
            <Pagination page={page} pageSize={PAGE_SIZE} count={count} onPageChange={setPage} />
          </>
        )}
      </Card>

      <Card className="mt-6">
        <CardHeader title="Bonnes pratiques" icon={<ShieldAlert className="h-5 w-5" />} />
        <CardBody className="grid gap-3 text-sm text-slate-600 sm:grid-cols-2">
          <p>• Plusieurs échecs consécutifs verrouillent temporairement le compte.</p>
          <p>• Les mots de passe ne sont jamais enregistrés dans ces journaux.</p>
          <p>• Les réinitialisations exigent un changement à la prochaine connexion.</p>
          <p>• Aucune opération validée ne peut être supprimée définitivement.</p>
        </CardBody>
      </Card>
    </div>
  )
}
