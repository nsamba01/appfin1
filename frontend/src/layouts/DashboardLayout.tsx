import {
  Activity,
  ArrowLeftRight,
  ChevronDown,
  Landmark,
  LayoutDashboard,
  LogOut,
  Menu,
  ScrollText,
  Settings,
  ShieldCheck,
  Users,
  Wallet,
  X,
} from 'lucide-react'
import { useEffect, useMemo, useRef, useState } from 'react'
import { NavLink, Outlet, useLocation, useNavigate } from 'react-router-dom'

import { useAuth } from '../contexts/AuthContext'
import { useToast } from '../contexts/ToastContext'
import { cn } from '../utils/cn'
import { getInitials } from '../utils/format'
import { Badge } from '../components/ui/Badge'

interface NavItem {
  to: string
  label: string
  icon: typeof LayoutDashboard
  adminOnly?: boolean
  section: 'general' | 'admin'
}

const NAV_ITEMS: NavItem[] = [
  { to: '/', label: 'Tableau de bord', icon: LayoutDashboard, section: 'general' },
  { to: '/operations', label: 'Opérations', icon: ArrowLeftRight, section: 'general' },
  { to: '/balances', label: 'Balances', icon: Wallet, section: 'general' },
  { to: '/bank', label: 'Compte Ecobank', icon: Landmark, section: 'general' },
  { to: '/history', label: 'Historique financier', icon: Activity, section: 'general' },
  { to: '/admin/users', label: 'Utilisateurs', icon: Users, adminOnly: true, section: 'admin' },
  { to: '/admin/bank', label: 'Configuration Ecobank', icon: ShieldCheck, adminOnly: true, section: 'admin' },
  { to: '/admin/audit', label: 'Journaux & audit', icon: ScrollText, adminOnly: true, section: 'admin' },
  { to: '/admin/settings', label: 'Paramètres', icon: Settings, adminOnly: true, section: 'admin' },
]

const PAGE_TITLES: Record<string, string> = {
  '/': 'Tableau de bord',
  '/operations': 'Opérations financières',
  '/balances': 'Balances',
  '/bank': 'Compte bancaire Ecobank',
  '/history': 'Historique financier',
  '/admin/users': 'Gestion des utilisateurs',
  '/admin/bank': 'Configuration Ecobank',
  '/admin/audit': 'Journaux & audit',
  '/admin/settings': 'Paramètres généraux',
}

const SidebarContent = ({ onNavigate }: { onNavigate?: () => void }) => {
  const { user } = useAuth()
  const isAdmin = user?.role === 'ADMIN'
  const general = NAV_ITEMS.filter((item) => item.section === 'general')
  const admin = NAV_ITEMS.filter((item) => item.section === 'admin' && isAdmin)

  const link = (item: NavItem) => {
    const Icon = item.icon
    return (
      <NavLink
        key={item.to}
        to={item.to}
        end={item.to === '/'}
        onClick={onNavigate}
        className={({ isActive }) =>
          cn(
            'group flex items-center gap-3 rounded-xl px-3 py-2.5 text-sm font-medium transition',
            isActive
              ? 'bg-brand-600 text-white shadow-sm'
              : 'text-slate-600 hover:bg-slate-100 hover:text-ink-900',
          )
        }
      >
        {({ isActive }) => (
          <>
            <Icon
              className={cn(
                'h-[18px] w-[18px] transition',
                isActive ? 'text-white' : 'text-slate-400 group-hover:text-brand-600',
              )}
            />
            <span className="truncate">{item.label}</span>
          </>
        )}
      </NavLink>
    )
  }

  return (
    <div className="flex h-full flex-col">
      <div className="flex items-center gap-3 px-5 py-5">
        <div className="flex h-10 w-10 items-center justify-center rounded-xl bg-gradient-to-br from-brand-600 to-brand-800 shadow-sm">
          <Landmark className="h-5 w-5 text-white" />
        </div>
        <div className="min-w-0">
          <p className="truncate font-display text-[15px] font-extrabold leading-tight text-ink-900">
            {user?.application?.company_name ?? 'ICHESS Finance'}
          </p>
          <p className="text-[11px] font-medium uppercase tracking-wide text-slate-400">
            Finance & Banque
          </p>
        </div>
      </div>

      <nav className="flex-1 space-y-6 overflow-y-auto px-3 pb-4">
        <div className="space-y-1">
          <p className="px-3 pb-1 text-[10px] font-bold uppercase tracking-[0.14em] text-slate-400">
            Pilotage
          </p>
          {general.map(link)}
        </div>
        {admin.length > 0 && (
          <div className="space-y-1">
            <p className="px-3 pb-1 text-[10px] font-bold uppercase tracking-[0.14em] text-slate-400">
              Administration
            </p>
            {admin.map(link)}
          </div>
        )}
      </nav>

      <div className="mx-3 mb-4 rounded-xl border border-slate-200 bg-slate-50/80 p-3">
        <div className="flex items-center gap-2 text-xs font-semibold text-slate-600">
          <ShieldCheck className="h-4 w-4 text-emerald-600" />
          Session sécurisée
        </div>
        <p className="mt-1 text-[11px] leading-relaxed text-slate-500">
          Accès contrôlé par rôle. Toutes les actions sensibles sont journalisées.
        </p>
      </div>
    </div>
  )
}

