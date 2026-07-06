import { useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";

import {
  addMember,
  createTeam,
  deleteTeam,
  listTeams,
  listUsers,
  removeMember,
  updateTeam,
} from "../api/endpoints.js";
import { useToast } from "../components/Toast.jsx";
import {
  EmptyState,
  ErrorState,
  Spinner,
  avatarColors,
  initials,
  localPart,
} from "../components/ui.jsx";

export default function TeamsSection() {
  const toast = useToast();
  const queryClient = useQueryClient();
  const teams = useQuery({ queryKey: ["teams"], queryFn: listTeams });
  const users = useQuery({ queryKey: ["users"], queryFn: listUsers });
  const [name, setName] = useState("");

  const invalidate = () => {
    queryClient.invalidateQueries({ queryKey: ["teams"] });
    queryClient.invalidateQueries({ queryKey: ["me"] });
  };

  const create = useMutation({
    mutationFn: () => createTeam({ name: name.trim() }),
    onSuccess: () => {
      setName("");
      invalidate();
      toast.success("Equipo creado.", "team.change");
    },
    onError: (err) => toast.error(err),
  });

  return (
    <section aria-labelledby="teams-heading" style={{ marginTop: "34px" }}>
      <div className="sect-head">
        <h3 id="teams-heading" className="sect-title">
          Equipos
        </h3>
        <form
          className="new-team-form"
          onSubmit={(e) => {
            e.preventDefault();
            if (name.trim()) create.mutate();
          }}
        >
          <label htmlFor="new-team-name" className="visually-hidden">
            Nombre del nuevo equipo
          </label>
          <input
            id="new-team-name"
            placeholder="Nuevo equipo…"
            value={name}
            onChange={(e) => setName(e.target.value)}
          />
          <button type="submit" className="btn-soft" disabled={create.isPending || !name.trim()}>
            + Crear
          </button>
        </form>
      </div>

      {teams.isPending && <Spinner label="cargando equipos…" />}
      {teams.isError && <ErrorState error={teams.error} />}
      {teams.data?.length === 0 && <EmptyState title="Sin equipos todavía." />}

      {teams.data?.length > 0 && (
        <div className="teams-grid">
          {teams.data.map((team) => (
            <TeamCard key={team.id} team={team} users={users.data || []} onChanged={invalidate} />
          ))}
        </div>
      )}
    </section>
  );
}

function TeamCard({ team, users, onChanged }) {
  const toast = useToast();
  const [selectedUser, setSelectedUser] = useState("");

  const rename = useMutation({
    mutationFn: (nextName) => updateTeam(team.id, { name: nextName }),
    onSuccess: () => {
      onChanged();
      toast.success("Equipo renombrado.", "team.change");
    },
    onError: (err) => toast.error(err),
  });
  const destroy = useMutation({
    mutationFn: () => deleteTeam(team.id),
    onSuccess: () => {
      onChanged();
      toast.success(`Equipo “${team.name}” eliminado (permisos cascadeados).`, "team.change");
    },
    onError: (err) => toast.error(err),
  });
  const add = useMutation({
    mutationFn: () => addMember(team.id, Number(selectedUser)),
    onSuccess: () => {
      setSelectedUser("");
      onChanged();
      toast.success("Miembro agregado.", "membership.change");
    },
    onError: (err) => toast.error(err),
  });
  const remove = useMutation({
    mutationFn: (userId) => removeMember(team.id, userId),
    onSuccess: () => {
      onChanged();
      toast.success("Miembro quitado.", "membership.change");
    },
    onError: (err) => toast.error(err),
  });

  const memberIds = new Set(team.members.map((m) => m.id));
  const candidates = users.filter((u) => !memberIds.has(u.id));
  const count = `${team.members.length} ${team.members.length === 1 ? "miembro" : "miembros"}`;

  return (
    <div className="team-card">
      <div className="team-card-head">
        <div className="team-name">{team.name}</div>
        <span>
          <button
            type="button"
            className="btn-ghost"
            aria-label={`Renombrar ${team.name}`}
            onClick={() => {
              const next = window.prompt("Nuevo nombre del equipo:", team.name);
              if (next && next.trim() !== team.name) rename.mutate(next.trim());
            }}
          >
            ✎
          </button>
          <button
            type="button"
            className="btn-ghost danger"
            aria-label={`Eliminar ${team.name}`}
            onClick={() => {
              if (
                window.confirm(
                  `¿Eliminar "${team.name}"? Sus membresías y permisos de Drive se pierden.`,
                )
              ) {
                destroy.mutate();
              }
            }}
          >
            ✕
          </button>
        </span>
      </div>
      <div className="team-count">{count}</div>

      <div className="team-members">
        {team.members.length === 0 && <span className="no-perm">sin miembros</span>}
        {team.members.map((member) => {
          const colors = avatarColors(member.email);
          return (
            <div className="team-member" key={member.id}>
              <div
                className="avatar avatar-24"
                style={{ background: colors.bg, color: colors.fg }}
              >
                {initials(member.email)}
              </div>
              <span className="name" title={member.email}>
                {localPart(member.email)}
              </span>
              <button
                type="button"
                className="btn-ghost danger"
                aria-label={`Quitar a ${member.email} de ${team.name}`}
                onClick={() => remove.mutate(member.id)}
              >
                ✕
              </button>
            </div>
          );
        })}
      </div>

      <form
        className="team-add"
        onSubmit={(e) => {
          e.preventDefault();
          if (selectedUser) add.mutate();
        }}
      >
        <label htmlFor={`add-member-${team.id}`} className="visually-hidden">
          Agregar miembro a {team.name}
        </label>
        <select
          id={`add-member-${team.id}`}
          value={selectedUser}
          onChange={(e) => setSelectedUser(e.target.value)}
        >
          <option value="">Agregar…</option>
          {candidates.map((user) => (
            <option key={user.id} value={user.id}>
              {user.email}
            </option>
          ))}
        </select>
        <button type="submit" className="btn-pill" disabled={!selectedUser || add.isPending}>
          +
        </button>
      </form>
    </div>
  );
}
