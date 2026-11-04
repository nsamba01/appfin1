import {
  KeyRound,
  Lock,
  LockOpen,
  Pencil,
  Plus,
  Search,
  ShieldCheck,
  UserCheck,
  UserX,
  Users as UsersIcon,
} from 'lucide-react'
import { useCallback, useEffect, useState } from 'react'

import { Badge } from '../../components/ui/Badge'
import { Button } from '../../components/ui/Button'
import { Card } from '../../components/ui/Card'
import { EmptyState, ErrorState, Spinner } from '../../components/ui/Feedback'
import { Input, Select } from '../../components/ui/Field'
import { Modal, ConfirmDialog } from '../../components/ui/Modal'
import { PageHeader } from '../../components/ui/PageHeader'
import { useAuth } from '../../contexts/AuthContext'
import { useToast } from '../../contexts/ToastContext'
import { extractErrorMessage, extractFieldErrors } from '../../services/api'
import { adminService } from '../../services/admin'
import type { Role, User } from '../../types'
import { formatDateTime } from '../../utils/format'

interface CreateForm {
  username: string
  full_name: string
  email: string
  role: Role
  password: string
  force_password_change: boolean
}

const EMPTY_CREATE: CreateForm = {
  username: '',
  full_name: '',
  email: '',
  role: 'FINANCE',
  password: '',
  force_password_change: true,
}