export const DashboardLayout = () => {
  const { user, logout } = useAuth()
  const { error } = useToast()
  const navigate = useNavigate()
  const location = useLocation()
  const [mobileOpen, setMobileOpen] = useState(false)
  const [menuOpen, setMenuOpen] = useState(false)
  const menuRef = useRef<HTMLDivElement>(null)

  useEffect(() => {
    setMobileOpen(false)
  }, [location.pathname])

  useEffect(() => {
    const onClick = (event: MouseEvent) => {
      if (menuRef.current && !menuRef.current.contains(event.target as Node)) {
        setMenuOpen(false)
      }
    }
    document.addEventListener('mousedown', onClick)
    return () => document.removeEventListener('mousedown', onClick)
  }, [])

  const title = useMemo(() => PAGE_TITLES[location.pathname] ?? 'ICHESS Finance', [location.pathname])

  const handleLogout = async () => {
    try {
      await logout()
      navigate('/login', { replace: true })
    } catch {
      error('Déconnexion impossible', 'Veuillez réessayer.')
    }
  }

  return (
    <div className="min-h-screen bg-slate-50">
      {/* Desktop sidebar */}
      <aside className="fixed inset-y-0 left-0 z-30 hidden w-64 border-r border-slate-200 bg-white lg:block">
        <SidebarContent />
      </aside>

      {/* Mobile drawer */}
      {mobileOpen && (
        <div className="fixed inset-0 z-40 lg:hidden">
          <div
            className="absolute inset-0 bg-ink-900/40 backdrop-blur-sm"
            onClick={() => setMobileOpen(false)}
            aria-hidden
          />
          <aside className="relative h-full w-72 max-w-[85vw] animate-slide-in bg-white shadow-lift">
            <button
              type="button"
              onClick={() => setMobileOpen(false)}
              className="absolute right-3 top-4 rounded-lg p-2 text-slate-400 hover:bg-slate-100"
              aria-label="Fermer le menu"
            >
              <X className="h-5 w-5" />
            </button>
            <SidebarContent onNavigate={() => setMobileOpen(false)} />
          </aside>
        </div>
      )}

      <div className="lg:pl-64">
        <header className="sticky top-0 z-20 border-b border-slate-200 bg-white/85 backdrop-blur">
          <div className="flex h-16 items-center justify-between gap-4 px-4 sm:px-6 lg:px-8">
            <div className="flex min-w-0 items-center gap-3">
              <button
                type="button"
                onClick={() => setMobileOpen(true)}
                className="rounded-lg p-2 text-slate-500 hover:bg-slate-100 lg:hidden"
                aria-label="Ouvrir le menu"
              >
                <Menu className="h-5 w-5" />
              </button>
              <div className="min-w-0">
                <h2 className="truncate font-display text-[15px] font-bold text-ink-900">{title}</h2>
                <p className="hidden text-xs text-slate-500 sm:block">
                  {user?.role === 'ADMIN' ? 'Espace administrateur' : 'Espace financier'}
                </p>
              </div>
            </div>

            <div className="flex items-center gap-3">
              <Badge tone={user?.role === 'ADMIN' ? 'brand' : 'info'} className="hidden sm:inline-flex">
                {user?.role_label ?? ''}
              </Badge>

              <div className="relative" ref={menuRef}>
                <button
                  type="button"
                  onClick={() => setMenuOpen((open) => !open)}
                  aria-haspopup="menu"
                  aria-expanded={menuOpen}
                  className="flex items-center gap-2.5 rounded-xl border border-transparent p-1 pl-1 pr-2 transition hover:border-slate-200 hover:bg-slate-50"
                >
                  <span className="flex h-9 w-9 items-center justify-center rounded-lg bg-gradient-to-br from-brand-500 to-brand-700 text-sm font-bold text-white">
                    {getInitials(user?.full_name || user?.username || 'U')}
                  </span>
                  <span className="hidden text-left sm:block">
                    <span className="block text-sm font-semibold leading-tight text-ink-900">
                      {user?.full_name || user?.username}
                    </span>
                    <span className="block text-[11px] text-slate-500">{user?.username}</span>
                  </span>
                  <ChevronDown className="h-4 w-4 text-slate-400" />
                </button>

                {menuOpen && (
                  <div
                    role="menu"
                    className="absolute right-0 top-full z-30 mt-2 w-64 animate-fade-in rounded-xl border border-slate-200 bg-white p-2 shadow-lift"
                  >
                    <div className="px-3 py-2">
                      <p className="text-sm font-semibold text-ink-900">
                        {user?.full_name || user?.username}
                      </p>
                      <p className="truncate text-xs text-slate-500">{user?.email || '—'}</p>
                      <p className="mt-1 text-[11px] text-slate-400">
                        Dernière connexion : {user?.last_login_ip ?? '—'}
                      </p>
                    </div>
                    <div className="my-1 h-px bg-slate-100" />
                    <button
                      type="button"
                      role="menuitem"
                      onClick={() => {
                        setMenuOpen(false)
                        navigate('/change-password')
                      }}
                      className="flex w-full items-center gap-2 rounded-lg px-3 py-2 text-sm text-ink-700 hover:bg-slate-50"
                    >
                      <ShieldCheck className="h-4 w-4 text-slate-400" />
                      Changer le mot de passe
                    </button>
                    <button
                      type="button"
                      role="menuitem"
                      onClick={handleLogout}
                      className="flex w-full items-center gap-2 rounded-lg px-3 py-2 text-sm text-red-600 hover:bg-red-50"
                    >
                      <LogOut className="h-4 w-4" />
                      Se déconnecter
                    </button>
                  </div>
                )}
              </div>
            </div>
          </div>
        </header>

        <main className="mx-auto w-full max-w-[1400px] px-4 py-6 sm:px-6 lg:px-8 lg:py-8">
          <Outlet />
        </main>
      </div>
    </div>
  )
}
