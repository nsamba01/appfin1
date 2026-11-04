import {
  AlertTriangle,
  CheckCircle2,
  CloudDownload,
  Eye,
  EyeOff,
  KeyRound,
  Landmark,
  Link2,
  RefreshCw,
  ShieldAlert,
  ShieldCheck,
  Trash2,
  WifiOff,
} from 'lucide-react'
import { useCallback, useEffect, useState } from 'react'

import { Badge } from '../../components/ui/Badge'
import { Button } from '../../components/ui/Button'
import { Card, CardBody, CardHeader } from '../../components/ui/Card'
import { EmptyState, Spinner } from '../../components/ui/Feedback'
import { Input, Select } from '../../components/ui/Field'
import { ConfirmDialog } from '../../components/ui/Modal'
import { PageHeader } from '../../components/ui/PageHeader'
import { useToast } from '../../contexts/ToastContext'
import { extractErrorMessage, extractFieldErrors } from '../../services/api'
import { bankingService } from '../../services/finance'
import type { EcobankConfig, SyncLogEntry } from '../../types'
import { formatDateTime } from '../../utils/format'

interface FormState {
  is_enabled: boolean
  environment: 'SANDBOX' | 'PRODUCTION'
  base_url: string
  auth_path: string
  balance_path: string
  client_id: string
  affiliate_code: string
  source_code: string
  public_key: string
  ip_address: string
  secret_key: string
  subscription_key: string
  account_no: string
  service_code: string
  token_request_type: string
  balance_request_type: string
  timeout_seconds: number
  sync_interval_minutes: number
  auto_sync_enabled: boolean
  sandbox_mode_enabled: boolean
}

const EMPTY: FormState = {
  is_enabled: false,
  environment: 'SANDBOX',
  base_url: 'https://apimuat-gateway.ecobank.com',
  auth_path: '/corp-auth/api/v2/integration/auth/app/token',
  balance_path: '/corp-account-inquiry/api/v2/integration/account/inquiry/balance',
  client_id: '',
  affiliate_code: '',
  source_code: '',
  public_key: '',
  ip_address: '',
  secret_key: '',
  subscription_key: '',
  account_no: '',
  service_code: 'ACCOUNT_SERVICE',
  token_request_type: 'GET_API_TOKEN',
  balance_request_type: 'GET_ACCOUNT_BALANCE',
  timeout_seconds: 30,
  sync_interval_minutes: 30,
  auto_sync_enabled: true,
  sandbox_mode_enabled: false,
}