export const AdminUsersPage = () => {
  const { user: currentUser } = useAuth()
  const { success, error: notifyError } = useToast()

  const [users, setUsers] = useState<User[]>([])
  const [loading, setLoading] = useState(true)
  const [listError, setListError] = useState('')
  const [search, setSearch] = useState('')
  const [roleFilter, setRoleFilter] = useState<Role | ''>('')

  const [createOpen, setCreateOpen] = useState(false)
  const [createForm, setCreateForm] = useState<CreateForm>(EMPTY_CREATE)
  const [createErrors, setCreateErrors] = useState<Record<string, string>>({})
  const [saving, setSaving] = useState(false)

  const [editing, setEditing] = useState<User | null>(null)
  const [editForm, setEditForm] = useState<{ full_name: string; email: string; role: Role; is_active: boolean }>({
    full_name: '',
    email: '',
    role: 'FINANCE',
    is_active: true,
  })

  const [resetTarget, setResetTarget] = useState<User | null>(null)
  const [newPassword, setNewPassword] = useState('')
  const [forceChange, setForceChange] = useState(true)
  const [resetErrors, setResetErrors] = useState<Record<string, string>>({})
  const [resetting, setResetting] = useState(false)

  const [toggleTarget, setToggleTarget] = useState<User | null>(null)
  const [toggling, setToggling] = useState(false)

  const load = useCallback(async () => {
    setLoading(true)
    setListError('')
    try {
      const data = await adminService.listUsers({
        search: search.trim() || undefined,
        role: roleFilter || undefined,
      })
      setUsers(data.results)
    } catch (err) {
      setListError(extractErrorMessage(err, 'Impossible de charger les utilisateurs.'))
    } finally {
      setLoading(false)
    }
  }, [search, roleFilter])

  useEffect(() => {
    const timer = window.setTimeout(() => void load(), 300)
    return () => window.clearTimeout(timer)
  }, [load])

  const handleCreate = async () => {
    setSaving(true)
    setCreateErrors({})
    try {
      await adminService.createUser({
        ...createForm,
        username: createForm.username.trim(),
      })
      success('Utilisateur créé', `${createForm.username} peut désormais se connecter.`)
      setCreateOpen(false)
      setCreateForm(EMPTY_CREATE)
      await load()
    } catch (err) {
      setCreateErrors(extractFieldErrors(err))
      notifyError('Création impossible', extractErrorMessage(err))
    } finally {
      setSaving(false)
    }
  }

  const openEdit = (user: User) => {
    setEditing(user)
    setEditForm({
      full_name: user.full_name,
      email: user.email,
      role: user.role,
      is_active: user.is_active,
    })
  }

  const handleUpdate = async () => {
    if (!editing) return
    setSaving(true)
    try {
      await adminService.updateUser(editing.id, editForm)
      success('Utilisateur mis à jour', 'Les modifications ont été journalisées.')
      setEditing(null)
      await load()
    } catch (err) {
      notifyError('Modification impossible', extractErrorMessage(err))
    } finally {
      setSaving(false)
    }
  }

  const handleReset = async () => {
    if (!resetTarget) return
    setResetting(true)
    setResetErrors({})
    try {
      await adminService.resetPassword(resetTarget.id, newPassword, forceChange)
      success('Mot de passe réinitialisé', `Transmettez le nouveau mot de passe à ${resetTarget.username}.`)
      setResetTarget(null)
      setNewPassword('')
      await load()
    } catch (err) {
      setResetErrors(extractFieldErrors(err))
      notifyError('Réinitialisation impossible', extractErrorMessage(err))
    } finally {
      setResetting(false)
    }
  }

  const handleToggle = async () => {
    if (!toggleTarget) return
    setToggling(true)
    try {
      const updated = await adminService.toggleActive(toggleTarget.id)
      success(
        updated.is_active ? 'Compte activé' : 'Compte désactivé',
        `${updated.username} a été ${updated.is_active ? 'réactivé' : 'désactivé'}.`,
      )
      setToggleTarget(null)
      await load()
    } catch (err) {
      notifyError('Action impossible', extractErrorMessage(err))
    } finally {
      setToggling(false)
    }
  }

  return (
    <div className="animate-fade-in">
      <PageHeader
        eyebrow="Espace administrateur"
        title="Gestion des utilisateurs"
        description="Créez les comptes financiers, attribuez les rôles et contrôlez les accès."
        actions={
          <Button onClick={() => setCreateOpen(true)} icon={<Plus className="h-4 w-4" />}>
            Nouvel utilisateur
          </Button>
        }
      />

      <Card className="mb-5 p-4">
        <div className="grid gap-3 sm:grid-cols-3">
          <div className="sm:col-span-2">
            <Input
              aria-label="Rechercher un utilisateur"
              placeholder="Rechercher par nom, identifiant ou email…"
              value={search}
              onChange={(event) => setSearch(event.target.value)}
              icon={<Search className="h-4 w-4" />}
            />
          </div>
          <Select
            aria-label="Filtrer par rôle"
            value={roleFilter}
            onChange={(event) => setRoleFilter(event.target.value as Role | '')}
            placeholder="Tous les rôles"
            options={[
              { value: 'FINANCE', label: 'Financiers' },
              { value: 'ADMIN', label: 'Administrateurs' },
            ]}
          />
        </div>
      </Card>

      <Card>
        {loading ? (
          <Spinner label="Chargement des utilisateurs…" />
        ) : listError ? (
          <ErrorState message={listError} onRetry={() => void load()} />
        ) : users.length === 0 ? (
          <EmptyState
            title="Aucun utilisateur"
            description="Créez le premier compte financier."
            icon={<UsersIcon className="h-7 w-7" />}
          />
        ) : (
          <div className="table-shell">
            <table className="min-w-full divide-y divide-slate-100" data-testid="users-table">
              <thead className="bg-slate-50/70">
                <tr>
                  <th className="th">Utilisateur</th>
                  <th className="th">Rôle</th>
                  <th className="th">Statut</th>
                  <th className="th">Dernière connexion</th>
                  <th className="th text-right">Actions</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-slate-100">
                {users.map((user) => (
                  <tr key={user.id} className="group hover:bg-slate-50/70">
                    <td className="td">
                      <div className="flex items-center gap-3">
                        <span className="flex h-9 w-9 items-center justify-center rounded-lg bg-brand-50 text-sm font-bold text-brand-700">
                          {(user.full_name || user.username).slice(0, 2).toUpperCase()}
                        </span>
                        <div>
                          <p className="font-medium text-ink-900">{user.full_name || user.username}</p>
                          <p className="text-xs text-slate-500">
                            {user.username}
                            {user.email ? ` · ${user.email}` : ''}
                          </p>
                        </div>
                      </div>
                    </td>
                    <td className="td">
                      <Badge tone={user.role === 'ADMIN' ? 'brand' : 'info'}>{user.role_label}</Badge>
                    </td>
                    <td className="td">
                      <div className="flex flex-wrap items-center gap-1.5">
                        <Badge tone={user.is_active ? 'success' : 'danger'} dot>
                          {user.is_active ? 'Actif' : 'Désactivé'}
                        </Badge>
                        {user.must_change_password && <Badge tone="warning">Changement requis</Badge>}
                        {user.is_locked && <Badge tone="danger">Verrouillé</Badge>}
                      </div>
                    </td>
                    <td className="td text-slate-500">
                      {user.last_login_at ? formatDateTime(user.last_login_at) : 'Jamais'}
                    </td>
                    <td className="td">
                      <div className="flex items-center justify-end gap-1">
                        <button
                          type="button"
                          onClick={() => openEdit(user)}
                          className="rounded-lg p-2 text-slate-500 transition hover:bg-brand-50 hover:text-brand-700"
                          aria-label={`Modifier ${user.username}`}
                        >
                          <Pencil className="h-4 w-4" />
                        </button>
                        <button
                          type="button"
                          onClick={() => {
                            setResetTarget(user)
                            setNewPassword('')
                            setForceChange(true)
                            setResetErrors({})
                          }}
                          className="rounded-lg p-2 text-slate-500 transition hover:bg-amber-50 hover:text-amber-700"
                          aria-label={`Réinitialiser le mot de passe de ${user.username}`}
                        >
                          <KeyRound className="h-4 w-4" />
                        </button>
                        {user.is_locked && (
                          <button
                            type="button"
                            onClick={async () => {
                              try {
                                await adminService.unlock(user.id)
                                success('Compte déverrouillé', user.username)
                                await load()
                              } catch (err) {
                                notifyError('Déverrouillage impossible', extractErrorMessage(err))
                              }
                            }}
                            className="rounded-lg p-2 text-slate-500 transition hover:bg-emerald-50 hover:text-emerald-700"
                            aria-label={`Déverrouiller ${user.username}`}
                          >
                            <LockOpen className="h-4 w-4" />
                          </button>
                        )}
                        <button
                          type="button"
                          disabled={user.id === currentUser?.id}
                          onClick={() => setToggleTarget(user)}
                          className="rounded-lg p-2 text-slate-500 transition hover:bg-red-50 hover:text-red-600 disabled:cursor-not-allowed disabled:opacity-30"
                          aria-label={`${user.is_active ? 'Désactiver' : 'Activer'} ${user.username}`}
                        >
                          {user.is_active ? <UserX className="h-4 w-4" /> : <UserCheck className="h-4 w-4" />}
                        </button>
                      </div>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </Card>

      {/* Create */}
      <Modal
        open={createOpen}
        onClose={() => setCreateOpen(false)}
        title="Nouvel utilisateur"
        description="Le mot de passe doit être transmis de façon sécurisée à l'utilisateur."
        footer={
          <>
            <Button variant="secondary" onClick={() => setCreateOpen(false)} disabled={saving}>
              Annuler
            </Button>
            <Button onClick={() => void handleCreate()} loading={saving}>
              Créer le compte
            </Button>
          </>
        }
      >
        <div className="grid gap-4 sm:grid-cols-2">
          <Input
            label="Identifiant"
            name="username"
            value={createForm.username}
            onChange={(event) => setCreateForm({ ...createForm, username: event.target.value })}
            error={createErrors.username}
            autoComplete="off"
            required
          />
          <Select
            label="Rôle"
            name="role"
            value={createForm.role}
            onChange={(event) => setCreateForm({ ...createForm, role: event.target.value as Role })}
            options={[
              { value: 'FINANCE', label: 'Financier' },
              { value: 'ADMIN', label: 'Administrateur' },
            ]}
            error={createErrors.role}
            required
          />
          <Input
            label="Nom complet"
            name="full_name"
            value={createForm.full_name}
            onChange={(event) => setCreateForm({ ...createForm, full_name: event.target.value })}
            error={createErrors.full_name}
          />
          <Input
            label="Email (facultatif)"
            name="email"
            type="email"
            value={createForm.email}
            onChange={(event) => setCreateForm({ ...createForm, email: event.target.value })}
            error={createErrors.email}
          />
          <div className="sm:col-span-2">
            <Input
              label="Mot de passe initial"
              name="password"
              type="password"
              autoComplete="new-password"
              value={createForm.password}
              onChange={(event) => setCreateForm({ ...createForm, password: event.target.value })}
              error={createErrors.password}
              hint="10 caractères minimum, avec majuscule, minuscule, chiffre et caractère spécial."
              required
            />
          </div>
          <label className="flex items-center gap-2.5 text-sm text-ink-700 sm:col-span-2">
            <input
              type="checkbox"
              checked={createForm.force_password_change}
              onChange={(event) =>
                setCreateForm({ ...createForm, force_password_change: event.target.checked })
              }
              className="h-4 w-4 rounded border-slate-300 text-brand-600 focus:ring-brand-500"
            />
            Forcer le changement de mot de passe à la première connexion
          </label>
        </div>
      </Modal>

      {/* Edit */}
      <Modal
        open={Boolean(editing)}
        onClose={() => setEditing(null)}
        title="Modifier l'utilisateur"
        description={editing?.username}
        footer={
          <>
            <Button variant="secondary" onClick={() => setEditing(null)} disabled={saving}>
              Annuler
            </Button>
            <Button onClick={() => void handleUpdate()} loading={saving}>
              Enregistrer
            </Button>
          </>
        }
      >
        <div className="grid gap-4 sm:grid-cols-2">
          <Input
            label="Nom complet"
            value={editForm.full_name}
            onChange={(event) => setEditForm({ ...editForm, full_name: event.target.value })}
          />
          <Input
            label="Email"
            type="email"
            value={editForm.email}
            onChange={(event) => setEditForm({ ...editForm, email: event.target.value })}
          />
          <Select
            label="Rôle"
            value={editForm.role}
            onChange={(event) => setEditForm({ ...editForm, role: event.target.value as Role })}
            options={[
              { value: 'FINANCE', label: 'Financier' },
              { value: 'ADMIN', label: 'Administrateur' },
            ]}
          />
          <Select
            label="Statut du compte"
            value={editForm.is_active ? 'active' : 'inactive'}
            onChange={(event) => setEditForm({ ...editForm, is_active: event.target.value === 'active' })}
            options={[
              { value: 'active', label: 'Actif' },
              { value: 'inactive', label: 'Désactivé' },
            ]}
          />
        </div>
      </Modal>

      {/* Reset password */}
      <Modal
        open={Boolean(resetTarget)}
        onClose={() => setResetTarget(null)}
        title="Réinitialiser le mot de passe"
        description={resetTarget?.username}
        size="sm"
        footer={
          <>
            <Button variant="secondary" onClick={() => setResetTarget(null)} disabled={resetting}>
              Annuler
            </Button>
            <Button onClick={() => void handleReset()} loading={resetting} icon={<Lock className="h-4 w-4" />}>
              Réinitialiser
            </Button>
          </>
        }
      >
        <div className="space-y-4">
          <Input
            label="Nouveau mot de passe"
            type="password"
            autoComplete="new-password"
            value={newPassword}
            onChange={(event) => setNewPassword(event.target.value)}
            error={resetErrors.new_password}
            required
          />
          <label className="flex items-center gap-2.5 text-sm text-ink-700">
            <input
              type="checkbox"
              checked={forceChange}
              onChange={(event) => setForceChange(event.target.checked)}
              className="h-4 w-4 rounded border-slate-300 text-brand-600 focus:ring-brand-500"
            />
            Forcer le changement à la prochaine connexion
          </label>
          <p className="flex items-start gap-2 rounded-lg bg-slate-50 p-3 text-xs text-slate-500">
            <ShieldCheck className="mt-0.5 h-4 w-4 shrink-0 text-slate-400" />
            Le mot de passe est haché avant stockage et n'apparaît jamais en clair.
          </p>
        </div>
      </Modal>

      <ConfirmDialog
        open={Boolean(toggleTarget)}
        title={toggleTarget?.is_active ? 'Désactiver ce compte ?' : 'Activer ce compte ?'}
        message={
          toggleTarget?.is_active
            ? `${toggleTarget?.username} ne pourra plus se connecter. Le compte et son historique sont conservés.`
            : `${toggleTarget?.username} pourra à nouveau se connecter.`
        }
        confirmLabel={toggleTarget?.is_active ? 'Désactiver' : 'Activer'}
        tone={toggleTarget?.is_active ? 'danger' : 'primary'}
        loading={toggling}
        onConfirm={() => void handleToggle()}
        onCancel={() => setToggleTarget(null)}
      />
    </div>
  )
}
