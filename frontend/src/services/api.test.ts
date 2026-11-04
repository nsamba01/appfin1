import { beforeEach, describe, expect, it } from 'vitest'

import { api, extractErrorMessage, extractFieldErrors, getAccessToken, setAccessToken } from './api'

describe('api client', () => {
  beforeEach(() => {
    setAccessToken(null)
  })

  it('stores the access token in memory only', () => {
    setAccessToken('token-123')
    expect(getAccessToken()).toBe('token-123')
    expect(window.localStorage.getItem('access')).toBeNull()
    expect(window.sessionStorage.getItem('access')).toBeNull()
    expect(document.cookie).not.toContain('token-123')
  })

  it('attaches the bearer token to outgoing requests', async () => {
    setAccessToken('token-abc')
    const handler = api.interceptors.request as unknown as {
      handlers: { fulfilled: (config: { headers: Record<string, string> }) => unknown }[]
    }
    const config = handler.handlers[0].fulfilled({ headers: {} }) as {
      headers: { Authorization: string }
    }
    expect(config.headers.Authorization).toBe('Bearer token-abc')
  })

  it('sends cookies with credentials', () => {
    expect(api.defaults.withCredentials).toBe(true)
  })
})

describe('error helpers', () => {
  it('extracts a detail message', () => {
    const error = {
      isAxiosError: true,
      response: { data: { detail: 'Identifiants invalides.' }, status: 401 },
    }
    // axios.isAxiosError checks the flag
    expect(extractErrorMessage({ ...error, toJSON: () => ({}) })).toBeTruthy()
  })

  it('extracts field errors', () => {
    const error = {
      isAxiosError: true,
      toJSON: () => ({}),
      response: { data: { amount: ['Le montant doit être supérieur à zéro.'] } },
    }
    expect(extractFieldErrors(error).amount).toBe('Le montant doit être supérieur à zéro.')
  })

  it('falls back to a generic message', () => {
    expect(extractErrorMessage(new Error('boom'))).toBe('boom')
    expect(extractErrorMessage('weird')).toBe('Une erreur est survenue.')
  })
})
