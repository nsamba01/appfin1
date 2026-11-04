import {
  AlertTriangle,
  ArrowDownRight,
  ArrowUpRight,
  Building2,
  CalendarRange,
  CheckCircle2,
  Info,
  Landmark,
  RefreshCw,
  Scale,
  Wallet,
  XCircle,
} from 'lucide-react'
import { useCallback, useEffect, useMemo, useState } from 'react'
import {
  Area,
  AreaChart,
  Bar,
  BarChart,
  CartesianGrid,
  Cell,
  Legend,
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
import { StatCard } from '../components/ui/StatCard'
import { useAuth } from '../contexts/AuthContext'
import { extractErrorMessage } from '../services/api'
import { financeService } from '../services/finance'
import type { DashboardCharts, DashboardSummary } from '../types'
import { formatDate, formatDateTime, formatMoney, formatMonth } from '../utils/format'

const ALERT_ICONS = {
  info: Info,
  warning: AlertTriangle,
  error: XCircle,
  success: CheckCircle2,
}

const ALERT_STYLES = {
  info: 'border-sky-200 bg-sky-50 text-sky-800',
  warning: 'border-amber-200 bg-amber-50 text-amber-800',
  error: 'border-red-200 bg-red-50 text-red-800',
  success: 'border-emerald-200 bg-emerald-50 text-emerald-800',
}

const ChartTooltip = ({
  active,
  payload,
  label,
  currency,
}: {
  active?: boolean
  payload?: { name?: string; value?: number | string; color?: string }[]
  label?: string
  currency: string
}) => {
  if (!active || !payload?.length) return null
  return (
    <div className="rounded-xl border border-slate-200 bg-white px-3 py-2 text-xs shadow-lift">
      <p className="mb-1 font-semibold text-ink-800">{label}</p>
      {payload.map((entry) => (
        <p key={entry.name} className="flex items-center gap-2 text-slate-600">
          <span className="h-2 w-2 rounded-full" style={{ background: entry.color }} />
          {entry.name} : {formatMoney(entry.value, currency)}
        </p>
      ))}
    </div>
  )
}

export const DashboardPage = () => {
  const { user } = useAuth()
  const [summary, setSummary] = useState<DashboardSummary | null>(null)
  const [charts, setCharts] = useState<DashboardCharts | null>(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState('')
  const [dateFrom, setDateFrom] = useState('')
  const [dateTo, setDateTo] = useState('')

  const load = useCallback(async () => {
    setLoading(true)
    setError('')
    try {
      const filters = { date_from: dateFrom || undefined, date_to: dateTo || undefined }
      const [summaryData, chartsData] = await Promise.all([
        financeService.summary(filters),
        financeService.charts(filters),
      ])
      setSummary(summaryData)
      setCharts(chartsData)
    } catch (err) {
      setError(extractErrorMessage(err, 'Impossible de charger le tableau de bord.'))
    } finally {
      setLoading(false)
    }
  }, [dateFrom, dateTo])

  useEffect(() => {
    void load()
  }, [load])

  const currency = summary?.currency ?? 'USD'

  const gapTone = useMemo(() => {
    const status = summary?.comparison.status
    if (status === 'EQUAL') return { tone: 'success' as const, icon: CheckCircle2, label: 'Soldes identiques' }
    if (status === 'FINANCIAL_HIGHER') return { tone: 'warning' as const, icon: ArrowUpRight, label: 'Solde financier supérieur' }
    if (status === 'BANK_HIGHER') return { tone: 'danger' as const, icon: ArrowDownRight, label: 'Solde bancaire supérieur' }
    return { tone: 'neutral' as const, icon: Info, label: 'Comparaison indisponible' }
  }, [summary?.comparison.status])

  const monthlyData = useMemo(
    () =>
      (charts?.monthly ?? []).map((point) => ({
        period: formatMonth(point.period),
        Entrées: Number(point.entries),
        Sorties: Number(point.exits),
        Solde: Number(point.balance),
      })),
    [charts?.monthly],
  )

  const bankHistoryData = useMemo(
    () =>
      (charts?.bank_history ?? []).map((point) => ({
        label: point.label,
        Solde: Number(point.balance),
      })),
    [charts?.bank_history],
  )

  const gapHistoryData = useMemo(
    () =>
      (charts?.gap_history ?? []).map((point) => ({
        label: point.label,
        Financier: Number(point.financial_balance),
        Bancaire: point.bank_balance === null ? null : Number(point.bank_balance),
        Écart: point.gap === null ? null : Number(point.gap),
      })),
    [charts?.gap_history],
  )

  const comparisonData = useMemo(
    () =>
      (charts?.comparison ?? [])
        .filter((row) => row.indicator !== 'Balance')
        .map((row) => ({
          name: row.indicator,
          Financier: Number(row.financial),
          Bancaire: row.bank === null ? null : Number(row.bank),
        })),
    [charts?.comparison],
  )

  if (loading && !summary) {
    return <Spinner label="Chargement du tableau de bord…" />
  }

  if (error && !summary) {
    return <ErrorState message={error} onRetry={() => void load()} />
  }

  if (!summary) return null

  const GapIcon = gapTone.icon

  return (
    <div className="animate-fade-in" data-testid="dashboard-page">
      <PageHeader
        eyebrow={`Bienvenue, ${user?.full_name || user?.username || ''}`}
        title="Tableau de bord financier & bancaire"
        description="Vue consolidée de la situation financière interne et du compte bancaire Ecobank."
        actions={
          <>
            <div className="flex items-center gap-2 rounded-xl border border-slate-200 bg-white px-3 py-1.5 shadow-sm">
              <CalendarRange className="h-4 w-4 text-slate-400" />
              <input
                type="date"
                aria-label="Date de début"
                value={dateFrom}
                onChange={(event) => setDateFrom(event.target.value)}
                className="w-[130px] border-0 bg-transparent p-0 text-sm text-ink-700 focus:outline-none"
              />
              <span className="text-slate-300">→</span>
              <input
                type="date"
                aria-label="Date de fin"
                value={dateTo}
                onChange={(event) => setDateTo(event.target.value)}
                className="w-[130px] border-0 bg-transparent p-0 text-sm text-ink-700 focus:outline-none"
              />
            </div>
            <Button
              variant="secondary"
              onClick={() => void load()}
              loading={loading}
              icon={<RefreshCw className="h-4 w-4" />}
            >
              Actualiser
            </Button>
          </>
        }
      />

      {summary.alerts.length > 0 && (
        <div className="mb-6 space-y-2">
          {summary.alerts.map((alert) => {
            const Icon = ALERT_ICONS[alert.level] ?? Info
            return (
              <div
                key={`${alert.level}-${alert.title}`}
                role="status"
                className={`flex items-start gap-3 rounded-xl border px-4 py-3 ${ALERT_STYLES[alert.level]}`}
              >
                <Icon className="mt-0.5 h-5 w-5 shrink-0" />
                <div>
                  <p className="text-sm font-semibold">{alert.title}</p>
                  <p className="mt-0.5 text-sm opacity-90">{alert.message}</p>
                </div>
              </div>
            )
          })}
        </div>
      )}

      {/* Stat cards */}
      <div className="grid gap-4 sm:grid-cols-2 xl:grid-cols-4">
        <StatCard
          label="Solde financier interne"
          value={formatMoney(summary.financial.balance, currency)}
          hint={`${summary.financial.operation_count} opération(s) enregistrée(s)`}
          icon={<Wallet className="h-5 w-5" />}
          tone={Number(summary.financial.balance) >= 0 ? 'success' : 'danger'}
        />
        <StatCard
          label="Solde bancaire Ecobank"
          value={formatMoney(summary.bank.available_balance, summary.bank.currency || currency)}
          hint={
            summary.bank.is_sandbox
              ? 'Données simulées (sandbox)'
              : summary.bank.balance_updated_at
                ? `Synchronisé ${formatDateTime(summary.bank.balance_updated_at)}`
                : 'Aucune synchronisation'
          }
          icon={<Landmark className="h-5 w-5" />}
          tone={summary.bank.is_sandbox ? 'warning' : 'brand'}
          badge={
            summary.bank.is_sandbox ? (
              <Badge tone="warning" dot>
                Simulation sandbox
              </Badge>
            ) : summary.bank.available_balance ? (
              <Badge tone="success" dot>
                Compte {summary.bank.account_masked}
              </Badge>
            ) : (
              <Badge tone="neutral" dot>
                Non disponible
              </Badge>
            )
          }
        />
        <StatCard
          label="Total des entrées"
          value={formatMoney(summary.financial.total_entries, currency)}
          hint="Somme des entrées de la période"
          icon={<ArrowDownRight className="h-5 w-5 rotate-180" />}
          tone="success"
        />
        <StatCard
          label="Total des sorties"
          value={formatMoney(summary.financial.total_exits, currency)}
          hint="Somme des sorties de la période"
          icon={<ArrowUpRight className="h-5 w-5" />}
          tone="danger"
        />
      </div>

      <div className="mt-4 grid gap-4 sm:grid-cols-2 xl:grid-cols-3">
        <StatCard
          label="Balance financière"
          value={formatMoney(summary.comparison.financial_balance, currency)}
          hint="Total des entrées − total des sorties"
          icon={<Scale className="h-5 w-5" />}
          tone="neutral"
        />
        <StatCard
          label="Écart financier / bancaire"
          value={
            summary.comparison.gap === null
              ? '—'
              : formatMoney(summary.comparison.gap, currency)
          }
          hint={summary.comparison.status_label}
          icon={<GapIcon className="h-5 w-5" />}
          tone={gapTone.tone === 'neutral' ? 'neutral' : gapTone.tone}
          badge={<Badge tone={gapTone.tone}>{gapTone.label}</Badge>}
        />
        <StatCard
          label="Mouvements non rapprochés"
          value={summary.unreconciled.count}
          hint={summary.unreconciled.note}
          icon={<Building2 className="h-5 w-5" />}
          tone="warning"
        />
      </div>

      {/* Comparison table + gap chart */}
      <div className="mt-6 grid gap-6 xl:grid-cols-5">
        <Card className="xl:col-span-3">
          <CardHeader
            title="Comparaison financière et bancaire"
            subtitle="Les mouvements internes non rapprochés restent identifiés séparément."
            icon={<Scale className="h-5 w-5" />}
            action={<Badge tone="brand">{summary.currency}</Badge>}
          />
          <div className="table-shell">
            <table className="min-w-full divide-y divide-slate-100">
              <thead className="bg-slate-50/70">
                <tr>
                  <th className="th">Indicateurs</th>
                  <th className="th text-right">Situation financière</th>
                  <th className="th text-right">Situation bancaire</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-slate-100">
                {[
                  {
                    label: "Total des entrées",
                    financial: formatMoney(summary.financial.total_entries, currency),
                    bank: '—',
                    note: "Non fourni par l'API",
                  },
                  {
                    label: 'Total des sorties',
                    financial: formatMoney(summary.financial.total_exits, currency),
                    bank: '—',
                    note: "Non fourni par l'API",
                  },
                  {
                    label: 'Solde disponible',
                    financial: formatMoney(summary.comparison.financial_balance, currency),
                    bank: formatMoney(summary.bank.available_balance, summary.bank.currency || currency),
                    note: summary.bank.is_sandbox ? 'Simulé (sandbox)' : 'API Ecobank',
                  },
                  {
                    label: 'Balance',
                    financial: formatMoney(summary.financial.balance, currency),
                    bank: '—',
                    note: "Non fourni par l'API",
                  },
                  {
                    label: 'Date de mise à jour',
                    financial: formatDate(summary.generated_at),
                    bank: summary.bank.balance_updated_at
                      ? formatDateTime(summary.bank.balance_updated_at)
                      : 'Jamais synchronisé',
                    note: summary.bank.last_sync_status ?? '',
                  },
                ].map((row) => (
                  <tr key={row.label} className="hover:bg-slate-50/60">
                    <td className="td font-medium text-ink-800">{row.label}</td>
                    <td className="td text-right font-semibold tabular-nums text-ink-900">
                      {row.financial}
                    </td>
                    <td className="td text-right tabular-nums">
                      <span className={row.bank === '—' ? 'text-slate-400' : 'font-semibold text-ink-900'}>
                        {row.bank}
                      </span>
                      {row.note && <span className="ml-2 text-[11px] text-slate-400">{row.note}</span>}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
          <div className="flex flex-wrap items-center justify-between gap-3 border-t border-slate-100 px-5 py-3.5">
            <p className="text-xs text-slate-500">
              Écart = solde financier interne − solde bancaire Ecobank
            </p>
            <Badge tone={gapTone.tone} dot>
              {summary.comparison.gap === null
                ? 'Écart non calculable'
                : `${formatMoney(summary.comparison.gap, currency)}`}
            </Badge>
          </div>
        </Card>

        <Card className="xl:col-span-2">
          <CardHeader title="Soldes comparés" subtitle="Situation interne et solde bancaire" icon={<Scale className="h-5 w-5" />} />
          <CardBody>
            {comparisonData.length === 0 ? (
              <EmptyState title="Aucune donnée à comparer" />
            ) : (
              <div className="h-[260px]">
                <ResponsiveContainer width="100%" height="100%">
                  <BarChart data={comparisonData} margin={{ top: 8, right: 8, left: -18, bottom: 0 }}>
                    <CartesianGrid strokeDasharray="3 3" stroke="#eef2f7" vertical={false} />
                    <XAxis dataKey="name" tick={{ fontSize: 11, fill: '#64748b' }} axisLine={false} tickLine={false} />
                    <YAxis tick={{ fontSize: 11, fill: '#94a3b8' }} axisLine={false} tickLine={false} />
                    <Tooltip content={<ChartTooltip currency={currency} />} />
                    <Legend iconType="circle" wrapperStyle={{ fontSize: 12 }} />
                    <Bar dataKey="Financier" fill="#1d4ed8" radius={[6, 6, 0, 0]} maxBarSize={38} />
                    <Bar dataKey="Bancaire" fill="#60a5fa" radius={[6, 6, 0, 0]} maxBarSize={38} />
                  </BarChart>
                </ResponsiveContainer>
              </div>
            )}
          </CardBody>
        </Card>
      </div>

      {/* Charts */}
      <div className="mt-6 grid gap-6 xl:grid-cols-2">
        <Card>
          <CardHeader
            title="Évolution des entrées et sorties"
            subtitle="Mensuelle, en devise de l'application"
            icon={<ArrowUpRight className="h-5 w-5" />}
          />
          <CardBody>
            {monthlyData.length === 0 ? (
              <EmptyState
                title="Aucune opération enregistrée"
                description="Les graphiques apparaîtront dès la première opération."
              />
            ) : (
              <div className="h-[280px]">
                <ResponsiveContainer width="100%" height="100%">
                  <BarChart data={monthlyData} margin={{ top: 8, right: 8, left: -18, bottom: 0 }}>
                    <CartesianGrid strokeDasharray="3 3" stroke="#eef2f7" vertical={false} />
                    <XAxis dataKey="period" tick={{ fontSize: 11, fill: '#64748b' }} axisLine={false} tickLine={false} />
                    <YAxis tick={{ fontSize: 11, fill: '#94a3b8' }} axisLine={false} tickLine={false} />
                    <Tooltip content={<ChartTooltip currency={currency} />} />
                    <Legend iconType="circle" wrapperStyle={{ fontSize: 12 }} />
                    <Bar dataKey="Entrées" fill="#047857" radius={[6, 6, 0, 0]} maxBarSize={30} />
                    <Bar dataKey="Sorties" fill="#dc2626" radius={[6, 6, 0, 0]} maxBarSize={30} />
                  </BarChart>
                </ResponsiveContainer>
              </div>
            )}
          </CardBody>
        </Card>

        <Card>
          <CardHeader
            title="Évolution du solde financier"
            subtitle="Solde cumulé par mois"
            icon={<Wallet className="h-5 w-5" />}
          />
          <CardBody>
            {monthlyData.length === 0 ? (
              <EmptyState title="Aucune donnée disponible" />
            ) : (
              <div className="h-[280px]">
                <ResponsiveContainer width="100%" height="100%">
                  <AreaChart data={monthlyData} margin={{ top: 8, right: 8, left: -18, bottom: 0 }}>
                    <defs>
                      <linearGradient id="balanceGradient" x1="0" y1="0" x2="0" y2="1">
                        <stop offset="0%" stopColor="#1d4ed8" stopOpacity={0.28} />
                        <stop offset="100%" stopColor="#1d4ed8" stopOpacity={0.02} />
                      </linearGradient>
                    </defs>
                    <CartesianGrid strokeDasharray="3 3" stroke="#eef2f7" vertical={false} />
                    <XAxis dataKey="period" tick={{ fontSize: 11, fill: '#64748b' }} axisLine={false} tickLine={false} />
                    <YAxis tick={{ fontSize: 11, fill: '#94a3b8' }} axisLine={false} tickLine={false} />
                    <Tooltip content={<ChartTooltip currency={currency} />} />
                    <Area
                      type="monotone"
                      dataKey="Solde"
                      stroke="#1d4ed8"
                      strokeWidth={2.5}
                      fill="url(#balanceGradient)"
                    />
                  </AreaChart>
                </ResponsiveContainer>
              </div>
            )}
          </CardBody>
        </Card>

        <Card>
          <CardHeader
            title="Historique des soldes bancaires"
            subtitle="Chaque point provient d'une synchronisation enregistrée"
            icon={<Landmark className="h-5 w-5" />}
          />
          <CardBody>
            {bankHistoryData.length === 0 ? (
              <EmptyState
                title="Aucun solde bancaire disponible"
                description="Configurez l'API Ecobank (administrateur) pour alimenter cet historique."
              />
            ) : (
              <div className="h-[280px]">
                <ResponsiveContainer width="100%" height="100%">
                  <LineChart data={bankHistoryData} margin={{ top: 8, right: 8, left: -18, bottom: 0 }}>
                    <CartesianGrid strokeDasharray="3 3" stroke="#eef2f7" vertical={false} />
                    <XAxis dataKey="label" tick={{ fontSize: 10, fill: '#64748b' }} axisLine={false} tickLine={false} />
                    <YAxis tick={{ fontSize: 11, fill: '#94a3b8' }} axisLine={false} tickLine={false} />
                    <Tooltip content={<ChartTooltip currency={summary.bank.currency || currency} />} />
                    <Line type="monotone" dataKey="Solde" stroke="#0ea5e9" strokeWidth={2.5} dot={{ r: 2 }} />
                  </LineChart>
                </ResponsiveContainer>
              </div>
            )}
          </CardBody>
        </Card>

        <Card>
          <CardHeader
            title="Écarts financiers et bancaires"
            subtitle="Comparaison à chaque synchronisation"
            icon={<Scale className="h-5 w-5" />}
          />
          <CardBody>
            {gapHistoryData.length === 0 ? (
              <EmptyState
                title="Aucun écart calculable"
                description="Un solde bancaire réel est nécessaire pour calculer l'écart."
              />
            ) : (
              <div className="h-[280px]">
                <ResponsiveContainer width="100%" height="100%">
                  <BarChart data={gapHistoryData} margin={{ top: 8, right: 8, left: -18, bottom: 0 }}>
                    <CartesianGrid strokeDasharray="3 3" stroke="#eef2f7" vertical={false} />
                    <XAxis dataKey="label" tick={{ fontSize: 10, fill: '#64748b' }} axisLine={false} tickLine={false} />
                    <YAxis tick={{ fontSize: 11, fill: '#94a3b8' }} axisLine={false} tickLine={false} />
                    <Tooltip content={<ChartTooltip currency={currency} />} />
                    <Legend iconType="circle" wrapperStyle={{ fontSize: 12 }} />
                    <Bar dataKey="Financier" fill="#1d4ed8" radius={[6, 6, 0, 0]} maxBarSize={28} />
                    <Bar dataKey="Bancaire" fill="#60a5fa" radius={[6, 6, 0, 0]} maxBarSize={28} />
                    <Bar dataKey="Écart" radius={[6, 6, 0, 0]} maxBarSize={28}>
                      {gapHistoryData.map((entry, index) => (
                        <Cell
                          key={`gap-${index}`}
                          fill={Number(entry.Écart) === 0 ? '#047857' : Number(entry.Écart) > 0 ? '#f59e0b' : '#dc2626'}
                        />
                      ))}
                    </Bar>
                  </BarChart>
                </ResponsiveContainer>
              </div>
            )}
          </CardBody>
        </Card>
      </div>
    </div>
  )
}
