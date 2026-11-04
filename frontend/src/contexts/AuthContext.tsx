import {
  createContext,
  useCallback,
  useContext,
  useEffect,
  useMemo,
  useRef,
  useState,
  type ReactNode,
} from 'react'

import {
  registerRefreshHandler,
  registerUnauthorizedHandler,
  setAccessToken,
} from '../services/api'
import { authService } from '../services/auth'
import type { User } from '../types'

interface AuthContextValue {
  user: User | null
  loading: boolean
  login: (username: string, password: string) => Promise<User>
  logout: () => Promise<void>
  refreshUser: () => Promise<User | null>
  refreshSession: () => Promise<string | null>
  changePassword: (payload: {
    current_password: string
    new_password: string
    confirm_password: string
  }) => Promise<void>
}

const AuthContext = createContext<AuthContextValue | undefined>(undefined)

export function AuthProvider({ children }: { children: ReactNode }) {
  const [user, setUser] = useState<User | null>(null)
  const [loading, setLoading] = useState(true)
  const userRef = useRef<User | null>(null)
  const bootstrapped = useRef(false)

  useEffect(() => {
    userRef.current = user
  }, [user])

  const applySession = useCallback((nextUser: User, access: string) => {
    setAccessToken(access)
    setUser(nextUser)
  }, [])

  const clearSession = useCallback(() => {
    setAccessToken(null)
    setUser(null)
  }, [])

  const refreshSession = useCallback(async (): Promise<string | null> => {
    try {
      const data = await authService.refresh()
      applySession(data.user, data.access)
      return data.access
    } catch {
      clearSession()
      return null
    }
  }, [applySession, clearSession])

  const refreshUser = useCallback(async () => {
    try {
      const fresh = await authService.me()
      if (fresh && fresh.id) setUser(fresh)
      return fresh ?? null
    } catch {
      return null
    }
  }, [])

  const login = useCallback(
    async (username: string, password: string) => {
      const data = await authService.login(username, password)
      applySession(data.user, data.access)
      return data.user
    },
    [applySession],
  )

  const logout = useCallback(async () => {
    try {
      await authService.logout()
    } finally {
      clearSession()
    }
  }, [clearSession])

  const changePassword = useCallback(
    async (payload: {
      current_password: string
      new_password: string
      confirm_password: string
    }) => {
      await authService.changePassword(payload)
      // The backend revokes every token: the user must sign in again.
      clearSession()
    },
    [clearSession],
  )

  // Bootstrap: restore the session from the httpOnly refresh cookie.
  useEffect(() => {
    let cancelled = false
    const bootstrap = async () => {
      try {
        await refreshSession()
      } finally {
        if (!cancelled) setLoading(false)
      }
    }
    if (!bootstrapped.current) {
      bootstrapped.current = true
      void bootstrap()
    }
    return () => {
      cancelled = true
    }
  }, [refreshSession])

  // Wire the axios interceptors to this provider.
  useEffect(() => {
    registerRefreshHandler(refreshSession)
    registerUnauthorizedHandler(() => {
      clearSession()
    })
  }, [refreshSession, clearSession])

  // Silent refresh so an active session never expires mid-action.
  useEffect(() => {
    if (!user) return
    const interval = window.setInterval(() => {
      void refreshSession()
    }, 12 * 60 * 1000)
    const onVisible = () => {
      if (document.visibilityState === 'visible') void refreshSession()
    }
    document.addEventListener('visibilitychange', onVisible)
    return () => {
      window.clearInterval(interval)
      document.removeEventListener('visibilitychange', onVisible)
    }
  }, [user, refreshSession])

  // If a pending password change is detected, refresh the profile.
  useEffect(() => {
    if (user?.must_change_password) {
      void refreshUser()
    }
  }, [user?.must_change_password, refreshUser])

  const value = useMemo<AuthContextValue>(
    () => ({
      user,
      loading,
      login,
      logout,
      refreshUser,
      refreshSession,
      changePassword,
    }),
    [user, loading, login, logout, refreshUser, refreshSession, changePassword],
  )

  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>
}

export const useAuth = (): AuthContextValue => {
  const context = useContext(AuthContext)
  if (!context) throw new Error('useAuth must be used inside <AuthProvider>')
  return context
}
