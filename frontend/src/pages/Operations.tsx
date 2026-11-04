import {
  ArrowDownLeft,
  ArrowUpRight,
  CalendarRange,
  Download,
  FileSpreadsheet,
  FileText,
  Filter,
  Pencil,
  Plus,
  Search,
  Trash2,
} from 'lucide-react'
import { useCallback, useEffect, useMemo, useState } from 'react'

import { Badge } from '../components/ui/Badge'
import { Button } from '../components/ui/Button'
import { Card } from '../components/ui/Card'
import { EmptyState, ErrorState, Spinner } from '../components/ui/Feedback'
import { Input, Select, Textarea } from '../components/ui/Field'
import { Modal, ConfirmDialog } from '../components/ui/Modal'
import { PageHeader } from '../components/ui/PageHeader'
import { Pagination } from '../components/ui/Pagination'
import { useAuth } from '../contexts/AuthContext'
import { useToast } from '../contexts/ToastContext'
import { extractErrorMessage, extractFieldErrors } from '../services/api'
import { financeService, type OperationFilters, type OperationInput } from '../services/finance'
import type { Operation, OperationType } from '../types'
import { formatDate, formatDateTime, formatMoney, todayISO } from '../utils/format'

const PAGE_SIZE = 25

const EMPTY_FORM: OperationInput = {
  date: todayISO(),
  label: '',
  amount: '',
  operation_type: 'ENTRY',
  reference: '',
  observation: '',
}

