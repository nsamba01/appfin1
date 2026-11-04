import { screen, waitFor } from '@testing-library/react'
import { beforeEach, describe, expect, it, vi } from 'vitest'

import { authService } from './services/auth'
import { financeService } from './services/finance'
import { adminService } from './services/admin'
import { App } from './App'
import { adminUser, bankInfo, dashboardSummary, financeUser } from './test/factories'
import { renderWithProviders } from './test/render'

vi.mock('./services/auth', () => ({
  authService: {
    login: vi.fn(),
    refresh: vi.fn(),
    me: vi.fn(),
    logout: vi.fn(),
    changePassword: vi.fn(),
    roles: vi.fn(),
  },
}))

vi.mock('./services/finance', () => ({
  financeService: {
    summary: vi.fn(),
    charts: vi.fn(),
    history: vi.fn(),
    list: vi.fn(),
    create: vi.fn(),
    update: vi.fn(),
    remove: vi.fn(),
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

vi.mock('./services/admin', () => ({
  adminService: {
    listUsers: vi.fn(),
    createUser: vi.fn(),
    updateUser: vi.fn(),
    resetPassword: vi.fn(),
    toggleActive: vi.fn(),
    unlock: vi.fn(),
    settings: vi.fn(),
    updateSettings: vi.fn(),
    auditLogs: vi.fn(),
    loginLogs: vi.fn(),
    financeHistory: vi.fn(),
  },
}))

const mockedAuth = vi.mocked(authService)
const mockedFinance = vi.mocked(financeService)
const mockedAdmin = vi.mocked(adminService)

const emptyPage = { count: 0, next: null, previous: null, results: [] }

const chartsPayload = {
  currency: 'USD',
  monthly: [],
  bank_history: [],
  gap_history: [],
  comparison: [],
  balances_chart: [],
  bank_is_sandbox: false,
  bank_available: true,
}

beforeEach(() => {
  vi.clearAllMocks()
  mockedFinance.summary.mockResolvedValue(dashboardSummary)
  mockedFinance.charts.mockResolvedValue(chartsPayload)
  mockedFinance.list.mockResolvedValue(emptyPage)
  mockedAdmin.listUsers.mockResolvedValue(emptyPage)
})

describe('Routing and access control', () => {
  it('redirects an unauthenticated visitor to the login page', async () => {
    mockedAuth.refresh.mockRejectedValue(new Error('no session'))
    renderWithProviders(<App />, { route: '/' })
    expect(await screen.findByRole('heading', { name: 'Connexion', level: 2 })).toBeInTheDocument()
  })

  it('shows the dashboard once authenticated', async () => {
    mockedAuth.refresh.mockResolvedValue({ access: 'token', user: financeUser })
    renderWithProviders(<App />, { route: '/' })
    expect(
      await screen.findByRole('heading', { name: /tableau de bord financier/i, level: 1 }),
    ).toBeInTheDocument()
    expect(screen.getAllByText(/solde financier interne/i).length).toBeGreaterThan(0)
    expect(screen.getAllByText(/solde bancaire ecobank/i).length).toBeGreaterThan(0)
  })

  it('prevents a finance user from opening an admin page', async () => {
    mockedAuth.refresh.mockResolvedValue({ access: 'token', user: financeUser })
    renderWithProviders(<App />, { route: '/admin/users' })
    expect(
      await screen.findByRole('heading', { name: /tableau de bord financier/i, level: 1 }),
    ).toBeInTheDocument()
    expect(screen.queryByRole('heading', { name: /gestion des utilisateurs/i, level: 1 })).toBeNull()
  })

  it('allows an administrator to open the users page', async () => {
    mockedAuth.refresh.mockResolvedValue({ access: 'token', user: adminUser })
    renderWithProviders(<App />, { route: '/admin/users' })
    expect(
      await screen.findByRole('heading', { name: /gestion des utilisateurs/i, level: 1 }),
    ).toBeInTheDocument()
    await waitFor(() => expect(mockedAdmin.listUsers).toHaveBeenCalled())
  })

  it('hides admin navigation from finance users', async () => {
    mockedAuth.refresh.mockResolvedValue({ access: 'token', user: financeUser })
    renderWithProviders(<App />, { route: '/' })
    await screen.findByRole('heading', { name: /tableau de bord financier/i, level: 1 })
    expect(screen.queryByRole('link', { name: /utilisateurs/i })).toBeNull()
    expect(screen.queryByRole('link', { name: /configuration ecobank/i })).toBeNull()
  })

  it('shows a not-found page for unknown routes', async () => {
    mockedAuth.refresh.mockResolvedValue({ access: 'token', user: financeUser })
    renderWithProviders(<App />, { route: '/inconnu' })
    expect(await screen.findByText('404')).toBeInTheDocument()
  })
})

describe('Dashboard', () => {
  it('renders the computed values from the API', async () => {
    mockedAuth.refresh.mockResolvedValue({ access: 'token', user: financeUser })
    mockedFinance.summary.mockResolvedValue({
      ...dashboardSummary,
      bank: { ...bankInfo, available_balance: null, is_sandbox: false },
      comparison: {
        ...dashboardSummary.comparison,
        gap: null,
        status: 'UNAVAILABLE',
        status_label: 'Comparaison indisponible (aucun solde bancaire réel)',
        bank_balance: null,
      },
      alerts: [
        {
          level: 'info',
          title: 'API Ecobank non configurée',
          message: 'Aucun identifiant bancaire enregistré.',
        },
      ],
    })
    renderWithProviders(<App />, { route: '/' })

    expect((await screen.findAllByText(/api ecobank non configurée/i)).length).toBeGreaterThan(0)
    expect(screen.getAllByText(/comparaison indisponible/i).length).toBeGreaterThan(0)
    expect(screen.getAllByText(/3 opération/).length).toBeGreaterThan(0)
  })

  it('shows a sandbox warning when the bank data is simulated', async () => {
    mockedAuth.refresh.mockResolvedValue({ access: 'token', user: financeUser })
    mockedFinance.summary.mockResolvedValue({
      ...dashboardSummary,
      bank: { ...bankInfo, is_sandbox: true, source: 'SANDBOX' },
      comparison: {
        ...dashboardSummary.comparison,
        status: 'UNAVAILABLE',
        gap: null,
        bank_is_sandbox: true,
        has_real_bank_data: false,
      },
      alerts: [
        {
          level: 'warning',
          title: 'Mode sandbox actif',
          message: 'Le solde bancaire affiché est simulé (sandbox).',
        },
      ],
    })
    renderWithProviders(<App />, { route: '/' })
    expect((await screen.findAllByText(/mode sandbox actif/i))[0]).toBeInTheDocument()
    expect(screen.getAllByText(/simulation sandbox/i).length).toBeGreaterThan(0)
  })

  it('reports a network error with a retry action', async () => {
    mockedAuth.refresh.mockResolvedValue({ access: 'token', user: financeUser })
    mockedFinance.summary.mockRejectedValue({
      isAxiosError: true,
      toJSON: () => ({}),
      response: { data: { detail: 'Erreur serveur.' }, status: 500 },
    })
    renderWithProviders(<App />, { route: '/' })
    expect(await screen.findByRole('button', { name: /réessayer/i })).toBeInTheDocument()
    expect(screen.getAllByText('Erreur serveur.').length).toBeGreaterThan(0)
  })
})