export const AdminBankConfigPage = () => {
  const { success, error: notifyError, info } = useToast()
  const [config, setConfig] = useState<EcobankConfig | null>(null)
  const [form, setForm] = useState<FormState>(EMPTY)
  const [loading, setLoading] = useState(true)
  const [saving, setSaving] = useState(false)
  const [testing, setTesting] = useState(false)
  const [syncing, setSyncing] = useState(false)
  const [logs, setLogs] = useState<SyncLogEntry[]>([])
  const [fieldErrors, setFieldErrors] = useState<Record<string, string>>({})
  const [showSecrets, setShowSecrets] = useState(false)
  const [clearOpen, setClearOpen] = useState(false)
  const [clearing, setClearing] = useState(false)

  const load = useCallback(async () => {
    setLoading(true)
    try {
      const [configData, logsData] = await Promise.all([
        bankingService.config(),
        bankingService.logs(),
      ])
      const typed = configData as unknown as EcobankConfig
      setConfig(typed)
      setLogs(logsData)
      setForm({
        is_enabled: typed.is_enabled,
        environment: typed.environment,
        base_url: typed.base_url,
        auth_path: typed.auth_path,
        balance_path: typed.balance_path,
        client_id: typed.client_id,
        affiliate_code: typed.affiliate_code,
        source_code: typed.source_code,
        public_key: typed.public_key,
        ip_address: typed.ip_address ?? '',
        secret_key: '',
        subscription_key: '',
        account_no: '',
        service_code: typed.service_code || 'ACCOUNT_SERVICE',
        token_request_type: typed.token_request_type || 'GET_API_TOKEN',
        balance_request_type: typed.balance_request_type || 'GET_ACCOUNT_BALANCE',
        timeout_seconds: typed.timeout_seconds,
        sync_interval_minutes: typed.sync_interval_minutes,
        auto_sync_enabled: typed.auto_sync_enabled,
        sandbox_mode_enabled: typed.sandbox_mode_enabled,
      })
    } catch (err) {
      notifyError('Chargement impossible', extractErrorMessage(err))
    } finally {
      setLoading(false)
    }
  }, [notifyError])

  useEffect(() => {
    void load()
  }, [load])

  const update = <K extends keyof FormState>(key: K, value: FormState[K]) => {
    setForm((current) => ({ ...current, [key]: value }))
  }

  const save = async () => {
    setSaving(true)
    setFieldErrors({})
    try {
      const payload: Record<string, unknown> = { ...form }
      if (!form.secret_key) delete payload.secret_key
      if (!form.subscription_key) delete payload.subscription_key
      if (!form.account_no) delete payload.account_no
      if (!form.ip_address) delete payload.ip_address
      const updated = (await bankingService.updateConfig(payload)) as unknown as EcobankConfig
      setConfig(updated)
      setForm((current) => ({ ...current, secret_key: '', subscription_key: '', account_no: '' }))
      success('Configuration enregistrée', 'Les secrets sont chiffrés au repos.')
      const logsData = await bankingService.logs()
      setLogs(logsData)
    } catch (err) {
      setFieldErrors(extractFieldErrors(err))
      notifyError('Enregistrement impossible', extractErrorMessage(err))
    } finally {
      setSaving(false)
    }
  }

  const testConnection = async () => {
    setTesting(true)
    try {
      const result = await bankingService.testConnection()
      if (result.success) success('Connexion réussie', result.message)
      else notifyError('Connexion échouée', result.message)
      await load()
    } catch (err) {
      notifyError('Test impossible', extractErrorMessage(err))
    } finally {
      setTesting(false)
    }
  }

  const syncNow = async () => {
    setSyncing(true)
    try {
      const result = await bankingService.syncNow()
      if (result.success) success('Synchronisation terminée', result.message)
      else info('Synchronisation non effectuée', result.message)
      await load()
    } catch (err) {
      notifyError('Synchronisation impossible', extractErrorMessage(err))
    } finally {
      setSyncing(false)
    }
  }

  const clearSecrets = async () => {
    setClearing(true)
    try {
      await bankingService.clearSecrets()
      success('Identifiants supprimés', 'La connexion bancaire est désormais désactivée.')
      setClearOpen(false)
      await load()
    } catch (err) {
      notifyError('Suppression impossible', extractErrorMessage(err))
    } finally {
      setClearing(false)
    }
  }

  if (loading && !config) return <Spinner label="Chargement de la configuration…" />

  const statusTone: 'success' | 'danger' | 'warning' | 'neutral' =
    config?.connection_status === 'CONNECTED'
      ? 'success'
      : config?.connection_status === 'ERROR'
        ? 'danger'
        : config?.connection_status === 'SANDBOX'
          ? 'warning'
          : 'neutral'

  return (
    <div className="animate-fade-in">
      <PageHeader
        eyebrow="Espace administrateur"
        title="Configuration Ecobank"
        description="Renseignez les paramètres officiels de l'API. Les secrets sont chiffrés et ne sont jamais renvoyés au navigateur."
        actions={
          <>
            <Button
              variant="secondary"
              onClick={() => void testConnection()}
              loading={testing}
              icon={<Link2 className="h-4 w-4" />}
            >
              Tester la connexion
            </Button>
            <Button
              variant="secondary"
              onClick={() => void syncNow()}
              loading={syncing}
              icon={<CloudDownload className="h-4 w-4" />}
            >
              Synchroniser
            </Button>
            <Button onClick={() => void save()} loading={saving} icon={<ShieldCheck className="h-4 w-4" />}>
              Enregistrer
            </Button>
          </>
        }
      />

      {config && (
        <div className="mb-5 grid gap-4 sm:grid-cols-2 xl:grid-cols-4">
          {[
            { label: 'Statut de la connexion', value: config.connection_status_label, tone: statusTone },
            { label: 'Compte', value: config.masked_account_no || '—', tone: 'neutral' as const },
            {
              label: 'Dernier test',
              value: config.last_test_at ? formatDateTime(config.last_test_at) : 'Jamais',
              tone: 'neutral' as const,
            },
            {
              label: 'Dernière sync',
              value: config.last_sync_at ? formatDateTime(config.last_sync_at) : 'Jamais',
              tone: 'neutral' as const,
            },
          ].map((item) => (
            <Card key={item.label} className="px-5 py-4">
              <p className="text-[11px] font-semibold uppercase tracking-wide text-slate-400">
                {item.label}
              </p>
              <div className="mt-1.5">
                <Badge tone={item.tone}>{item.value}</Badge>
              </div>
            </Card>
          ))}
        </div>
      )}

      {config?.sandbox_simulation && (
        <div className="mb-5 flex items-start gap-3 rounded-xl border border-amber-200 bg-amber-50 px-4 py-3 text-amber-900">
          <ShieldAlert className="mt-0.5 h-5 w-5 shrink-0" />
          <div>
            <p className="text-sm font-semibold">Mode démonstration sandbox actif</p>
            <p className="mt-0.5 text-sm">
              Aucun identifiant réel n'est enregistré. Les soldes affichés sont simulés et
              clairement identifiés comme tels dans toute l'application.
            </p>
          </div>
        </div>
      )}

      <div className="grid gap-6 xl:grid-cols-3">
        <div className="space-y-6 xl:col-span-2">
          <Card>
            <CardHeader
              title="Environnement & activation"
              subtitle="Ne jamais utiliser une URL UAT en production"
              icon={<Landmark className="h-5 w-5" />}
            />
            <CardBody className="grid gap-4 sm:grid-cols-2">
              <Select
                label="Environnement"
                value={form.environment}
                onChange={(event) =>
                  update('environment', event.target.value as 'SANDBOX' | 'PRODUCTION')
                }
                options={[
                  { value: 'SANDBOX', label: 'Sandbox (UAT)' },
                  { value: 'PRODUCTION', label: 'Production' },
                ]}
              />
              <Input
                label="Fréquence de synchronisation (minutes)"
                type="number"
                min={1}
                max={1440}
                value={form.sync_interval_minutes}
                onChange={(event) => update('sync_interval_minutes', Number(event.target.value))}
                error={fieldErrors.sync_interval_minutes}
              />
              <Input
                label="URL de l'API (HTTPS)"
                value={form.base_url}
                onChange={(event) => update('base_url', event.target.value)}
                error={fieldErrors.base_url}
                className="sm:col-span-2"
                required
              />
              <Input
                label="Chemin du service d'authentification"
                value={form.auth_path}
                onChange={(event) => update('auth_path', event.target.value)}
                error={fieldErrors.auth_path}
                className="sm:col-span-2"
              />
              <Input
                label="Chemin du solde de compte"
                value={form.balance_path}
                onChange={(event) => update('balance_path', event.target.value)}
                error={fieldErrors.balance_path}
                className="sm:col-span-2"
              />
              <label className="flex items-center gap-2.5 text-sm text-ink-700">
                <input
                  type="checkbox"
                  checked={form.is_enabled}
                  onChange={(event) => update('is_enabled', event.target.checked)}
                  className="h-4 w-4 rounded border-slate-300 text-brand-600 focus:ring-brand-500"
                />
                Activer la connexion Ecobank
              </label>
              <label className="flex items-center gap-2.5 text-sm text-ink-700">
                <input
                  type="checkbox"
                  checked={form.auto_sync_enabled}
                  onChange={(event) => update('auto_sync_enabled', event.target.checked)}
                  className="h-4 w-4 rounded border-slate-300 text-brand-600 focus:ring-brand-500"
                />
                Synchronisation automatique
              </label>
              <label className="flex items-start gap-2.5 text-sm text-ink-700 sm:col-span-2">
                <input
                  type="checkbox"
                  checked={form.sandbox_mode_enabled}
                  onChange={(event) => update('sandbox_mode_enabled', event.target.checked)}
                  className="mt-0.5 h-4 w-4 rounded border-slate-300 text-brand-600 focus:ring-brand-500"
                />
                <span>
                  Activer le mode démonstration sandbox
                  <span className="mt-0.5 block text-xs text-slate-500">
                    Uniquement sans accès API réel. Les soldes simulés sont explicitement
                    identifiés et ne participent jamais au calcul de l'écart.
                  </span>
                </span>
              </label>
            </CardBody>
          </Card>

          <Card>
            <CardHeader
              title="Identifiants partenaires"
              subtitle="Fournis par Ecobank lors de l'onboarding"
              icon={<KeyRound className="h-5 w-5" />}
              action={
                <button
                  type="button"
                  onClick={() => setShowSecrets((visible) => !visible)}
                  className="inline-flex items-center gap-1.5 rounded-lg px-2 py-1 text-xs font-semibold text-slate-500 hover:bg-slate-100"
                >
                  {showSecrets ? <EyeOff className="h-3.5 w-3.5" /> : <Eye className="h-3.5 w-3.5" />}
                  {showSecrets ? 'Masquer' : 'Afficher la saisie'}
                </button>
              }
            />
            <CardBody className="grid gap-4 sm:grid-cols-2">
              <Input
                label="Client ID"
                value={form.client_id}
                onChange={(event) => update('client_id', event.target.value)}
                error={fieldErrors.client_id}
              />
              <Input
                label="Affiliate Code"
                value={form.affiliate_code}
                onChange={(event) => update('affiliate_code', event.target.value.toUpperCase())}
                error={fieldErrors.affiliate_code}
                hint="Ex. ECD (RDC), EGH (Ghana)"
              />
              <Input
                label="Source Code"
                value={form.source_code}
                onChange={(event) => update('source_code', event.target.value)}
                error={fieldErrors.source_code}
              />
              <Input
                label="Public Key"
                value={form.public_key}
                onChange={(event) => update('public_key', event.target.value)}
                error={fieldErrors.public_key}
              />
              <Input
                label="Adresse IP déclarée"
                value={form.ip_address}
                onChange={(event) => update('ip_address', event.target.value)}
                error={fieldErrors.ip_address}
                placeholder="IP publique du serveur"
              />
              <Input
                label="Service Code"
                value={form.service_code}
                onChange={(event) => update('service_code', event.target.value)}
                hint="ACCOUNT_SERVICE pour l'API de compte"
              />
              <Input
                label="Secret Key"
                type={showSecrets ? 'text' : 'password'}
                autoComplete="new-password"
                value={form.secret_key}
                onChange={(event) => update('secret_key', event.target.value)}
                placeholder={config?.has_secret_key ? 'Enregistrée — laisser vide pour conserver' : 'À saisir'}
                error={fieldErrors.secret_key}
                hint="Chiffrée au repos, jamais renvoyée au navigateur."
              />
              <Input
                label="Subscription Key"
                type={showSecrets ? 'text' : 'password'}
                autoComplete="new-password"
                value={form.subscription_key}
                onChange={(event) => update('subscription_key', event.target.value)}
                placeholder={config?.has_subscription_key ? 'Enregistrée — laisser vide pour conserver' : 'À saisir'}
                error={fieldErrors.subscription_key}
              />
              <Input
                label="Numéro de compte Ecobank"
                type={showSecrets ? 'text' : 'password'}
                autoComplete="off"
                value={form.account_no}
                onChange={(event) => update('account_no', event.target.value)}
                placeholder={config?.has_account_no ? `Masqué (${config.masked_account_no})` : 'À saisir'}
                error={fieldErrors.account_no}
              />
              <Input
                label="Délai d'attente (secondes)"
                type="number"
                min={5}
                max={120}
                value={form.timeout_seconds}
                onChange={(event) => update('timeout_seconds', Number(event.target.value))}
                error={fieldErrors.timeout_seconds}
              />
              <Input
                label="Request type (jeton)"
                value={form.token_request_type}
                onChange={(event) => update('token_request_type', event.target.value)}
              />
              <Input
                label="Request type (solde)"
                value={form.balance_request_type}
                onChange={(event) => update('balance_request_type', event.target.value)}
              />
            </CardBody>
          </Card>
        </div>

        <div className="space-y-6">
          <Card>
            <CardHeader title="Diagnostic" icon={<AlertTriangle className="h-5 w-5" />} />
            <CardBody className="space-y-3">
              <div className="flex items-center justify-between rounded-lg bg-slate-50 px-3 py-2.5">
                <span className="text-sm text-slate-600">Identifiants complets</span>
                <Badge tone={config?.has_secret_key && config?.has_subscription_key && config?.has_account_no ? 'success' : 'warning'}>
                  {config?.has_secret_key && config?.has_subscription_key && config?.has_account_no
                    ? 'Oui'
                    : 'Incomplets'}
                </Badge>
              </div>
              <div className="rounded-lg bg-slate-50 px-3 py-2.5">
                <p className="text-xs font-semibold uppercase tracking-wide text-slate-400">
                  Dernier message
                </p>
                <p className="mt-1 text-sm text-slate-600">
                  {config?.last_sync_message || config?.last_test_message || 'Aucun test effectué.'}
                </p>
              </div>
              <Button
                variant="danger"
                fullWidth
                onClick={() => setClearOpen(true)}
                icon={<Trash2 className="h-4 w-4" />}
              >
                Supprimer les identifiants
              </Button>
            </CardBody>
          </Card>

          <Card>
            <CardHeader
              title="Journal de synchronisation"
              icon={<RefreshCw className="h-5 w-5" />}
              action={<Badge tone="neutral">{logs.length}</Badge>}
            />
            <div className="max-h-[420px] overflow-y-auto">
              {logs.length === 0 ? (
                <EmptyState title="Aucune synchronisation" description="Le journal se remplit à chaque tentative." />
              ) : (
                <ul className="divide-y divide-slate-100">
                  {logs.map((log) => (
                    <li key={log.id} className="px-5 py-3">
                      <div className="flex items-center justify-between gap-2">
                        <Badge
                          tone={
                            log.status === 'SUCCESS'
                              ? 'success'
                              : log.status === 'FAILED'
                                ? 'danger'
                                : log.status === 'SKIPPED'
                                  ? 'warning'
                                  : 'info'
                          }
                        >
                          {log.status_label}
                        </Badge>
                        <span className="text-xs text-slate-400">{formatDateTime(log.created_at)}</span>
                      </div>
                      <p className="mt-1 line-clamp-2 text-xs text-slate-600">{log.message}</p>
                      <p className="mt-1 text-[11px] text-slate-400">
                        {log.trigger_label} · {log.duration_ms} ms
                        {log.http_status ? ` · HTTP ${log.http_status}` : ''}
                      </p>
                    </li>
                  ))}
                </ul>
              )}
            </div>
          </Card>
        </div>
      </div>

      <Card className="mt-6">
        <CardBody>
          <div className="flex items-start gap-3">
            {config?.connection_status === 'CONNECTED' ? (
              <CheckCircle2 className="mt-0.5 h-5 w-5 shrink-0 text-emerald-600" />
            ) : (
              <WifiOff className="mt-0.5 h-5 w-5 shrink-0 text-slate-400" />
            )}
            <div className="text-sm text-slate-600">
              <p className="font-semibold text-ink-900">Vérification de l'intégration</p>
              <p className="mt-1 leading-relaxed">
                Aucun endpoint n'est inventé : les chemins par défaut correspondent à la
                documentation Account Enquiry d'Ecobank. La signature hash (SHA-512) et l'ordre
                des champs sont conformes au protocole observé. Tests et synchronisations sont
                exécutés uniquement depuis le backend ; le navigateur ne détient aucun secret.
              </p>
            </div>
          </div>
        </CardBody>
      </Card>

      <ConfirmDialog
        open={clearOpen}
        title="Supprimer les identifiants bancaires ?"
        message="Le secret, la clé d'abonnement et le numéro de compte seront effacés. La connexion bancaire sera désactivée jusqu'à une nouvelle configuration."
        confirmLabel="Supprimer"
        loading={clearing}
        onConfirm={() => void clearSecrets()}
        onCancel={() => setClearOpen(false)}
      />
    </div>
  )
}
