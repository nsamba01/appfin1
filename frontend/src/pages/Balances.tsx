import { CalendarRange, Landmark, Scale, TrendingDown, TrendingUp, Wallet } from 'lucide-react'
import { useCallback, useEffect, useMemo, useState } from 'react'
import {
  Bar,
  BarChart,
  CartesianGrid,
  Legend,
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
import type { FinancialTotals, MonthlyPoint } from '../types'
import { formatMoney, formatMonth } from '../utils/format'

interface BalancesPayload {
  currency: string
  totals: FinancialTotals
  financial_balance: string
  monthly_series: MonthlyPoint[]
}

export const BalancesPage = () => {
  const { user } = useAuth()
  const [data, setData] = useState<BalancesPayload | null>(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState('')
  const [dateFrom, setDateFrom] = useState('')
  const [dateTo, setDateTo] = useState('')

  const load = useCallback(async () => {
    setLoading(true)
    setError('')
    try {
      const payload = await financeService.balances({
        date_from: dateFrom || undefined,
        date_to: dateTo || undefined,
      })
      setData(payload as BalancesPayload)
    } catch (err) {
      setError(extractErrorMessage(err, 'Impossible de charger les balances.'))
    } finally {
      setLoading(false)
    }
  }, [dateFrom, dateTo])

  useEffect(() => {
    void load()
  }, [load])

  const currency = data?.currency ?? user?.application?.currency ?? 'USD'

  const chartData = useMemo(
    () =>
      (data?.monthly_series ?? []).map((point) => ({
        period: formatMonth(point.period),
        Entrées: Number(point.entries),
        Sorties: Number(point.exits),
        Solde: Number(point.balance),
      })),
    [data?.monthly_series],
  )

  if (loading && !data) return <Spinner label="Calcul des balances…" />
  if (error && !data) return <ErrorState message={error} onRetry={() => void load()} />
  if (!data) return null

  return (
    <div className="animate-fade-in">
      <PageHeader
        eyebrow="Module financier"
        title="Balances financières"
        description="Totaux des entrées et sorties calculés côté serveur avec une précision décimale."
        actions={
          <div className="flex flex-wrap items-center gap-2">
            <div className="flex items-center gap-2 rounded-xl border border-slate-200 bg-white px-3 py-1.5 shadow-sm">
              <CalendarRange className="h-4 w-4 text-slate-400" />
              <input
                type="date"
                aria-label="Date de début"
                value={dateFrom}
                onChange={(event) => setDateFrom(event.target.value)}
                className="w-[128px] border-0 bg-transparent p-0 text-sm focus:outline-none"
              />
              <span className="text-slate-300">→</span>
              <input
                type="date"
                aria-label="Date de fin"
                value={dateTo}
                onChange={(event) => setDateTo(event.target.value)}
                className="w-[128px] border-0 bg-transparent p-0 text-sm focus:outline-none"
              />
            </div>
            <Button variant="secondary" onClick={() => void load()} loading={loading}>
              Actualiser
            </Button>
          </div>
        }
      />

      <div className="grid gap-4 sm:grid-cols-2 xl:grid-cols-4">
        <StatCard
          label="Total des entrées"
          value={formatMoney(data.totals.total_entries, currency)}
          icon={<TrendingUp className="h-5 w-5" />}
          tone="success"
        />
        <StatCard
          label="Total des sorties"
          value={formatMoney(data.totals.total_exits, currency)}
          icon={<TrendingDown className="h-5 w-5" />}
          tone="danger"
        />
        <StatCard
          label="Solde financier disponible"
          value={formatMoney(data.financial_balance, currency)}
          hint="Entrées − sorties"
          icon={<Wallet className="h-5 w-5" />}
          tone={Number(data.financial_balance) >= 0 ? 'success' : 'danger'}
        />
        <StatCard
          label="Balance financière"
          value={formatMoney(data.totals.balance, currency)}
          hint={`${data.totals.operation_count} opération(s)`}
          icon={<Scale className="h-5 w-5" />}
          tone="neutral"
        />
      </div>

      <div className="mt-6 grid gap-6 xl:grid-cols-3">
        <Card className="xl:col-span-2">
          <CardHeader
            title="Évolution mensuelle"
            subtitle="Entrées, sorties et solde cumulé"
            icon={<TrendingUp className="h-5 w-5" />}
          />
          <CardBody>
            {chartData.length === 0 ? (
              <EmptyState title="Aucune donnée sur la période" />
            ) : (
              <div className="h-[320px]">
                <ResponsiveContainer width="100%" height="100%">
                  <BarChart data={chartData} margin={{ top: 8, right: 8, left: -18, bottom: 0 }}>
                    <CartesianGrid strokeDasharray="3 3" stroke="#eef2f7" vertical={false} />
                    <XAxis dataKey="period" tick={{ fontSize: 11, fill: '#64748b' }} axisLine={false} tickLine={false} />
                    <YAxis tick={{ fontSize: 11, fill: '#94a3b8' }} axisLine={false} tickLine={false} />
                    <Tooltip
                      formatter={(value: number) => formatMoney(value, currency)}
                      contentStyle={{ borderRadius: 12, border: '1px solid #e2e8f0', fontSize: 12 }}
                    />
                    <Legend iconType="circle" wrapperStyle={{ fontSize: 12 }} />
                    <Bar dataKey="Entrées" fill="#047857" radius={[6, 6, 0, 0]} maxBarSize={30} />
                    <Bar dataKey="Sorties" fill="#dc2626" radius={[6, 6, 0, 0]} maxBarSize={30} />
                    <Bar dataKey="Solde" fill="#1d4ed8" radius={[6, 6, 0, 0]} maxBarSize={30} />
                  </BarChart>
                </ResponsiveContainer>
              </div>
            )}
          </CardBody>
        </Card>

        <Card>
          <CardHeader title="Détail par mois" subtitle="Solde cumulé" icon={<Landmark className="h-5 w-5" />} />
          <div className="table-shell max-h-[360px] overflow-y-auto">
            <table className="min-w-full divide-y divide-slate-100">
              <thead className="sticky top-0 bg-slate-50/95 backdrop-blur">
                <tr>
                  <th className="th">Période</th>
                  <th className="th text-right">Entrées</th>
                  <th className="th text-right">Solde</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-slate-100">
                {data.monthly_series.length === 0 ? (
                  <tr>
                    <td colSpan={3} className="td text-center text-slate-400">
                      Aucune donnée
                    </td>
                  </tr>
                ) : (
                  data.monthly_series
                    .slice()
                    .reverse()
                    .map((point) => (
                      <tr key={point.period} className="hover:bg-slate-50/70">
                        <td className="td font-medium text-ink-800">{formatMonth(point.period)}</td>
                        <td className="td text-right tabular-nums text-emerald-700">
                          {formatMoney(point.entries, currency)}
                        </td>
                        <td className="td text-right">
                          <Badge tone={Number(point.balance) >= 0 ? 'success' : 'danger'}>
                            {formatMoney(point.balance, currency)}
                          </Badge>
                        </td>
                      </tr>
                    ))
                )}
              </tbody>
            </table>
          </div>
        </Card>
      </div>

      <Card className="mt-6">
        <CardBody>
          <div className="flex items-start gap-3">
            <span className="mt-0.5 flex h-9 w-9 items-center justify-center rounded-xl bg-brand-50 text-brand-600">
              <Scale className="h-5 w-5" />
            </span>
            <div>
              <p className="text-sm font-semibold text-ink-900">Méthode de calcul</p>
              <p className="mt-1 text-sm leading-relaxed text-slate-600">
                Solde financier = total des entrées − total des sorties. Balance financière =
                total des entrées − total des sorties. Ces montants sont calculés par le serveur
                en base décimale et ne proviennent jamais d'un calcul navigateur.
              </p>
            </div>
          </div>
        </CardBody>
      </Card>
    </div>
  )
}
