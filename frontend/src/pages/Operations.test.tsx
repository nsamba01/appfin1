import { screen, waitFor, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { beforeEach, describe, expect, it, vi } from 'vitest'

import { authService } from '../services/auth'
import { financeService } from '../services/finance'
import { financeUser } from '../test/factories'
import { renderWithProviders } from '../test/render'
import type { Operation } from '../types'
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
    list: vi.fn(),
    create: vi.fn(),
    update: vi.fn(),
    remove: vi.fn(),
    history: vi.fn(),
    balances: vi.fn(),
    summary: vi.fn(),
    charts: vi.fn(),
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
const mockedFinance = vi.mocked(financeService)

const sampleOperation: Operation = {
  id: 1,
  date: '2026-11-01',
  label: 'Financement reçu',
  amount: '5000.00',
  operation_type: 'ENTRY',
  operation_type_label: 'Entrée',
  reference: 'FIN-001',
  observation: 'Apport initial',
  signed_amount: '5000.00',
  created_by_username: 'Emanuel',
  updated_by_username: null,
  is_deleted: false,
  deleted_at: null,
  created_at: '2026-11-01T09:00:00Z',
  updated_at: '2026-11-01T09:00:00Z',
}

const page = (results: Operation[]) => ({
  count: results.length,
  next: null,
  previous: null,
  results,
})

beforeEach(() => {
  vi.clearAllMocks()
  mockedAuth.refresh.mockResolvedValue({ access: 'token', user: financeUser })
  mockedFinance.list.mockResolvedValue(page([sampleOperation]))
  mockedFinance.history.mockResolvedValue([])
})

describe('Operations page', () => {
  it('lists operations with amounts and types', async () => {
    renderWithProviders(<App />, { route: '/operations' })

    expect(await screen.findByRole('heading', { name: /opérations financières/i, level: 1 })).toBeInTheDocument()
    const table = await screen.findByTestId('operations-table')
    expect(within(table).getByText('Financement reçu')).toBeInTheDocument()
    expect(within(table).getByText(/entrée/i)).toBeInTheDocument()
    expect(within(table).getByText(/fin-001/i)).toBeInTheDocument()
    expect(within(table).getByText(/\+/)).toBeInTheDocument()
  })

  it('filters by type and search term', async () => {
    const user = userEvent.setup()
    renderWithProviders(<App />, { route: '/operations' })
    await screen.findByTestId('operations-table')

    await user.selectOptions(screen.getByLabelText(/filtrer par type/i), 'EXIT')
    await waitFor(() =>
      expect(mockedFinance.list).toHaveBeenCalledWith(
        expect.objectContaining({ operation_type: 'EXIT' }),
      ),
    )

    await user.type(screen.getByLabelText(/rechercher une opération/i), 'matériel')
    await waitFor(
      () =>
        expect(mockedFinance.list).toHaveBeenCalledWith(
          expect.objectContaining({ search: 'matériel' }),
        ),
      { timeout: 2000 },
    )
  })

  it('validates the form before calling the API', async () => {
    const user = userEvent.setup()
    renderWithProviders(<App />, { route: '/operations' })
    await screen.findByTestId('operations-table')

    await user.click(screen.getByRole('button', { name: /nouvelle opération/i }))
    await user.click(await screen.findByRole('button', { name: /créer l’opération/i }))

    expect(await screen.findByText(/le libellé doit contenir au moins 3 caractères/i)).toBeInTheDocument()
    expect(screen.getByText(/le montant doit être supérieur à zéro/i)).toBeInTheDocument()
    expect(mockedFinance.create).not.toHaveBeenCalled()
  })

  it('creates an operation and refreshes the list', async () => {
    mockedFinance.create.mockResolvedValue(sampleOperation)
    const user = userEvent.setup()
    renderWithProviders(<App />, { route: '/operations' })
    await screen.findByTestId('operations-table')

    await user.click(screen.getByRole('button', { name: /nouvelle opération/i }))
    await user.type(screen.getByLabelText(/^libellé/i), 'Achat de matériel')
    await user.type(screen.getByLabelText(/^montant/i), '1200')
    await user.selectOptions(screen.getByLabelText(/type d'opération/i), 'EXIT')
    await user.click(screen.getByRole('button', { name: /créer l’opération/i }))

    await waitFor(() =>
      expect(mockedFinance.create).toHaveBeenCalledWith(
        expect.objectContaining({
          label: 'Achat de matériel',
          amount: '1200',
          operation_type: 'EXIT',
        }),
      ),
    )
    await waitFor(() => expect(mockedFinance.list).toHaveBeenCalledTimes(2))
  })

  it('shows a French error when the API refuses the creation', async () => {
    mockedFinance.create.mockRejectedValue({
      isAxiosError: true,
      toJSON: () => ({}),
      response: {
        data: { label: ['Le libellé doit contenir au moins 3 caractères.'] },
        status: 400,
      },
    })
    const user = userEvent.setup()
    renderWithProviders(<App />, { route: '/operations' })
    await screen.findByTestId('operations-table')

    await user.click(screen.getByRole('button', { name: /nouvelle opération/i }))
    await user.type(screen.getByLabelText(/^libellé/i), 'Achat')
    await user.type(screen.getByLabelText(/^montant/i), '10')
    await user.click(screen.getByRole('button', { name: /créer l’opération/i }))

    expect(
      (await screen.findAllByText(/le libellé doit contenir au moins 3 caractères/i)).length,
    ).toBeGreaterThan(0)
  })

  it('archives an operation only after confirmation', async () => {
    mockedFinance.remove.mockResolvedValue(undefined)
    const user = userEvent.setup()
    renderWithProviders(<App />, { route: '/operations' })
    const table = await screen.findByTestId('operations-table')

    await user.click(within(table).getByRole('button', { name: /supprimer financement reçu/i }))
    expect(await screen.findByText(/archiver cette opération/i)).toBeInTheDocument()
    expect(mockedFinance.remove).not.toHaveBeenCalled()

    await user.click(screen.getByRole('button', { name: /^archiver$/i }))
    await waitFor(() => expect(mockedFinance.remove).toHaveBeenCalledWith(1))
  })

  it('shows an empty state when no operation matches', async () => {
    mockedFinance.list.mockResolvedValue(page([]))
    renderWithProviders(<App />, { route: '/operations' })
    expect(await screen.findByText(/aucune opération trouvée/i)).toBeInTheDocument()
  })
})
