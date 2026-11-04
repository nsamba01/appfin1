import { screen } from '@testing-library/react'
import { beforeEach, describe, expect, it, vi } from 'vitest'

import { authService } from '../services/auth'
import { bankingService } from '../services/finance'
import { bankInfo, financeUser } from '../test/factories'
import { renderWithProviders } from '../test/render'
import { App } from '../App'

vi.mock('../services/auth', () => ({
  authService: {
    login: vi.fn(),
    refresh: vi.fn(),
    me: vi.fn(),
    logout: vi.fn(),
    changePassword: vi.fn(),
    roles: vi.fn(),
  },
}))

vi.mock('../services/finance', () => ({
  financeService: {
    summary: vi.fn(),
    charts: vi.fn(),
    list: vi.fn(),
    create: vi.fn(),
    update: vi.fn(),
    remove: vi.fn(),
    history: vi.fn(),
    balances: vi.fn(),
    comparison: vi.fn(),
    downloadExport: vi.fn(),
  },
  bankingService: {
    status: vi.fn(),
    history: vi.fn(),
    config: vi.fn(),
    updateConfig: vi.fn(),
    testConnection: vi.fn(),
    syncNow: vi.fn(),
    logs: vi.fn(),
    clearSecrets: vi.fn(),
  },
}))

const mockedAuth = vi.mocked(authService)
const mockedBanking = vi.mocked(bankingService)

beforeEach(() => {
  vi.clearAllMocks()
  mockedAuth.refresh.mockResolvedValue({ access: 'token', user: financeUser })
  mockedBanking.status.mockResolvedValue(bankInfo)
  mockedBanking.history.mockResolvedValue({ currency: 'USD', results: [] })
})

describe('Bank page', () => {
  it('shows the Ecobank balance, masked account and status', async () => {
    renderWithProviders(<App />, { route: '/bank' })

    expect(await screen.findByText('••••••6858')).toBeInTheDocument()
    expect(screen.getByText('ICHESS FINANCE')).toBeInTheDocument()
    expect(screen.getByText(/^USD$/)).toBeInTheDocument()
    expect(screen.getAllByText(/connecté/i).length).toBeGreaterThan(0)
    expect(screen.getByText(/mis à jour/i)).toBeInTheDocument()
  })

  it('warns clearly when the balance is simulated in sandbox', async () => {
    mockedBanking.status.mockResolvedValue({
      ...bankInfo,
      is_sandbox: true,
      source: 'SANDBOX',
      connection_status: 'SANDBOX',
      connection_status_label: 'Mode sandbox (simulation)',
      account_name: 'COMPTE DE DÉMONSTRATION SANDBOX',
    })
    renderWithProviders(<App />, { route: '/bank' })
    expect(await screen.findByText(/mode sandbox — données simulées/i)).toBeInTheDocument()
    expect(screen.getByText(/ne provient pas de l'api/i)).toBeInTheDocument()
  })

  it('shows unavailable when the API is not configured', async () => {
    mockedBanking.status.mockResolvedValue({
      ...bankInfo,
      available_balance: null,
      current_balance: null,
      connection_status: 'NOT_CONFIGURED',
      connection_status_label: 'Non configuré',
      is_configured: false,
      account_masked: '—',
      account_name: '—',
      currency: '—',
      balance_updated_at: null,
      last_sync_at: null,
      last_sync_status: null,
      last_sync_message: '',
      source: 'NONE',
    })
    renderWithProviders(<App />, { route: '/bank' })
    expect((await screen.findAllByText(/non configuré/i)).length).toBeGreaterThan(0)
    expect(screen.getByText(/aucun solde synchronisé/i)).toBeInTheDocument()
    expect(screen.getByText(/aucun historique/i)).toBeInTheDocument()
  })
})
