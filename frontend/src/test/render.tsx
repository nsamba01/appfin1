import { render } from '@testing-library/react'
import type { ReactElement } from 'react'
import { MemoryRouter } from 'react-router-dom'

import { AuthProvider } from '../contexts/AuthContext'
import { ToastProvider } from '../contexts/ToastContext'

export const renderWithProviders = (ui: ReactElement, { route = '/' } = {}) =>
  render(
    <MemoryRouter initialEntries={[route]}>
      <ToastProvider>
        <AuthProvider>{ui}</AuthProvider>
      </ToastProvider>
    </MemoryRouter>,
  )

export const renderWithRouter = renderWithProviders
