import axios, { AxiosError, type AxiosInstance, type InternalAxiosRequestConfig } from 'axios'

export const API_BASE_URL = import.meta.env.VITE_API_BASE_URL || '/api'

export const api: AxiosInstance = axios.create({
  baseURL: API_BASE_URL,
  withCredentials: true,
  timeout: 30_000,
  headers: { 'Content-Type': 'application/json', Accept: 'application/json' },
})

let accessToken: string | null = null
let refreshHandler: (() => Promise<string | null>) | null = null
let unauthorizedHandler: (() => void) | null = null

export const setAccessToken = (token: string | null): void => {
  accessToken = token
}

export const getAccessToken = (): string | null => accessToken

export const registerRefreshHandler = (handler: () => Promise<string | null>): void => {
  refreshHandler = handler
}

export const registerUnauthorizedHandler = (handler: () => void): void => {
  unauthorizedHandler = handler
}

api.interceptors.request.use((config: InternalAxiosRequestConfig) => {
  if (accessToken && !config.headers.Authorization) {
    config.headers.Authorization = `Bearer ${accessToken}`
  }
  return config
})

let refreshPromise: Promise<string | null> | null = null
let sessionExpiredFired = false

interface RetryableConfig extends InternalAxiosRequestConfig {
  _retry?: boolean
}

api.interceptors.response.use(
  (response) => response,
  async (error: AxiosError) => {
    const status = error.response?.status
    const config = error.config as RetryableConfig | undefined
    const url = config?.url ?? ''
    const isAuthEndpoint = url.includes('/auth/login/') || url.includes('/auth/refresh/')

    if (status === 401 && config && !config._retry && !isAuthEndpoint) {
      config._retry = true
      if (!refreshPromise) {
        refreshPromise = (refreshHandler?.() ?? Promise.resolve(null)).finally(() => {
          refreshPromise = null
        })
      }
      const token = await refreshPromise
      if (token) {
        config.headers.Authorization = `Bearer ${token}`
        return api.request(config)
      }
      if (!sessionExpiredFired) {
        sessionExpiredFired = true
        unauthorizedHandler?.()
        window.setTimeout(() => {
          sessionExpiredFired = false
        }, 3000)
      }
    }
    return Promise.reject(error)
  },
)

export interface ApiErrorPayload {
  detail?: string
  code?: string
  [key: string]: unknown
}

export const extractErrorMessage = (error: unknown, fallback = 'Une erreur est survenue.'): string => {
  if (axios.isAxiosError(error)) {
    const data = error.response?.data as ApiErrorPayload | undefined
    if (data) {
      if (typeof data.detail === 'string' && data.detail) return data.detail
      const firstKey = Object.keys(data).find((key) => key !== 'code')
      const value = firstKey ? data[firstKey] : undefined
      if (typeof value === 'string') return value
      if (Array.isArray(value) && typeof value[0] === 'string') return value[0]
      if (value && typeof value === 'object') {
        const nested = Object.values(value as Record<string, unknown>)[0]
        if (Array.isArray(nested) && typeof nested[0] === 'string') return nested[0]
        if (typeof nested === 'string') return nested
      }
    }
    if (error.code === 'ECONNABORTED') {
      return 'Le serveur met trop de temps à répondre. Veuillez réessayer.'
    }
    if (!error.response) {
      return 'Impossible de joindre le serveur. Vérifiez votre connexion.'
    }
    return fallback
  }
  if (error instanceof Error && error.message) return error.message
  return fallback
}

export const extractFieldErrors = (error: unknown): Record<string, string> => {
  if (!axios.isAxiosError(error)) return {}
  const data = error.response?.data as Record<string, unknown> | undefined
  if (!data || typeof data !== 'object') return {}
  const out: Record<string, string> = {}
  for (const [key, value] of Object.entries(data)) {
    if (key === 'detail' || key === 'code') continue
    if (typeof value === 'string') out[key] = value
    else if (Array.isArray(value) && typeof value[0] === 'string') out[key] = value[0]
  }
  return out
}
