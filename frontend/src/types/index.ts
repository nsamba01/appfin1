export type Role = 'FINANCE' | 'ADMIN'

export interface UserPermissions {
  can_manage_users: boolean
  can_manage_bank_config: boolean
  can_view_audit_logs: boolean
  can_manage_operations: boolean
  can_view_bank_data: boolean
  can_export: boolean
}

export interface User {
  id: number
  username: string
  full_name: string
  email: string
  role: Role
  role_label: string
  is_active: boolean
  must_change_password: boolean
  last_login_at: string | null
  last_login_ip: string | null
  is_locked?: boolean
  created_at?: string
  updated_at?: string
  permissions?: UserPermissions
  application?: {
    company_name: string
    currency: string
    role: Role
  }
}

export type OperationType = 'ENTRY' | 'EXIT'

export interface Operation {
  id: number
  date: string
  label: string
  amount: string
  operation_type: OperationType
  operation_type_label: string
  reference: string
  observation: string
  signed_amount: string
  created_by_username: string | null
  updated_by_username: string | null
  is_deleted: boolean
  deleted_at: string | null
  created_at: string
  updated_at: string
}

export interface Paginated<T> {
  count: number
  next: string | null
  previous: string | null
  results: T[]
}

export interface FinancialTotals {
  total_entries: string
  total_exits: string
  balance: string
  operation_count: number
}

export type GapStatus = 'EQUAL' | 'FINANCIAL_HIGHER' | 'BANK_HIGHER' | 'UNAVAILABLE'

export type ConnectionStatus = 'NOT_CONFIGURED' | 'CONFIGURED' | 'CONNECTED' | 'ERROR' | 'SANDBOX'

export interface BankInfo {
  name: string
  environment: 'SANDBOX' | 'PRODUCTION'
  environment_label: string
  account_masked: string
  account_name: string
  currency: string
  available_balance: string | null
  current_balance: string | null
  account_status: string
  balance_updated_at: string | null
  source: 'API' | 'SANDBOX' | 'NONE'
  is_sandbox: boolean
  connection_status: ConnectionStatus
  connection_status_label: string
  is_configured: boolean
  is_enabled: boolean
  sandbox_mode_enabled: boolean
  last_sync_at: string | null
  last_sync_status: string | null
  last_sync_message: string
  last_test_at: string | null
  last_test_status: string | null
  last_test_message: string
  sync_interval_minutes: number
  auto_sync_enabled: boolean
}

export interface Alert {
  level: 'info' | 'warning' | 'error' | 'success'
  title: string
  message: string
}

export interface DashboardSummary {
  currency: string
  company_name: string
  date_from: string | null
  date_to: string | null
  generated_at: string
  financial: FinancialTotals & {
    financial_balance: string
    last_operation_at: string | null
    updated_at: string
  }
  bank: BankInfo
  comparison: {
    gap: string | null
    absolute_gap: string | null
    status: GapStatus
    status_label: string
    bank_balance: string | null
    financial_balance: string
    bank_is_sandbox: boolean
    has_real_bank_data: boolean
  }
  unreconciled: {
    count: number
    total_entries: string
    total_exits: string
    net: string
    since: string | null
    note: string
  }
  alerts: Alert[]
}

export interface MonthlyPoint {
  period: string
  entries: string
  exits: string
  balance: string
}

export interface BankHistoryPoint {
  date: string
  label: string
  balance: string
  is_sandbox: boolean
}

export interface GapHistoryPoint {
  date: string
  label: string
  financial_balance: string
  bank_balance: string | null
  gap: string | null
  is_sandbox: boolean
}

export interface DashboardCharts {
  currency: string
  monthly: MonthlyPoint[]
  bank_history: BankHistoryPoint[]
  gap_history: GapHistoryPoint[]
  comparison: { indicator: string; financial: string; bank: string | null }[]
  balances_chart: { name: string; value: string | null }[]
  bank_is_sandbox: boolean
  bank_available: boolean
}

export interface ComparisonRow {
  indicator: string
  financial: string
  bank: string | null
  bank_note: string
  is_date?: boolean
}

export interface ComparisonTable {
  currency: string
  rows: ComparisonRow[]
  gap: {
    gap: string | null
    absolute_gap: string | null
    status: GapStatus
    status_label: string
  }
  bank: BankInfo
}

export interface BalanceSnapshot {
  id: number
  status: string
  source: 'API' | 'SANDBOX'
  is_sandbox: boolean
  available_balance: string | null
  current_balance: string | null
  currency: string
  account_no_masked: string
  account_name: string
  account_status: string
  branch_code: string
  response_code: string
  fetched_at: string
}

export interface SyncLogEntry {
  id: number
  trigger: 'MANUAL' | 'SCHEDULED' | 'TEST'
  trigger_label: string
  status: 'SUCCESS' | 'FAILED' | 'RUNNING' | 'SKIPPED'
  status_label: string
  http_status: number | null
  response_code: string
  message: string
  duration_ms: number
  is_sandbox: boolean
  triggered_by_username: string | null
  created_at: string
}

export interface AuditEntry {
  id: number
  actor_username: string
  action: string
  action_label: string
  entity: string
  entity_id: string
  description: string
  metadata: Record<string, unknown>
  ip_address: string | null
  created_at: string
}

export interface LoginAttemptEntry {
  id: number
  username_attempted: string
  successful: boolean
  ip_address: string | null
  user_agent: string
  reason: string
  created_at: string
}

export interface ApplicationSettings {
  company_name: string
  currency: string
  timezone_label: string
  allow_finance_edit_operations: boolean
  allow_finance_delete_operations: boolean
  operation_edit_window_days: number
  bank_sync_interval_minutes: number
  updated_at: string
}

export interface EcobankConfig {
  is_enabled: boolean
  environment: 'SANDBOX' | 'PRODUCTION'
  base_url: string
  auth_path: string
  balance_path: string
  client_id: string
  affiliate_code: string
  source_code: string
  public_key: string
  ip_address: string | null
  secret_key?: string
  subscription_key?: string
  account_no?: string
  account_name: string
  currency: string
  masked_account_no: string
  service_code: string
  token_request_type: string
  balance_request_type: string
  timeout_seconds: number
  sync_interval_minutes: number
  auto_sync_enabled: boolean
  sandbox_mode_enabled: boolean
  has_secret_key: boolean
  has_subscription_key: boolean
  has_account_no: boolean
  connection_status: ConnectionStatus
  connection_status_label: string
  is_configured: boolean
  sandbox_simulation: boolean
  last_test_at: string | null
  last_test_status: string | null
  last_test_message: string
  last_sync_at: string | null
  last_sync_status: string | null
  last_sync_message: string
  updated_at: string
}
