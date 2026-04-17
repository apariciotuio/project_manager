'use client';

import { useState } from 'react';
import { useTeams } from '@/hooks/use-teams';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { Textarea } from '@/components/ui/textarea';
import { Card, CardContent } from '@/components/ui/card';
import { Label } from '@/components/ui/label';
import {
  Dialog,
  DialogContent,
  DialogHeader,
  DialogTitle,
  DialogFooter,
} from '@/components/ui/dialog';
import { Users, ChevronDown, ChevronUp, Plus } from 'lucide-react';
import type { Team } from '@/lib/types/api';

interface TeamsPageProps {
  params: { slug: string };
}

export default function TeamsPage({ params: { slug: _slug } }: TeamsPageProps) {
  const { teams, isLoading, error, createTeam, addMember } = useTeams();
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
    if (!addMemberTeamId || !memberUserId.trim()) return;
    setAddingMember(true);
    try {
      await addMember(addMemberTeamId, { user_id: memberUserId.trim() });
      setAddMemberTeamId(null);
      setMemberUserId('');
    } catch {
      // silently ignore for now
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
      <div className="p-6">
        <h1 className="mb-4 text-h3 font-semibold">Equipos</h1>
        <p className="text-body-sm text-muted-foreground">Cargando...</p>
      </div>
    );
  }

  if (error) {
    return (
      <div className="p-6">
        <h1 className="mb-4 text-h3 font-semibold">Equipos</h1>
        <p className="text-body-sm text-destructive">Error al cargar los equipos.</p>
      </div>
    );
  }

  return (
    <div className="mx-auto max-w-2xl p-6">
      <div className="mb-6 flex items-center justify-between">
        <h1 className="text-h3 font-semibold">Equipos</h1>
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
      <Dialog open={addMemberTeamId !== null} onOpenChange={(o) => !o && setAddMemberTeamId(null)}>
        <DialogContent>
          <DialogHeader>
            <DialogTitle>Añadir miembro</DialogTitle>
          </DialogHeader>
          <form onSubmit={(e) => void handleAddMember(e)} className="space-y-4">
            <div className="space-y-1.5">
              <Label htmlFor="member-id">ID de usuario *</Label>
              <Input
                id="member-id"
                placeholder="UUID del usuario"
                value={memberUserId}
                onChange={(e) => setMemberUserId(e.target.value)}
                required
              />
            </div>
            <DialogFooter>
              <Button type="button" variant="outline" onClick={() => setAddMemberTeamId(null)}>
                Cancelar
              </Button>
              <Button type="submit" disabled={!memberUserId.trim() || addingMember}>
                {addingMember ? 'Añadiendo...' : 'Añadir'}
              </Button>
            </DialogFooter>
          </form>
        </DialogContent>
      </Dialog>
    </div>
  );
}
