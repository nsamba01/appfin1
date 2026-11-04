import { Building2, Clock, Lock, Save, Settings as SettingsIcon, ShieldCheck } from 'lucide-react'
import { useCallback, useEffect, useState } from 'react'

import { Button } from '../../components/ui/Button'
import { Card, CardBody, CardHeader } from '../../components/ui/Card'
import { Spinner } from '../../components/ui/Feedback'
import { Input } from '../../components/ui/Field'
import { PageHeader } from '../../components/ui/PageHeader'
import { useAuth } from '../../contexts/AuthContext'
import { useToast } from '../../contexts/ToastContext'
import { extractErrorMessage, extractFieldErrors } from '../../services/api'
import { adminService } from '../../services/admin'
import type { ApplicationSettings } from '../../types'
import { formatDateTime } from '../../utils/format'

export const AdminSettingsPage = () => {
  const { refreshUser } = useAuth()
  const { success, error: notifyError } = useToast()
  const [settings, setSettings] = useState<ApplicationSettings | null>(null)
  const [loading, setLoading] = useState(true)
  const [saving, setSaving] = useState(false)
  const [fieldErrors, setFieldErrors] = useState<Record<string, string>>({})

  const load = useCallback(async () => {
    setLoading(true)
    try {
      const data = await adminService.settings()
      setSettings(data)
    } catch (err) {
      notifyError('Chargement impossible', extractErrorMessage(err))
    } finally {
      setLoading(false)
    }
  }, [notifyError])

  useEffect(() => {
    void load()
  }, [load])

  const update = <K extends keyof ApplicationSettings>(key: K, value: ApplicationSettings[K]) => {
    if (!settings) return
    setSettings({ ...settings, [key]: value })
  }

  const save = async () => {
    if (!settings) return
    setSaving(true)
    setFieldErrors({})
    try {
      const updated = await adminService.updateSettings({
        company_name: settings.company_name,
        currency: settings.currency,
        timezone_label: settings.timezone_label,
        allow_finance_edit_operations: settings.allow_finance_edit_operations,
        allow_finance_delete_operations: settings.allow_finance_delete_operations,
        operation_edit_window_days: settings.operation_edit_window_days,
        bank_sync_interval_minutes: settings.bank_sync_interval_minutes,
      })
      setSettings(updated)
      success('Paramètres enregistrés', 'Les règles s’appliquent immédiatement.')
      await refreshUser()
    } catch (err) {
      setFieldErrors(extractFieldErrors(err))
      notifyError('Enregistrement impossible', extractErrorMessage(err))
    } finally {
      setSaving(false)
    }
  }

  if (loading && !settings) return <Spinner label="Chargement des paramètres…" />
  if (!settings) return null

  return (
    <div className="animate-fade-in">
      <PageHeader
        eyebrow="Espace administrateur"
        title="Paramètres généraux"
        description="Identité de l'application et règles métier appliquées aux utilisateurs financiers."
        actions={
          <Button onClick={() => void save()} loading={saving} icon={<Save className="h-4 w-4" />}>
            Enregistrer
          </Button>
        }
      />

      <div className="grid gap-6 lg:grid-cols-2">
        <Card>
          <CardHeader
            title="Identité de l'application"
            subtitle="Affichée dans l'interface et les exports"
            icon={<Building2 className="h-5 w-5" />}
          />
          <CardBody className="space-y-4">
            <Input
              label="Nom de l'organisation"
              value={settings.company_name}
              onChange={(event) => update('company_name', event.target.value)}
              error={fieldErrors.company_name}
              required
            />
            <Input
              label="Devise"
              value={settings.currency}
              onChange={(event) => update('currency', event.target.value.toUpperCase())}
              hint="Code ISO 4217, ex. USD, CDF, EUR"
              error={fieldErrors.currency}
              maxLength={5}
              required
            />
            <Input
              label="Fuseau horaire"
              value={settings.timezone_label}
              onChange={(event) => update('timezone_label', event.target.value)}
              hint="Ex. Africa/Kinshasa"
              error={fieldErrors.timezone_label}
            />
            <p className="text-xs text-slate-400">
              Dernière mise à jour : {formatDateTime(settings.updated_at)}
            </p>
          </CardBody>
        </Card>

        <Card>
          <CardHeader
            title="Règles métier — financiers"
            subtitle="Contrôlez ce qu'un financier peut modifier"
            icon={<Lock className="h-5 w-5" />}
          />
          <CardBody className="space-y-4">
            <label className="flex items-start justify-between gap-4 rounded-xl border border-slate-200 p-4">
              <span>
                <span className="block text-sm font-semibold text-ink-900">
                  Modifier les opérations
                </span>
                <span className="mt-0.5 block text-xs text-slate-500">
                  Autoriser les financiers à modifier une opération existante.
                </span>
              </span>
              <input
                type="checkbox"
                checked={settings.allow_finance_edit_operations}
                onChange={(event) => update('allow_finance_edit_operations', event.target.checked)}
                className="mt-0.5 h-5 w-5 rounded border-slate-300 text-brand-600 focus:ring-brand-500"
              />
            </label>

            <label className="flex items-start justify-between gap-4 rounded-xl border border-slate-200 p-4">
              <span>
                <span className="block text-sm font-semibold text-ink-900">
                  Archiver les opérations
                </span>
                <span className="mt-0.5 block text-xs text-slate-500">
                  L'archivage conserve toujours la trace d'audit.
                </span>
              </span>
              <input
                type="checkbox"
                checked={settings.allow_finance_delete_operations}
                onChange={(event) => update('allow_finance_delete_operations', event.target.checked)}
                className="mt-0.5 h-5 w-5 rounded border-slate-300 text-brand-600 focus:ring-brand-500"
              />
            </label>

            <Input
              label="Fenêtre de modification (jours)"
              type="number"
              min={0}
              max={3650}
              value={settings.operation_edit_window_days}
              onChange={(event) => update('operation_edit_window_days', Number(event.target.value))}
              hint="0 = pas de limite."
              error={fieldErrors.operation_edit_window_days}
            />
            <Input
              label="Fréquence de synchronisation bancaire (minutes)"
              type="number"
              min={1}
              max={1440}
              value={settings.bank_sync_interval_minutes}
              onChange={(event) => update('bank_sync_interval_minutes', Number(event.target.value))}
              error={fieldErrors.bank_sync_interval_minutes}
            />
          </CardBody>
        </Card>
      </div>

      <div className="mt-6 grid gap-6 lg:grid-cols-2">
        <Card>
          <CardHeader title="Sécurité active" icon={<ShieldCheck className="h-5 w-5" />} />
          <CardBody className="grid gap-3 text-sm text-slate-600 sm:grid-cols-2">
            {[
              'Hachage Argon2id',
              'JWT + cookie httpOnly',
              'Verrouillage anti-force brute',
              'Contrôle d’accès par rôle',
              'Journal d’audit complet',
              'Secrets bancaires chiffrés',
              'Validation stricte des entrées',
              'En-têtes de sécurité HTTP',
            ].map((item) => (
              <p key={item} className="flex items-center gap-2">
                <span className="h-1.5 w-1.5 rounded-full bg-emerald-500" />
                {item}
              </p>
            ))}
          </CardBody>
        </Card>

        <Card>
          <CardHeader title="Information" icon={<SettingsIcon className="h-5 w-5" />} />
          <CardBody className="space-y-3 text-sm leading-relaxed text-slate-600">
            <p>
              Les paramètres bancaires (identifiants API, numéro de compte, fréquence de
              synchronisation) se configurent exclusivement dans la page
              <span className="font-semibold text-ink-900"> Configuration Ecobank</span>.
            </p>
            <p className="flex items-start gap-2 rounded-xl bg-slate-50 p-3 text-xs">
              <Clock className="mt-0.5 h-4 w-4 shrink-0 text-slate-400" />
              Les modifications sont enregistrées dans le journal d'audit avec l'auteur et
              l'horodatage.
            </p>
          </CardBody>
        </Card>
      </div>
    </div>
  )
}
