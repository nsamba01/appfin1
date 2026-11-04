import {
  ArrowRight,
  Eye,
  EyeOff,
  Landmark,
  Lock,
  ShieldCheck,
  TrendingUp,
  User as UserIcon,
} from 'lucide-react'
import { useEffect, useState, type FormEvent } from 'react'
import { useLocation, useNavigate } from 'react-router-dom'

import { Button } from '../components/ui/Button'
import { Input } from '../components/ui/Field'
import { useAuth } from '../contexts/AuthContext'
import { useToast } from '../contexts/ToastContext'
import { extractErrorMessage } from '../services/api'

export const LoginPage = () => {
  const { login, user, loading } = useAuth()
  const navigate = useNavigate()
  const location = useLocation()
  const { error: notifyError, success } = useToast()

  const [username, setUsername] = useState('')
  const [password, setPassword] = useState('')
  const [showPassword, setShowPassword] = useState(false)
  const [submitting, setSubmitting] = useState(false)
  const [formError, setFormError] = useState('')
  const [fieldErrors, setFieldErrors] = useState<Record<string, string>>({})

  const from = (location.state as { from?: string } | null)?.from ?? '/'

  useEffect(() => {
    if (!loading && user) {
      navigate(user.must_change_password ? '/change-password' : from, { replace: true })
    }
  }, [loading, user, navigate, from])

  const handleSubmit = async (event: FormEvent) => {
    event.preventDefault()
    setFormError('')
    setFieldErrors({})

    if (!username.trim() || !password) {
      setFormError('Veuillez renseigner votre identifiant et votre mot de passe.')
      return
    }

    setSubmitting(true)
    try {
      const authenticated = await login(username.trim(), password)
      success('Connexion réussie', `Bienvenue, ${authenticated.full_name || authenticated.username}.`)
      navigate(authenticated.must_change_password ? '/change-password' : from, { replace: true })
    } catch (error) {
      const message = extractErrorMessage(error, 'Connexion impossible. Vérifiez vos identifiants.')
      setFormError(message)
      notifyError('Échec de la connexion', message)
      setPassword('')
    } finally {
      setSubmitting(false)
    }
  }

  return (
    <div className="flex min-h-screen flex-col lg:flex-row">
      {/* Brand panel */}
      <div className="relative hidden overflow-hidden bg-gradient-to-br from-brand-800 via-brand-700 to-brand-900 lg:flex lg:w-[52%] lg:flex-col lg:justify-between lg:p-12">
        <div
          className="absolute inset-0 opacity-30"
          style={{
            backgroundImage:
              'radial-gradient(circle at 20% 20%, rgba(147,197,253,0.45) 0, transparent 45%), radial-gradient(circle at 80% 70%, rgba(37,99,235,0.5) 0, transparent 50%)',
          }}
          aria-hidden
        />
        <div
          className="absolute inset-0 opacity-[0.07]"
          style={{
            backgroundImage:
              'linear-gradient(rgba(255,255,255,0.8) 1px, transparent 1px), linear-gradient(90deg, rgba(255,255,255,0.8) 1px, transparent 1px)',
            backgroundSize: '48px 48px',
          }}
          aria-hidden
        />

        <div className="relative flex items-center gap-3">
          <div className="flex h-11 w-11 items-center justify-center rounded-xl bg-white/15 backdrop-blur">
            <Landmark className="h-6 w-6 text-white" />
          </div>
          <div>
            <p className="font-display text-lg font-extrabold text-white">ICHESS Finance</p>
            <p className="text-xs font-medium uppercase tracking-[0.18em] text-brand-200">
              Gestion financière & bancaire
            </p>
          </div>
        </div>

        <div className="relative max-w-lg">
          <h1 className="font-display text-4xl font-extrabold leading-tight text-white">
            La maîtrise complète de votre trésorerie, en un seul écran.
          </h1>
          <p className="mt-4 text-base leading-relaxed text-brand-100/90">
            Enregistrez vos opérations internes, consultez le solde réel Ecobank et
            identifiez immédiatement tout écart — avec une traçabilité intégrale.
          </p>

          <div className="mt-9 grid gap-4 sm:grid-cols-2">
            {[
              { icon: TrendingUp, title: 'Soldes consolidés', text: 'Entrées, sorties et balance calculées côté serveur.' },
              { icon: ShieldCheck, title: 'Sécurité renforcée', text: 'Argon2id, RBAC, journal d’audit complet.' },
            ].map((feature) => (
              <div
                key={feature.title}
                className="rounded-xl border border-white/15 bg-white/10 p-4 backdrop-blur-sm"
              >
                <feature.icon className="h-5 w-5 text-brand-200" />
                <p className="mt-2.5 text-sm font-semibold text-white">{feature.title}</p>
                <p className="mt-1 text-xs leading-relaxed text-brand-100/80">{feature.text}</p>
              </div>
            ))}
          </div>
        </div>

        <p className="relative text-xs text-brand-200/70">
          © {new Date().getFullYear()} ICHESS Finance — Accès strictement réservé aux utilisateurs autorisés.
        </p>
      </div>

      {/* Form panel */}
      <div className="flex flex-1 flex-col justify-center bg-white px-5 py-10 sm:px-10 lg:px-16">
        <div className="mx-auto w-full max-w-md">
          <div className="mb-8 flex items-center gap-3 lg:hidden">
            <div className="flex h-10 w-10 items-center justify-center rounded-xl bg-brand-600">
              <Landmark className="h-5 w-5 text-white" />
            </div>
            <div>
              <p className="font-display text-base font-extrabold text-ink-900">ICHESS Finance</p>
              <p className="text-[11px] uppercase tracking-wider text-slate-500">
                Gestion financière & bancaire
              </p>
            </div>
          </div>

          <div className="mb-8">
            <h2 className="font-display text-2xl font-extrabold tracking-tight text-ink-900">
              Connexion
            </h2>
            <p className="mt-1.5 text-sm text-slate-500">
              Accédez à votre espace sécurisé.
            </p>
          </div>

          <form onSubmit={handleSubmit} noValidate className="space-y-5">
            {formError && (
              <div
                role="alert"
                className="rounded-xl border border-red-200 bg-red-50 px-4 py-3 text-sm text-red-700"
                data-testid="login-error"
              >
                {formError}
              </div>
            )}

            <Input
              label="Identifiant"
              name="username"
              autoComplete="username"
              autoFocus
              value={username}
              onChange={(event) => setUsername(event.target.value)}
              placeholder="Votre nom d'utilisateur"
              icon={<UserIcon className="h-4 w-4" />}
              error={fieldErrors.username}
              required
            />

            <div className="relative">
              <Input
                label="Mot de passe"
                name="password"
                type={showPassword ? 'text' : 'password'}
                autoComplete="current-password"
                value={password}
                onChange={(event) => setPassword(event.target.value)}
                placeholder="Votre mot de passe"
                icon={<Lock className="h-4 w-4" />}
                error={fieldErrors.password}
                required
              />
              <button
                type="button"
                onClick={() => setShowPassword((visible) => !visible)}
                className="absolute right-2 top-[34px] rounded-lg p-2 text-slate-400 transition hover:bg-slate-100 hover:text-ink-700"
                aria-label={showPassword ? 'Masquer le mot de passe' : 'Afficher le mot de passe'}
              >
                {showPassword ? <EyeOff className="h-4 w-4" /> : <Eye className="h-4 w-4" />}
              </button>
            </div>

            <Button
              type="submit"
              size="lg"
              fullWidth
              loading={submitting}
              icon={!submitting ? <ArrowRight className="h-4 w-4" /> : undefined}
              data-testid="login-submit"
            >
              {submitting ? 'Connexion…' : 'Se connecter'}
            </Button>
          </form>

          <div className="mt-8 rounded-xl border border-slate-200 bg-slate-50/70 p-4">
            <div className="flex items-start gap-2.5">
              <ShieldCheck className="mt-0.5 h-4 w-4 shrink-0 text-emerald-600" />
              <p className="text-xs leading-relaxed text-slate-500">
                Après plusieurs tentatives échouées, le compte est temporairement verrouillé.
                Lors de la première connexion, un changement de mot de passe est exigé.
              </p>
            </div>
          </div>

          <p className="mt-8 text-center text-xs text-slate-400">
            Accès réservé au personnel autorisé. Toute connexion est enregistrée.
          </p>
        </div>
      </div>
    </div>
  )
}
