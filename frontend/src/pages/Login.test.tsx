import { screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { describe, expect, it, vi } from 'vitest'

import { authService } from '../services/auth'
import { renderWithProviders } from '../test/render'
import { financeUser } from '../test/factories'
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

const mockedAuth = vi.mocked(authService)

const renderLogin = () =>
  renderWithProviders(<App />, { route: '/login' })

describe('Login page', () => {
  it('renders the login form', async () => {
    mockedAuth.refresh.mockRejectedValue(new Error('no session'))
    renderLogin()
    expect(await screen.findByRole('heading', { name: 'Connexion', level: 2 })).toBeInTheDocument()
    expect(screen.getByLabelText(/identifiant/i)).toBeInTheDocument()
    expect(screen.getByLabelText(/^mot de passe/i)).toBeInTheDocument()
    expect(screen.getByRole('button', { name: /se connecter/i })).toBeInTheDocument()
  })

  it('refuses to submit empty credentials', async () => {
    mockedAuth.refresh.mockRejectedValue(new Error('no session'))
    const user = userEvent.setup()
    renderLogin()

    await user.click(await screen.findByRole('button', { name: /se connecter/i }))
    expect(await screen.findByTestId('login-error')).toHaveTextContent(
      /renseigner votre identifiant/i,
    )
    expect(mockedAuth.login).not.toHaveBeenCalled()
  })

  it('shows the API error message on invalid credentials', async () => {
    mockedAuth.refresh.mockRejectedValue(new Error('no session'))
    mockedAuth.login.mockRejectedValue({
      isAxiosError: true,
      toJSON: () => ({}),
      response: { data: { detail: 'Identifiants invalides.' }, status: 401 },
    })
    const user = userEvent.setup()
    renderLogin()

    await user.type(await screen.findByLabelText(/^identifiant/i), 'Emanuel')
    await user.type(screen.getByLabelText(/^mot de passe/i), 'mauvais')
    await user.click(screen.getByRole('button', { name: /se connecter/i }))

    await waitFor(() => expect(mockedAuth.login).toHaveBeenCalledWith('Emanuel', 'mauvais'))
    expect(await screen.findByTestId('login-error')).toHaveTextContent('Identifiants invalides.')
  })

  it('signs in and leaves the login page on success', async () => {
    mockedAuth.refresh.mockRejectedValue(new Error('no session'))
    mockedAuth.login.mockResolvedValue({ access: 'access-token', user: financeUser })
    mockedAuth.me.mockResolvedValue(financeUser)
    const user = userEvent.setup()
    renderLogin()

    await user.type(await screen.findByLabelText(/^identifiant/i), 'Emanuel')
    await user.type(screen.getByLabelText(/^mot de passe/i), 'MotDePasse#2026')
    await user.click(screen.getByRole('button', { name: /se connecter/i }))

    await waitFor(() => expect(mockedAuth.login).toHaveBeenCalledWith('Emanuel', 'MotDePasse#2026'))
    await waitFor(() => expect(screen.queryByRole('button', { name: /se connecter/i })).toBeNull())
  })

  it('redirects a pending password change to the dedicated screen', async () => {
    const pendingUser = { ...financeUser, must_change_password: true }
    mockedAuth.refresh.mockResolvedValue({ access: 'token', user: pendingUser })
    mockedAuth.me.mockResolvedValue(pendingUser)
    renderWithProviders(<App />, { route: '/' })
    expect(
      await screen.findByRole('heading', { name: /changement de mot de passe/i, level: 1 }),
    ).toBeInTheDocument()
  })
})
