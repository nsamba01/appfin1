import { api } from './api'
import type {
  BalanceSnapshot,
  DashboardCharts,
  DashboardSummary,
  ComparisonTable,
  Operation,
  OperationType,
  Paginated,
  FinancialTotals,
  MonthlyPoint,
  BankInfo,
  SyncLogEntry,
} from '../types'

export interface OperationFilters {
  date_from?: string
  date_to?: string
  operation_type?: OperationType | ''
  search?: string
  page?: number
  page_size?: number
  ordering?: string
  include_deleted?: boolean
}

export interface OperationInput {
  date: string
  label: string
  amount: string
  operation_type: OperationType
  reference?: string
  observation?: string
}

const cleanParams = (filters: object): Record<string, unknown> => {
  const params: Record<string, unknown> = {}
  for (const [key, value] of Object.entries(filters as Record<string, unknown>)) {
    if (value !== undefined && value !== null && value !== '') params[key] = value
  }
  return params
}

export const financeService = {
  list: async (filters: OperationFilters = {}) => {
    const { data } = await api.get<Paginated<Operation>>('/finance/operations/', {
      params: cleanParams(filters),
    })
    return data
  },
  create: async (payload: OperationInput) => {
    const { data } = await api.post<Operation>('/finance/operations/', payload)
    return data
  },
  update: async (id: number, payload: Partial<OperationInput>) => {
    const { data } = await api.patch<Operation>(`/finance/operations/${id}/`, payload)
    return data
  },
  remove: async (id: number) => {
    await api.delete(`/finance/operations/${id}/`)
  },
  history: async (id: number) => {
    const { data } = await api.get<
      { id: number; action: string; action_label: string; description: string; actor_username: string; created_at: string }[]
    >(`/finance/operations/${id}/history/`)
    return data
  },
  balances: async (filters: { date_from?: string; date_to?: string } = {}) => {
    const { data } = await api.get<{
      currency: string
      date_from: string | null
      date_to: string | null
      totals: FinancialTotals
      financial_balance: string
      monthly_series: MonthlyPoint[]
      daily_series: { period: string; entries: string; exits: string; net: string }[]
    }>('/finance/balances/', { params: cleanParams(filters) })
    return data
  },
  exportUrl: (fileFormat: 'xlsx' | 'pdf', filters: OperationFilters = {}) => {
    const params = new URLSearchParams({
      file_format: fileFormat,
      ...(cleanParams(filters) as Record<string, string>),
    })
    return `/finance/operations/export/?${params.toString()}`
  },
  downloadExport: async (fileFormat: 'xlsx' | 'pdf', filters: OperationFilters = {}) => {
    const { data, headers } = await api.get<Blob>('/finance/operations/export/', {
      params: cleanParams({ ...filters, file_format: fileFormat }),
      responseType: 'blob',
    })
    const disposition = String(headers['content-disposition'] ?? '')
    const match = /filename="?([^";]+)"?/.exec(disposition)
    const filename = match?.[1] ?? `operations.${fileFormat}`
    const url = window.URL.createObjectURL(data)
    const link = document.createElement('a')
    link.href = url
    link.download = filename
    document.body.appendChild(link)
    link.click()
    link.remove()
    window.URL.revokeObjectURL(url)
  },
  summary: async (filters: { date_from?: string; date_to?: string } = {}) => {
    const { data } = await api.get<DashboardSummary>('/dashboard/summary/', {
      params: cleanParams(filters),
    })
    return data
  },
  charts: async (filters: { date_from?: string; date_to?: string } = {}) => {
    const { data } = await api.get<DashboardCharts>('/dashboard/charts/', {
      params: cleanParams(filters),
    })
    return data
  },
  comparison: async (filters: { date_from?: string; date_to?: string } = {}) => {
    const { data } = await api.get<ComparisonTable>('/dashboard/comparison/', {
      params: cleanParams(filters),
    })
    return data
  },
}

export const bankingService = {
  status: async () => {
    const { data } = await api.get<{ bank: BankInfo }>('/banking/status/')
    return data.bank
  },
  history: async (days = 90) => {
    const { data } = await api.get<{ currency: string; results: BalanceSnapshot[] }>(
      '/banking/history/',
      { params: { days } },
    )
    return data
  },
  config: async () => {
    const { data } = await api.get<Record<string, unknown>>('/banking/config/')
    return data
  },
  updateConfig: async (payload: Record<string, unknown>) => {
    const { data } = await api.patch('/banking/config/', payload)
    return data
  },
  testConnection: async () => {
    const { data } = await api.post<{
      success: boolean
      status: string
      message: string
      duration_ms: number
      tested_at: string
    }>('/banking/config/test/')
    return data
  },
  syncNow: async () => {
    const { data } = await api.post<SyncLogEntry & { success: boolean; bank: BankInfo }>(
      '/banking/sync/',
    )
    return data
  },
  logs: async () => {
    const { data } = await api.get<{ results: SyncLogEntry[] }>('/banking/logs/')
    return data.results
  },
  clearSecrets: async () => {
    const { data } = await api.post('/banking/config/clear-secrets/')
    return data
  },
}
