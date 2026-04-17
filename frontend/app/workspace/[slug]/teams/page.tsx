'use client';

import { useState, useMemo } from 'react';
import { useTeams } from '@/hooks/use-teams';
import { useWorkspaceMembers } from '@/hooks/use-workspace-members';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { Textarea } from '@/components/ui/textarea';
import { Card, CardContent } from '@/components/ui/card';
import { Label } from '@/components/ui/label';
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from '@/components/ui/select';
import {
  Dialog,
  DialogContent,
  DialogHeader,
  DialogTitle,
  DialogFooter,
} from '@/components/ui/dialog';
import { Users, ChevronDown, ChevronUp, Plus } from 'lucide-react';
import type { Team } from '@/lib/types/api';
import { isSessionExpired } from '@/lib/types/auth';
import { PageContainer } from '@/components/layout/page-container';
import { useFormErrors } from '@/lib/errors/use-form-errors';

interface TeamsPageProps {
  params: { slug: string };
}

export default function TeamsPage({ params: { slug: _slug } }: TeamsPageProps) {
  const { teams, isLoading, error, isPendingMutation, createTeam, addMember } = useTeams();
  const { members: workspaceMembers } = useWorkspaceMembers();
  const [expandedId, setExpandedId] = useState<string | null>(null);
  const [createOpen, setCreateOpen] = useState(false);
  const [newName, setNewName] = useState('');
  const [newDescription, setNewDescription] = useState('');
  const [creating, setCreating] = useState(false);
  const [createError, setCreateError] = useState<string | null>(null);

  // Add member dialog state
  const [addMemberTeamId, setAddMemberTeamId] = useState<string | null>(null);
  const [memberUserId, setMemberUserId] = useState('');
  const [addingMember, setAddingMember] = useState(false);
  const [addMemberError, setAddMemberError] = useState<string | null>(null);
  const { handleApiError: handleAddMemberApiError } = useFormErrors();

  const targetTeam = useMemo(
    () => teams.find((t) => t.id === addMemberTeamId) ?? null,
    [teams, addMemberTeamId],
  );

  const availableMembers = useMemo(() => {
    if (!targetTeam) return workspaceMembers;
    const existingIds = new Set(targetTeam.members.map((m) => m.user_id));
    return workspaceMembers.filter((m) => !existingIds.has(m.id));
  }, [targetTeam, workspaceMembers]);

  async function handleCreate(e: React.FormEvent) {
    e.preventDefault();
    if (!newName.trim()) return;
    setCreating(true);
    setCreateError(null);
    try {
      await createTeam({ name: newName.trim(), description: newDescription.trim() || undefined });
      setCreateOpen(false);
      setNewName('');
      setNewDescription('');
    } catch (err) {
      setCreateError(err instanceof Error ? err.message : 'Error al crear el equipo');
    } finally {
      setCreating(false);
    }
  }

  async function handleAddMember(e: React.FormEvent) {
    e.preventDefault();
    if (!addMemberTeamId || !memberUserId) return;
    setAddingMember(true);
    setAddMemberError(null);
    try {
      await addMember(addMemberTeamId, { user_id: memberUserId });
      setAddMemberTeamId(null);
      setMemberUserId('');
    } catch (err) {
      // Field errors (e.g. TEAM_MEMBER_ALREADY_EXISTS with field=user_id) surface as toast
      handleAddMemberApiError(err);
      setAddMemberError(err instanceof Error ? err.message : 'Error al añadir miembro');
    } finally {
      setAddingMember(false);
    }
  }

  function toggleExpand(teamId: string) {
    setExpandedId((prev) => (prev === teamId ? null : teamId));
  }

  function memberCountLabel(team: Team): string {
    const n = team.member_count;
    if (n === 1) return '1 miembro';
    return `${n} miembros`;
  }

  if (isLoading) {
    return (
      <PageContainer variant="wide">
        <h1 className="mb-4 text-h2 font-semibold">Equipos</h1>
        <p className="text-body-sm text-muted-foreground">Cargando...</p>
      </PageContainer>
    );
  }

  if (error) {
    if (isSessionExpired(error)) return null;
    return (
      <PageContainer variant="wide">
        <h1 className="mb-4 text-h2 font-semibold">Equipos</h1>
        <p className="text-body-sm text-destructive">
          No se pudieron cargar los equipos: {error.message}
        </p>
      </PageContainer>
    );
  }

  return (
    <PageContainer variant="wide">
      <div className="mb-6 flex items-center justify-between">
        <h1 className="text-h2 font-semibold">Equipos</h1>
        <Button onClick={() => setCreateOpen(true)}>
          <Plus className="mr-1.5 h-4 w-4" />
          Crear equipo
        </Button>
      </div>

      {teams.length === 0 ? (
        <div className="flex flex-col items-center gap-3 py-16 text-muted-foreground">
          <Users className="h-10 w-10 opacity-30" />
          <p className="text-body">No hay equipos creados</p>
        </div>
      ) : (
        <div className="flex flex-col gap-3">
          {teams.map((team) => {
            const isExpanded = expandedId === team.id;
            return (
              <Card key={team.id}>
                <CardContent className="p-4">
                  <div className="flex items-start justify-between">
                    <button
                      type="button"
                      aria-label={team.name}
                      className="flex flex-1 items-start gap-3 text-left"
                      onClick={() => toggleExpand(team.id)}
                    >
                      <Users className="mt-0.5 h-4 w-4 shrink-0 text-muted-foreground" />
                      <div>
                        <p className="font-medium text-foreground">{team.name}</p>
                        {team.description && (
                          <p className="text-body-sm text-muted-foreground">{team.description}</p>
                        )}
                        <p className="mt-1 text-body-sm text-muted-foreground">
                          {memberCountLabel(team)}
                        </p>
                      </div>
                    </button>
                    <div className="ml-2 mt-0.5 text-muted-foreground">
                      {isExpanded ? (
                        <ChevronUp className="h-4 w-4" />
                      ) : (
                        <ChevronDown className="h-4 w-4" />
                      )}
                    </div>
                  </div>

                  {isExpanded && (
                    <div className="mt-4 border-t pt-4">
                      {team.members.length === 0 ? (
                        <p className="text-body-sm text-muted-foreground">Sin miembros aún.</p>
                      ) : (
                        <ul className="space-y-2">
                          {team.members.map((m) => (
                            <li key={m.id} className="flex items-center gap-2 text-body-sm">
                              <span className="font-medium">{m.full_name}</span>
                              <span className="text-muted-foreground">{m.email}</span>
                            </li>
                          ))}
                        </ul>
                      )}
                      <Button
                        size="sm"
                        variant="outline"
                        className="mt-3"
                        onClick={() => {
                          setAddMemberTeamId(team.id);
                          setMemberUserId('');
                        }}
                      >
                        <Plus className="mr-1 h-3.5 w-3.5" />
                        Añadir miembro
                      </Button>
                    </div>
                  )}
                </CardContent>
              </Card>
            );
          })}
        </div>
      )}

      {/* Create team dialog */}
      <Dialog open={createOpen} onOpenChange={setCreateOpen}>
        <DialogContent>
          <DialogHeader>
            <DialogTitle>Crear equipo</DialogTitle>
          </DialogHeader>
          <form onSubmit={(e) => void handleCreate(e)} className="space-y-4">
            <div className="space-y-1.5">
              <Label htmlFor="team-name">Nombre *</Label>
              <Input
                id="team-name"
                placeholder="Nombre del equipo"
                value={newName}
                onChange={(e) => setNewName(e.target.value)}
                required
              />
            </div>
            <div className="space-y-1.5">
              <Label htmlFor="team-desc">Descripción</Label>
              <Textarea
                id="team-desc"
                placeholder="Descripción opcional"
                value={newDescription}
                onChange={(e) => setNewDescription(e.target.value)}
                rows={3}
              />
            </div>
            {createError && (
              <p className="text-body-sm text-destructive">{createError}</p>
            )}
            <DialogFooter>
              <Button type="button" variant="outline" onClick={() => setCreateOpen(false)}>
                Cancelar
              </Button>
              <Button type="submit" disabled={!newName.trim() || creating}>
                {creating ? 'Creando...' : 'Crear'}
              </Button>
            </DialogFooter>
          </form>
        </DialogContent>
      </Dialog>

      {/* Add member dialog */}
      <Dialog
        open={addMemberTeamId !== null}
        onOpenChange={(o) => {
          if (!o) {
            setAddMemberTeamId(null);
            setMemberUserId('');
            setAddMemberError(null);
          }
        }}
      >
        <DialogContent>
          <DialogHeader>
            <DialogTitle>Añadir miembro{targetTeam ? ` a ${targetTeam.name}` : ''}</DialogTitle>
          </DialogHeader>
          <form onSubmit={(e) => void handleAddMember(e)} className="space-y-4">
            <div className="space-y-2">
              <Label htmlFor="member-user">Usuario</Label>
              {availableMembers.length === 0 ? (
                <p className="text-body-sm text-muted-foreground">
                  No hay más usuarios del workspace disponibles para este equipo.
                </p>
              ) : (
                <Select value={memberUserId} onValueChange={setMemberUserId}>
                  <SelectTrigger id="member-user" className="h-11">
                    <SelectValue placeholder="Selecciona un miembro del workspace" />
                  </SelectTrigger>
                  <SelectContent>
                    {availableMembers.map((m) => (
                      <SelectItem key={m.id} value={m.id}>
                        {m.full_name} · {m.email}
                      </SelectItem>
                    ))}
                  </SelectContent>
                </Select>
              )}
            </div>
            {addMemberError && (
              <p className="text-body-sm text-destructive">{addMemberError}</p>
            )}
            <DialogFooter>
              <Button type="button" variant="outline" onClick={() => setAddMemberTeamId(null)}>
                Cancelar
              </Button>
              <Button type="submit" disabled={!memberUserId || addingMember || isPendingMutation}>
                {addingMember ? 'Añadiendo...' : 'Añadir'}
              </Button>
            </DialogFooter>
          </form>
        </DialogContent>
      </Dialog>
    </PageContainer>
  );
}
