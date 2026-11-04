import { api } from './api'
import type { Role, User } from '../types'

export interface LoginResponse {
  access: string
  user: User
}

export const authService = {
  login: async (username: string, password: string) => {
    const { data } = await api.post<LoginResponse>('/auth/login/', { username, password })
    return data
  },
  refresh: async () => {
    const { data } = await api.post<LoginResponse>('/auth/refresh/')
    return data
  },
  me: async () => {
    const { data } = await api.get<User>('/auth/me/')
    return data
  },
  logout: async () => {
    await api.post('/auth/logout/')
  },
  changePassword: async (payload: {
    current_password: string
    new_password: string
    confirm_password: string
  }) => {
    const { data } = await api.post<{ detail: string; user: User }>(
      '/auth/change-password/',
      payload,
    )
    return data
  },
  roles: async () => {
    const { data } = await api.get<{ value: Role; label: string }[]>('/auth/roles/')
    return data
  },
}
