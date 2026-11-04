import {
  AlertTriangle,
  Building2,
  CalendarClock,
  CreditCard,
  Hash,
  Landmark,
  RefreshCw,
  ShieldCheck,
  Wifi,
  WifiOff,
} from 'lucide-react'
import { useCallback, useEffect, useMemo, useState } from 'react'
import {
  CartesianGrid,
  Line,
  LineChart,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from 'recharts'

import { Badge } from '../components/ui/Badge'
import { Button } from '../components/ui/Button'
import { Card, CardBody, CardHeader } from '../components/ui/Card'
import { EmptyState, ErrorState, Spinner } from '../components/ui/Feedback'
import { PageHeader } from '../components/ui/PageHeader'
import { useToast } from '../contexts/ToastContext'
import { extractErrorMessage } from '../services/api'
import { bankingService } from '../services/finance'
import type { BalanceSnapshot, BankInfo } from '../types'
import { formatDateTime, formatMoney, relativeTime } from '../utils/format'

const STATUS_TONES: Record<string, 'success' | 'danger' | 'warning' | 'neutral' | 'info'> = {
  CONNECTED: 'success',
  CONFIGURED: 'info',
  NOT_CONFIGURED: 'neutral',
  ERROR: 'danger',
  SANDBOX: 'warning',
}

export const BankPage = () => {
  const { error: notifyError } = useToast()
  const [bank, setBank] = useState<BankInfo | null>(null)
  const [history, setHistory] = useState<BalanceSnapshot[]>([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState('')

  const load = useCallback(async () => {
    setLoading(true)
    setError('')
    try {
      const [bankData, historyData] = await Promise.all([
        bankingService.status(),
        bankingService.history(90),
      ])
      setBank(bankData)
      setHistory(historyData.results)
    } catch (err) {
      const message = extractErrorMessage(err, 'Impossible de charger les informations bancaires.')
      setError(message)
      notifyError('Erreur bancaire', message)
    } finally {
      setLoading(false)
    }
  }, [notifyError])

  useEffect(() => {
    void load()
  }, [load])

  const chartData = useMemo(
    () =>
      history
        .slice()
        .reverse()
        .map((snapshot) => ({
          label: formatDateTime(snapshot.fetched_at).split(' ').slice(0, 2).join(' '),
          Solde: snapshot.available_balance === null ? null : Number(snapshot.available_balance),
        })),
    [history],
  )

  if (loading && !bank) return <Spinner label="Chargement du compte Ecobank…" />
  if (error && !bank) return <ErrorState message={error} onRetry={() => void load()} />
  if (!bank) return null

  const tone = STATUS_TONES[bank.connection_status] ?? 'neutral'

  return (
    <div className="animate-fade-in">
      <PageHeader
        eyebrow="Module bancaire"
        title="Compte bancaire Ecobank"
        description="Solde consulté depuis l'API officielle. Consultation uniquement — aucune modification possible."
        actions={
          <Button variant="secondary" onClick={() => void load()} loading={loading} icon={<RefreshCw className="h-4 w-4" />}>
            Actualiser
          </Button>
        }
      />

      {bank.is_sandbox && (
        <div className="mb-5 flex items-start gap-3 rounded-xl border border-amber-200 bg-amber-50 px-4 py-3 text-amber-900">
          <AlertTriangle className="mt-0.5 h-5 w-5 shrink-0" />
          <div>
            <p className="text-sm font-semibold">Mode sandbox — données simulées</p>
            <p className="mt-0.5 text-sm">
              Ce solde est généré localement pour la démonstration. Il ne provient pas de l'API
              Ecobank et ne doit jamais être utilisé comme un solde bancaire réel.
            </p>
          </div>
        </div>
      )}

      <div className="grid gap-6 lg:grid-cols-3">
        <Card className="lg:col-span-2">
          <div className="relative overflow-hidden rounded-t-2xl bg-gradient-to-br from-brand-700 via-brand-800 to-brand-950 px-6 py-7 text-white">
            <div
              className="absolute inset-0 opacity-20"
              style={{
                backgroundImage:
                  'radial-gradient(circle at 85% 20%, rgba(147,197,253,0.6) 0, transparent 45%)',
              }}
              aria-hidden
            />
            <div className="relative flex items-start justify-between gap-4">
              <div>
                <p className="text-xs font-semibold uppercase tracking-[0.18em] text-brand-200">
                  Ecobank — {bank.environment_label}
                </p>
                <p className="mt-2 font-display text-sm font-medium text-brand-100">
                  Solde disponible
                </p>
                <p className="mt-1 font-display text-4xl font-extrabold tabular-nums">
                  {formatMoney(bank.available_balance, bank.currency === '—' ? 'USD' : bank.currency)}
                </p>
                <p className="mt-1 text-xs text-brand-200/80">
                  {bank.available_balance === null
                    ? 'Aucun solde synchronisé'
                    : `Mis à jour ${relativeTime(bank.balance_updated_at)}`}
                </p>
              </div>
              <div className="flex flex-col items-end gap-2">
                <Landmark className="h-9 w-9 text-white/80" />
                <Badge tone={tone} className="bg-white/15 text-white ring-white/25">
                  {bank.is_sandbox ? 'Simulation' : bank.connection_status_label}
                </Badge>
              </div>
            </div>

            <div className="relative mt-6 grid gap-4 sm:grid-cols-3">
              <div>
                <p className="text-[11px] uppercase tracking-wide text-brand-200">Numéro de compte</p>
                <p className="mt-0.5 font-mono text-sm font-semibold">{bank.account_masked}</p>
              </div>
              <div>
                <p className="text-[11px] uppercase tracking-wide text-brand-200">Titulaire</p>
                <p className="mt-0.5 truncate text-sm font-semibold">{bank.account_name}</p>
              </div>
              <div>
                <p className="text-[11px] uppercase tracking-wide text-brand-200">Devise</p>
                <p className="mt-0.5 text-sm font-semibold">{bank.currency}</p>
              </div>
            </div>
          </div>

          <div className="grid gap-px bg-slate-100 sm:grid-cols-2 lg:grid-cols-4">
            {[
              {
                icon: CreditCard,
                label: 'Solde comptable',
                value: bank.current_balance
                  ? formatMoney(bank.current_balance, bank.currency)
                  : 'Non fourni',
              },
              { icon: Hash, label: 'Statut du compte', value: bank.account_status || '—' },
              {
                icon: CalendarClock,
                label: 'Dernière synchronisation',
                value: bank.last_sync_at ? formatDateTime(bank.last_sync_at) : 'Jamais',
              },
              {
                icon: Wifi,
                label: 'Fréquence',
                value: `${bank.sync_interval_minutes} min${bank.auto_sync_enabled ? '' : ' (auto off)'}`,
              },
            ].map((item) => (
              <div key={item.label} className="bg-white px-5 py-4">
                <item.icon className="h-4 w-4 text-slate-400" />
                <p className="mt-2 text-[11px] font-semibold uppercase tracking-wide text-slate-400">
                  {item.label}
                </p>
                <p className="mt-0.5 truncate text-sm font-semibold text-ink-900">{item.value}</p>
              </div>
            ))}
          </div>
        </Card>

        <Card>
          <CardHeader title="État de la connexion" icon={<ShieldCheck className="h-5 w-5" />} />
          <CardBody className="space-y-4">
            <div
              className={`flex items-start gap-3 rounded-xl border px-4 py-3 ${
                bank.is_sandbox
                  ? 'border-amber-200 bg-amber-50 text-amber-900'
                  : bank.connection_status === 'CONNECTED'
                    ? 'border-emerald-200 bg-emerald-50 text-emerald-900'
                    : bank.connection_status === 'ERROR'
                      ? 'border-red-200 bg-red-50 text-red-900'
                      : 'border-slate-200 bg-slate-50 text-slate-700'
              }`}
            >
              {bank.connection_status === 'ERROR' ? (
                <WifiOff className="mt-0.5 h-5 w-5 shrink-0" />
              ) : (
                <Wifi className="mt-0.5 h-5 w-5 shrink-0" />
              )}
              <div>
                <p className="text-sm font-semibold">{bank.connection_status_label}</p>
                <p className="mt-0.5 text-xs opacity-90">
                  {bank.last_sync_message || bank.last_test_message || 'Aucun message.'}
                </p>
              </div>
            </div>

            <dl className="space-y-3 text-sm">
              {[
                ['Environnement', bank.environment_label],
                ['Source des données', bank.source === 'API' ? 'API Ecobank' : bank.source === 'SANDBOX' ? 'Sandbox (simulé)' : 'Aucune'],
                ['Dernier test', bank.last_test_at ? formatDateTime(bank.last_test_at) : 'Jamais testé'],
                ['Statut du test', bank.last_test_status || '—'],
                ['Dernier statut de sync', bank.last_sync_status || '—'],
              ].map(([label, value]) => (
                <div key={label} className="flex items-center justify-between gap-3 border-b border-slate-100 pb-2 last:border-0">
                  <dt className="text-slate-500">{label}</dt>
                  <dd className="text-right font-medium text-ink-900">{value}</dd>
                </div>
              ))}
            </dl>

            <div className="rounded-xl bg-slate-50 p-3 text-xs leading-relaxed text-slate-500">
              <Building2 className="mb-1 h-4 w-4 text-slate-400" />
              Seul un administrateur peut configurer l'API, déclencher une synchronisation ou
              modifier les paramètres bancaires.
            </div>
          </CardBody>
        </Card>
      </div>

      <div className="mt-6 grid gap-6 xl:grid-cols-2">
        <Card>
          <CardHeader
            title="Historique des soldes"
            subtitle="90 derniers jours de synchronisations"
            icon={<Landmark className="h-5 w-5" />}
          />
          <CardBody>
            {chartData.length === 0 ? (
              <EmptyState
                title="Aucun historique"
                description="L'historique se remplit à chaque synchronisation réussie."
              />
            ) : (
              <div className="h-[280px]">
                <ResponsiveContainer width="100%" height="100%">
                  <LineChart data={chartData} margin={{ top: 8, right: 12, left: -12, bottom: 0 }}>
                    <CartesianGrid strokeDasharray="3 3" stroke="#eef2f7" vertical={false} />
                    <XAxis dataKey="label" tick={{ fontSize: 10, fill: '#64748b' }} axisLine={false} tickLine={false} />
                    <YAxis tick={{ fontSize: 11, fill: '#94a3b8' }} axisLine={false} tickLine={false} />
                    <Tooltip
                      formatter={(value: number) => formatMoney(value, bank.currency === '—' ? 'USD' : bank.currency)}
                      contentStyle={{ borderRadius: 12, border: '1px solid #e2e8f0', fontSize: 12 }}
                    />
                    <Line type="monotone" dataKey="Solde" stroke="#1d4ed8" strokeWidth={2.5} dot={{ r: 2.5 }} />
                  </LineChart>
                </ResponsiveContainer>
              </div>
            )}
          </CardBody>
        </Card>

        <Card>
          <CardHeader title="Dernières synchronisations" icon={<RefreshCw className="h-5 w-5" />} />
          <div className="table-shell max-h-[340px] overflow-y-auto">
            <table className="min-w-full divide-y divide-slate-100">
              <thead className="sticky top-0 bg-slate-50/95 backdrop-blur">
                <tr>
                  <th className="th">Date</th>
                  <th className="th">Source</th>
                  <th className="th text-right">Solde</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-slate-100">
                {history.length === 0 ? (
                  <tr>
                    <td colSpan={3} className="td py-8 text-center text-slate-400">
                      Aucune synchronisation enregistrée
                    </td>
                  </tr>
                ) : (
                  history.map((snapshot) => (
                    <tr key={snapshot.id} className="hover:bg-slate-50/70">
                      <td className="td text-slate-600">{formatDateTime(snapshot.fetched_at)}</td>
                      <td className="td">
                        <Badge tone={snapshot.is_sandbox ? 'warning' : 'success'}>
                          {snapshot.is_sandbox ? 'Simulé' : 'API'}
                        </Badge>
                      </td>
                      <td className="td text-right font-semibold tabular-nums text-ink-900">
                        {formatMoney(snapshot.available_balance, snapshot.currency || bank.currency)}
                      </td>
                    </tr>
                  ))
                )}
              </tbody>
            </table>
          </div>
        </Card>
      </div>
    </div>
  )
}
