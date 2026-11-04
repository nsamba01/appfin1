import { Loader2 } from 'lucide-react'
import { Navigate, Route, Routes, useLocation } from 'react-router-dom'

import { useAuth } from './contexts/AuthContext'
import { DashboardLayout } from './layouts/DashboardLayout'
import { BankPage } from './pages/Bank'
import { BalancesPage } from './pages/Balances'
import { ChangePasswordPage } from './pages/ChangePassword'
import { DashboardPage } from './pages/Dashboard'
import { HistoryPage } from './pages/History'
import { LoginPage } from './pages/Login'
import { OperationsPage } from './pages/Operations'
import { AdminAuditPage } from './pages/admin/Audit'
import { AdminBankConfigPage } from './pages/admin/BankConfig'
import { AdminSettingsPage } from './pages/admin/Settings'
import { AdminUsersPage } from './pages/admin/Users'

const FullScreenLoader = () => (
  <div className="flex min-h-screen flex-col items-center justify-center gap-3 bg-slate-50">
    <Loader2 className="h-7 w-7 animate-spin text-brand-600" />
    <p className="text-sm text-slate-500">Vérification de la session…</p>
  </div>
)

const RequireAuth = ({ children }: { children: React.ReactNode }) => {
  const { user, loading } = useAuth()
  const location = useLocation()
  if (loading) return <FullScreenLoader />
  if (!user) return <Navigate to="/login" replace state={{ from: location.pathname }} />
  if (user.must_change_password && location.pathname !== '/change-password') {
    return <Navigate to="/change-password" replace />
  }
  return <>{children}</>
}

const RequireAdmin = ({ children }: { children: React.ReactNode }) => {
  const { user } = useAuth()
  if (!user) return <Navigate to="/login" replace />
  if (user.role !== 'ADMIN') return <Navigate to="/" replace />
  return <>{children}</>
}

const NotFound = () => (
  <div className="flex min-h-[50vh] flex-col items-center justify-center text-center">
    <p className="font-display text-6xl font-extrabold text-brand-200">404</p>
    <h1 className="mt-2 font-display text-xl font-bold text-ink-900">Page introuvable</h1>
    <p className="mt-1 text-sm text-slate-500">La page demandée n'existe pas ou a été déplacée.</p>
    <a
      href="/"
      className="mt-5 inline-flex items-center rounded-xl bg-brand-600 px-4 py-2.5 text-sm font-semibold text-white hover:bg-brand-700"
    >
      Retour au tableau de bord
    </a>
  </div>
)

export const App = () => (
  <Routes>
    <Route path="/login" element={<LoginPage />} />
    <Route
      path="/change-password"
      element={
        <RequireAuth>
          <ChangePasswordPage />
        </RequireAuth>
      }
    />
    <Route
      element={
        <RequireAuth>
          <DashboardLayout />
        </RequireAuth>
      }
    >
      <Route index element={<DashboardPage />} />
      <Route path="/operations" element={<OperationsPage />} />
      <Route path="/balances" element={<BalancesPage />} />
      <Route path="/bank" element={<BankPage />} />
      <Route path="/history" element={<HistoryPage />} />
      <Route
        path="/admin/users"
        element={
          <RequireAdmin>
            <AdminUsersPage />
          </RequireAdmin>
        }
      />
      <Route
        path="/admin/bank"
        element={
          <RequireAdmin>
            <AdminBankConfigPage />
          </RequireAdmin>
        }
      />
      <Route
        path="/admin/audit"
        element={
          <RequireAdmin>
            <AdminAuditPage />
          </RequireAdmin>
        }
      />
      <Route
        path="/admin/settings"
        element={
          <RequireAdmin>
            <AdminSettingsPage />
          </RequireAdmin>
        }
      />
      <Route path="*" element={<NotFound />} />
    </Route>
  </Routes>
)
