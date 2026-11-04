import { api } from './api'
import type {
  ApplicationSettings,
  AuditEntry,
  LoginAttemptEntry,
  Paginated,
  Role,
  User,
} from '../types'

export const adminService = {
  listUsers: async (params: { search?: string; role?: Role | ''; is_active?: boolean | '' } = {}) => {
    const { data } = await api.get<Paginated<User>>('/admin/users/', {
      params: Object.fromEntries(
        Object.entries(params).filter(([, value]) => value !== '' && value !== undefined),
      ),
    })
    return data
  },
  createUser: async (payload: {
    username: string
    full_name?: string
    email?: string
    role: Role
    password: string
    force_password_change: boolean
  }) => {
    const { data } = await api.post<User>('/admin/users/', payload)
    return data
  },
  updateUser: async (id: number, payload: Partial<User>) => {
    const { data } = await api.patch<User>(`/admin/users/${id}/`, payload)
    return data
  },
  resetPassword: async (id: number, newPassword: string, forceChange: boolean) => {
    const { data } = await api.post<{ detail: string }>(`/admin/users/${id}/password/`, {
      new_password: newPassword,
      force_change: forceChange,
    })
    return data
  },
  toggleActive: async (id: number) => {
    const { data } = await api.post<User>(`/admin/users/${id}/toggle-active/`)
    return data
  },
  unlock: async (id: number) => {
    const { data } = await api.post<User>(`/admin/users/${id}/unlock/`)
    return data
  },
  settings: async () => {
    const { data } = await api.get<ApplicationSettings>('/admin/settings/')
    return data
  },
  updateSettings: async (payload: Partial<ApplicationSettings>) => {
    const { data } = await api.patch<ApplicationSettings>('/admin/settings/', payload)
    return data
  },
  auditLogs: async (params: {
    search?: string
    action?: string
    date_from?: string
    date_to?: string
    page?: number
  } = {}) => {
    const { data } = await api.get<Paginated<AuditEntry>>('/admin/audit-logs/', {
      params: Object.fromEntries(Object.entries(params).filter(([, v]) => v !== '' && v !== undefined)),
    })
    return data
  },
  loginLogs: async (params: { username?: string; successful?: boolean | ''; page?: number } = {}) => {
    const { data } = await api.get<Paginated<LoginAttemptEntry>>('/admin/login-logs/', {
      params: Object.fromEntries(Object.entries(params).filter(([, v]) => v !== '' && v !== undefined)),
    })
    return data
  },
  financeHistory: async (params: { search?: string; page?: number } = {}) => {
    const { data } = await api.get<Paginated<AuditEntry>>('/finance/history/', {
      params: Object.fromEntries(Object.entries(params).filter(([, v]) => v !== '' && v !== undefined)),
    })
    return data
  },
}
