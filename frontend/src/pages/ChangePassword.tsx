import { Check, KeyRound, Lock, ShieldAlert } from 'lucide-react'
import { useState, type FormEvent } from 'react'
import { useNavigate } from 'react-router-dom'

import { Button } from '../components/ui/Button'
import { Card, CardBody, CardHeader } from '../components/ui/Card'
import { Input } from '../components/ui/Field'
import { useAuth } from '../contexts/AuthContext'
import { useToast } from '../contexts/ToastContext'
import { extractErrorMessage, extractFieldErrors } from '../services/api'

const rules = [
  { id: 'length', label: 'Au moins 10 caractères', test: (value: string) => value.length >= 10 },
  { id: 'upper', label: 'Une lettre majuscule', test: (value: string) => /[A-Z]/.test(value) },
  { id: 'lower', label: 'Une lettre minuscule', test: (value: string) => /[a-z]/.test(value) },
  { id: 'digit', label: 'Un chiffre', test: (value: string) => /[0-9]/.test(value) },
  { id: 'special', label: 'Un caractère spécial', test: (value: string) => /[^A-Za-z0-9]/.test(value) },
]

export const ChangePasswordPage = () => {
  const { user, changePassword } = useAuth()
  const { success, error } = useToast()
  const navigate = useNavigate()

  const [currentPassword, setCurrentPassword] = useState('')
  const [newPassword, setNewPassword] = useState('')
  const [confirmPassword, setConfirmPassword] = useState('')
  const [submitting, setSubmitting] = useState(false)
  const [formError, setFormError] = useState('')
  const [fieldErrors, setFieldErrors] = useState<Record<string, string>>({})

  const handled = (event: FormEvent) => {
    event.preventDefault()
    setFormError('')
    setFieldErrors({})
    void submit()
  }

  const submit = async () => {
    if (newPassword !== confirmPassword) {
      setFieldErrors({ confirm_password: 'Les deux mots de passe ne correspondent pas.' })
      return
    }
    if (!rules.every((rule) => rule.test(newPassword))) {
      setFormError('Le nouveau mot de passe ne respecte pas toutes les règles de sécurité.')
      return
    }
    setSubmitting(true)
    try {
      await changePassword({
        current_password: currentPassword,
        new_password: newPassword,
        confirm_password: confirmPassword,
      })
      success('Mot de passe modifié', 'Reconnectez-vous avec votre nouveau mot de passe.')
      navigate('/login', { replace: true })
    } catch (err) {
      setFieldErrors(extractFieldErrors(err))
      const message = extractErrorMessage(err, 'Impossible de modifier le mot de passe.')
      setFormError(message)
      error('Modification impossible', message)
    } finally {
      setSubmitting(false)
    }
  }

  return (
    <div className="mx-auto flex min-h-screen max-w-2xl flex-col justify-center px-4 py-10 sm:px-6">
      <div className="mb-6 flex items-center gap-3">
        <div className="flex h-11 w-11 items-center justify-center rounded-xl bg-brand-600">
          <KeyRound className="h-5 w-5 text-white" />
        </div>
        <div>
          <h1 className="font-display text-xl font-extrabold text-ink-900">
            Changement de mot de passe
          </h1>
          <p className="text-sm text-slate-500">
            {user?.must_change_password
              ? 'Votre mot de passe initial doit être remplacé avant de continuer.'
              : 'Mettez à jour votre mot de passe.'}
          </p>
        </div>
      </div>

      {user?.must_change_password && (
        <div className="mb-5 flex items-start gap-3 rounded-xl border border-amber-200 bg-amber-50 px-4 py-3">
          <ShieldAlert className="mt-0.5 h-5 w-5 shrink-0 text-amber-600" />
          <p className="text-sm text-amber-800">
            Pour des raisons de sécurité, l'accès aux modules financiers reste bloqué jusqu'au
            changement de votre mot de passe.
          </p>
        </div>
      )}

      <Card>
        <CardHeader
          title="Nouveau mot de passe"
          subtitle="Choisissez un mot de passe robuste et unique."
          icon={<Lock className="h-5 w-5" />}
        />
        <CardBody>
          <form onSubmit={handled} className="space-y-5" noValidate>
            {formError && (
              <div role="alert" className="rounded-xl border border-red-200 bg-red-50 px-4 py-3 text-sm text-red-700">
                {formError}
              </div>
            )}
            <Input
              label="Mot de passe actuel"
              name="current_password"
              type="password"
              autoComplete="current-password"
              value={currentPassword}
              onChange={(event) => setCurrentPassword(event.target.value)}
              error={fieldErrors.current_password}
              required
            />
            <Input
              label="Nouveau mot de passe"
              name="new_password"
              type="password"
              autoComplete="new-password"
              value={newPassword}
              onChange={(event) => setNewPassword(event.target.value)}
              error={fieldErrors.new_password}
              required
            />
            <Input
              label="Confirmer le nouveau mot de passe"
              name="confirm_password"
              type="password"
              autoComplete="new-password"
              value={confirmPassword}
              onChange={(event) => setConfirmPassword(event.target.value)}
              error={fieldErrors.confirm_password}
              required
            />

            <div className="rounded-xl border border-slate-200 bg-slate-50 p-4">
              <p className="mb-2 text-xs font-semibold uppercase tracking-wide text-slate-500">
                Règles de sécurité
              </p>
              <ul className="grid gap-1.5 sm:grid-cols-2">
                {rules.map((rule) => {
                  const ok = rule.test(newPassword)
                  return (
                    <li
                      key={rule.id}
                      className={`flex items-center gap-2 text-xs ${ok ? 'text-emerald-700' : 'text-slate-500'}`}
                    >
                      <span
                        className={`flex h-4 w-4 items-center justify-center rounded-full ${ok ? 'bg-emerald-100' : 'bg-slate-200'}`}
                      >
                        <Check className="h-3 w-3" />
                      </span>
                      {rule.label}
                    </li>
                  )
                })}
              </ul>
            </div>

            <Button type="submit" loading={submitting} fullWidth size="lg">
              Enregistrer le nouveau mot de passe
            </Button>
          </form>
        </CardBody>
      </Card>
    </div>
  )
}