export const OperationsPage = () => {
  const { user } = useAuth()
  const { success, error: notifyError } = useToast()

  const [operations, setOperations] = useState<Operation[]>([])
  const [count, setCount] = useState(0)
  const [page, setPage] = useState(1)
  const [loading, setLoading] = useState(true)
  const [listError, setListError] = useState('')

  const [search, setSearch] = useState('')
  const [debouncedSearch, setDebouncedSearch] = useState('')
  const [typeFilter, setTypeFilter] = useState<OperationType | ''>('')
  const [dateFrom, setDateFrom] = useState('')
  const [dateTo, setDateTo] = useState('')

  const [formOpen, setFormOpen] = useState(false)
  const [editing, setEditing] = useState<Operation | null>(null)
  const [form, setForm] = useState<OperationInput>(EMPTY_FORM)
  const [formErrors, setFormErrors] = useState<Record<string, string>>({})
  const [saving, setSaving] = useState(false)

  const [deleteTarget, setDeleteTarget] = useState<Operation | null>(null)
  const [deleting, setDeleting] = useState(false)
  const [exporting, setExporting] = useState<'xlsx' | 'pdf' | null>(null)

  const [historyTarget, setHistoryTarget] = useState<Operation | null>(null)
  const [historyEntries, setHistoryEntries] = useState<
    { id: number; action_label: string; description: string; actor_username: string; created_at: string }[]
  >([])
  const [historyLoading, setHistoryLoading] = useState(false)

  useEffect(() => {
    const timer = window.setTimeout(() => {
      setDebouncedSearch(search.trim())
      setPage(1)
    }, 350)
    return () => window.clearTimeout(timer)
  }, [search])

  const filters: OperationFilters = useMemo(
    () => ({
      date_from: dateFrom || undefined,
      date_to: dateTo || undefined,
      operation_type: typeFilter || undefined,
      search: debouncedSearch || undefined,
      page,
      page_size: PAGE_SIZE,
    }),
    [dateFrom, dateTo, typeFilter, debouncedSearch, page],
  )

  const load = useCallback(async () => {
    setLoading(true)
    setListError('')
    try {
      const data = await financeService.list(filters)
      setOperations(data.results)
      setCount(data.count)
    } catch (err) {
      setListError(extractErrorMessage(err, 'Impossible de charger les opérations.'))
    } finally {
      setLoading(false)
    }
  }, [filters])

  useEffect(() => {
    void load()
  }, [load])

  const currency = user?.application?.currency ?? 'USD'

  const openCreate = () => {
    setEditing(null)
    setForm({ ...EMPTY_FORM, date: todayISO() })
    setFormErrors({})
    setFormOpen(true)
  }

  const openEdit = (operation: Operation) => {
    setEditing(operation)
    setForm({
      date: operation.date,
      label: operation.label,
      amount: operation.amount,
      operation_type: operation.operation_type,
      reference: operation.reference,
      observation: operation.observation,
    })
    setFormErrors({})
    setFormOpen(true)
  }

  const submitForm = async () => {
    const errors: Record<string, string> = {}
    if (!form.date) errors.date = 'La date est obligatoire.'
    if (form.label.trim().length < 3) errors.label = 'Le libellé doit contenir au moins 3 caractères.'
    if (!form.amount || Number(form.amount) <= 0) errors.amount = 'Le montant doit être supérieur à zéro.'
    if (!form.operation_type) errors.operation_type = "Le type d'opération est obligatoire."
    if (Object.keys(errors).length > 0) {
      setFormErrors(errors)
      return
    }

    setSaving(true)
    try {
      if (editing) {
        await financeService.update(editing.id, form)
        success('Opération modifiée', 'La modification a été enregistrée dans le journal d’audit.')
      } else {
        await financeService.create(form)
        success('Opération enregistrée', 'Le solde financier a été recalculé côté serveur.')
      }
      setFormOpen(false)
      await load()
    } catch (err) {
      setFormErrors(extractFieldErrors(err))
      notifyError('Enregistrement impossible', extractErrorMessage(err))
    } finally {
      setSaving(false)
    }
  }

  const confirmDelete = async () => {
    if (!deleteTarget) return
    setDeleting(true)
    try {
      await financeService.remove(deleteTarget.id)
      success('Opération archivée', 'Elle reste consultable dans le journal d’audit.')
      setDeleteTarget(null)
      await load()
    } catch (err) {
      notifyError('Suppression impossible', extractErrorMessage(err))
    } finally {
      setDeleting(false)
    }
  }

  const openHistory = async (operation: Operation) => {
    setHistoryTarget(operation)
    setHistoryLoading(true)
    try {
      const entries = await financeService.history(operation.id)
      setHistoryEntries(entries)
    } catch (err) {
      notifyError('Historique indisponible', extractErrorMessage(err))
      setHistoryEntries([])
    } finally {
      setHistoryLoading(false)
    }
  }

  const handleExport = async (fileFormat: 'xlsx' | 'pdf') => {
    setExporting(fileFormat)
    try {
      await financeService.downloadExport(fileFormat, {
        date_from: dateFrom || undefined,
        date_to: dateTo || undefined,
        operation_type: typeFilter || undefined,
        search: debouncedSearch || undefined,
      })
      success('Export généré', `Le fichier ${fileFormat.toUpperCase()} a été téléchargé.`)
    } catch (err) {
      notifyError('Export impossible', extractErrorMessage(err))
    } finally {
      setExporting(null)
    }
  }

  return (
    <div className="animate-fade-in">
      <PageHeader
        eyebrow="Module financier"
        title="Opérations financières"
        description="Enregistrez, filtrez et exportez les entrées et sorties. Toute modification est auditée."
        actions={
          <>
            <div className="flex items-center gap-2">
              <Button
                variant="secondary"
                size="sm"
                loading={exporting === 'xlsx'}
                onClick={() => void handleExport('xlsx')}
                icon={<FileSpreadsheet className="h-4 w-4" />}
              >
                Excel
              </Button>
              <Button
                variant="secondary"
                size="sm"
                loading={exporting === 'pdf'}
                onClick={() => void handleExport('pdf')}
                icon={<FileText className="h-4 w-4" />}
              >
                PDF
              </Button>
            </div>
            <Button onClick={openCreate} icon={<Plus className="h-4 w-4" />}>
              Nouvelle opération
            </Button>
          </>
        }
      />

      <Card className="mb-5 p-4">
        <div className="grid gap-3 lg:grid-cols-12">
          <div className="lg:col-span-4">
            <Input
              aria-label="Rechercher une opération"
              placeholder="Rechercher par libellé, référence…"
              value={search}
              onChange={(event) => setSearch(event.target.value)}
              icon={<Search className="h-4 w-4" />}
            />
          </div>
          <div className="lg:col-span-2">
            <Select
              aria-label="Filtrer par type"
              value={typeFilter}
              onChange={(event) => {
                setTypeFilter(event.target.value as OperationType | '')
                setPage(1)
              }}
              placeholder="Tous les types"
              options={[
                { value: 'ENTRY', label: 'Entrées' },
                { value: 'EXIT', label: 'Sorties' },
              ]}
            />
          </div>
          <div className="lg:col-span-3">
            <div className="flex items-center gap-2 rounded-xl border border-slate-300 bg-white px-3 py-2.5">
              <CalendarRange className="h-4 w-4 shrink-0 text-slate-400" />
              <input
                type="date"
                aria-label="Période - début"
                value={dateFrom}
                onChange={(event) => {
                  setDateFrom(event.target.value)
                  setPage(1)
                }}
                className="w-full border-0 bg-transparent p-0 text-sm focus:outline-none"
              />
              <span className="text-slate-300">→</span>
              <input
                type="date"
                aria-label="Période - fin"
                value={dateTo}
                onChange={(event) => {
                  setDateTo(event.target.value)
                  setPage(1)
                }}
                className="w-full border-0 bg-transparent p-0 text-sm focus:outline-none"
              />
            </div>
          </div>
          <div className="flex items-center gap-2 lg:col-span-3">
            <Button
              variant="ghost"
              size="sm"
              onClick={() => {
                setSearch('')
                setTypeFilter('')
                setDateFrom('')
                setDateTo('')
                setPage(1)
              }}
              icon={<Filter className="h-4 w-4" />}
            >
              Réinitialiser
            </Button>
            <Button
              variant="ghost"
              size="sm"
              onClick={() => void load()}
              icon={<Download className="h-4 w-4 rotate-180" />}
            >
              Actualiser
            </Button>
          </div>
        </div>
      </Card>

      <Card>
        {loading ? (
          <Spinner label="Chargement des opérations…" />
        ) : listError ? (
          <ErrorState message={listError} onRetry={() => void load()} />
        ) : operations.length === 0 ? (
          <EmptyState
            title="Aucune opération trouvée"
            description="Ajustez vos filtres ou enregistrez une première opération financière."
            action={
              <Button onClick={openCreate} icon={<Plus className="h-4 w-4" />}>
                Nouvelle opération
              </Button>
            }
          />
        ) : (
          <>
            <div className="table-shell">
              <table className="min-w-full divide-y divide-slate-100" data-testid="operations-table">
                <thead className="bg-slate-50/70">
                  <tr>
                    <th className="th">Date</th>
                    <th className="th">Libellé</th>
                    <th className="th">Type</th>
                    <th className="th text-right">Montant</th>
                    <th className="th">Référence</th>
                    <th className="th">Saisi par</th>
                    <th className="th text-right">Actions</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-slate-100">
                  {operations.map((operation) => {
                    const isEntry = operation.operation_type === 'ENTRY'
                    return (
                      <tr key={operation.id} className="group hover:bg-slate-50/70">
                        <td className="td tabular-nums text-slate-600">{formatDate(operation.date)}</td>
                        <td className="td">
                          <button
                            type="button"
                            onClick={() => void openHistory(operation)}
                            className="max-w-[260px] truncate text-left font-medium text-ink-900 hover:text-brand-700 hover:underline"
                            title="Voir l'historique"
                          >
                            {operation.label}
                          </button>
                          {operation.observation && (
                            <p className="max-w-[260px] truncate text-xs text-slate-400">
                              {operation.observation}
                            </p>
                          )}
                        </td>
                        <td className="td">
                          <Badge tone={isEntry ? 'success' : 'danger'} dot>
                            {isEntry ? (
                              <span className="inline-flex items-center gap-1">
                                <ArrowDownLeft className="h-3 w-3" /> Entrée
                              </span>
                            ) : (
                              <span className="inline-flex items-center gap-1">
                                <ArrowUpRight className="h-3 w-3" /> Sortie
                              </span>
                            )}
                          </Badge>
                        </td>
                        <td
                          className={`td text-right font-semibold tabular-nums ${isEntry ? 'text-emerald-700' : 'text-red-600'}`}
                        >
                          {isEntry ? '+' : '−'} {formatMoney(operation.amount, currency)}
                        </td>
                        <td className="td text-slate-500">{operation.reference || '—'}</td>
                        <td className="td text-slate-500">{operation.created_by_username ?? '—'}</td>
                        <td className="td">
                          <div className="flex items-center justify-end gap-1 opacity-60 transition group-hover:opacity-100">
                            <button
                              type="button"
                              onClick={() => openEdit(operation)}
                              className="rounded-lg p-2 text-slate-500 transition hover:bg-brand-50 hover:text-brand-700"
                              aria-label={`Modifier ${operation.label}`}
                            >
                              <Pencil className="h-4 w-4" />
                            </button>
                            <button
                              type="button"
                              onClick={() => setDeleteTarget(operation)}
                              className="rounded-lg p-2 text-slate-500 transition hover:bg-red-50 hover:text-red-600"
                              aria-label={`Supprimer ${operation.label}`}
                            >
                              <Trash2 className="h-4 w-4" />
                            </button>
                          </div>
                        </td>
                      </tr>
                    )
                  })}
                </tbody>
              </table>
            </div>
            <Pagination page={page} pageSize={PAGE_SIZE} count={count} onPageChange={setPage} />
          </>
        )}
      </Card>

      {/* Create / edit */}
      <Modal
        open={formOpen}
        onClose={() => setFormOpen(false)}
        title={editing ? 'Modifier l’opération' : 'Nouvelle opération financière'}
        description={
          editing
            ? 'La modification sera enregistrée dans le journal d’audit.'
            : 'Le solde financier est recalculé automatiquement côté serveur.'
        }
        footer={
          <>
            <Button variant="secondary" onClick={() => setFormOpen(false)} disabled={saving}>
              Annuler
            </Button>
            <Button onClick={() => void submitForm()} loading={saving}>
              {editing ? 'Enregistrer' : 'Créer l’opération'}
            </Button>
          </>
        }
      >
        <div className="grid gap-4 sm:grid-cols-2">
          <Input
            label="Date de l'opération"
            name="date"
            type="date"
            value={form.date}
            onChange={(event) => setForm({ ...form, date: event.target.value })}
            error={formErrors.date}
            required
          />
          <Select
            label="Type d'opération"
            name="operation_type"
            value={form.operation_type}
            onChange={(event) =>
              setForm({ ...form, operation_type: event.target.value as OperationType })
            }
            options={[
              { value: 'ENTRY', label: 'Entrée' },
              { value: 'EXIT', label: 'Sortie' },
            ]}
            error={formErrors.operation_type}
            required
          />
          <div className="sm:col-span-2">
            <Input
              label="Libellé"
              name="label"
              value={form.label}
              onChange={(event) => setForm({ ...form, label: event.target.value })}
              placeholder="Ex. Financement reçu"
              error={formErrors.label}
              required
            />
          </div>
          <Input
            label={`Montant (${currency})`}
            name="amount"
            type="number"
            min="0.01"
            step="0.01"
            value={form.amount}
            onChange={(event) => setForm({ ...form, amount: event.target.value })}
            error={formErrors.amount}
            required
          />
          <Input
            label="Référence (facultative)"
            name="reference"
            value={form.reference}
            onChange={(event) => setForm({ ...form, reference: event.target.value })}
            placeholder="Ex. FIN-001"
          />
          <div className="sm:col-span-2">
            <Textarea
              label="Observation (facultative)"
              name="observation"
              value={form.observation}
              onChange={(event) => setForm({ ...form, observation: event.target.value })}
              placeholder="Commentaire interne…"
            />
          </div>
        </div>
      </Modal>

      <ConfirmDialog
        open={Boolean(deleteTarget)}
        title="Archiver cette opération ?"
        message={`L'opération « ${deleteTarget?.label ?? ''} » sera retirée des soldes mais restera tracée dans l'historique d'audit. Aucune donnée n'est supprimée définitivement.`}
        confirmLabel="Archiver"
        loading={deleting}
        onConfirm={() => void confirmDelete()}
        onCancel={() => setDeleteTarget(null)}
      />

      {/* Operation history */}
      <Modal
        open={Boolean(historyTarget)}
        onClose={() => setHistoryTarget(null)}
        title="Historique de l’opération"
        description={historyTarget?.label}
        size="lg"
      >
        {historyLoading ? (
          <Spinner label="Chargement de l’historique…" />
        ) : historyEntries.length === 0 ? (
          <p className="py-6 text-center text-sm text-slate-500">
            Aucun évènement enregistré pour cette opération.
          </p>
        ) : (
          <ol className="relative space-y-4 border-l border-slate-200 pl-6">
            {historyEntries.map((entry) => (
              <li key={entry.id} className="relative">
                <span className="absolute -left-[31px] top-1 h-3 w-3 rounded-full border-2 border-white bg-brand-600" />
                <p className="text-sm font-semibold text-ink-900">{entry.action_label}</p>
                <p className="text-sm text-slate-600">{entry.description}</p>
                <p className="mt-0.5 text-xs text-slate-400">
                  {entry.actor_username || 'système'} · {formatDateTime(entry.created_at)}
                </p>
              </li>
            ))}
          </ol>
        )}
      </Modal>
    </div>
  )
}
