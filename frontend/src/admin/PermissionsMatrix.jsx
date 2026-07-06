import { useEffect, useMemo, useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";

import {
  getPermissionMatrix,
  listCredentials,
  listTeams,
  savePermissionMatrix,
} from "../api/endpoints.js";
import { useToast } from "../components/Toast.jsx";
import { EmptyState, ErrorState, Spinner, localPart } from "../components/ui.jsx";

const ACTIONS = [
  { key: "can_view", label: "Visualizar" },
  { key: "can_download", label: "Descargar" },
  { key: "can_upload", label: "Subir" },
];

const EMPTY_ROW = { can_view: false, can_download: false, can_upload: false };

export default function PermissionsMatrix() {
  const toast = useToast();
  const queryClient = useQueryClient();

  const credentials = useQuery({ queryKey: ["credentials"], queryFn: listCredentials });
  const teams = useQuery({ queryKey: ["teams"], queryFn: listTeams });

  const [credentialId, setCredentialId] = useState(null);
  useEffect(() => {
    if (credentialId === null && credentials.data?.length) {
      const active = credentials.data.find((c) => c.is_active);
      setCredentialId((active ?? credentials.data[0]).id);
    }
  }, [credentials.data, credentialId]);

  const matrix = useQuery({
    queryKey: ["permissions", credentialId],
    queryFn: () => getPermissionMatrix(credentialId),
    enabled: credentialId !== null,
  });

  const [rows, setRows] = useState({});
  useEffect(() => {
    if (matrix.data && teams.data) {
      const initial = {};
      for (const team of teams.data) {
        initial[team.id] = { ...EMPTY_ROW, ...(matrix.data.permissions[String(team.id)] || {}) };
      }
      setRows(initial);
    }
  }, [matrix.data, teams.data]);

  const save = useMutation({
    mutationFn: () =>
      savePermissionMatrix(
        credentialId,
        Object.entries(rows).map(([teamId, flags]) => ({ team_id: Number(teamId), ...flags })),
      ),
    onSuccess: () => {
      toast.success("Permisos guardados y auditados (diff antes/después).", "permission.update");
      queryClient.invalidateQueries({ queryKey: ["permissions", credentialId] });
      queryClient.invalidateQueries({ queryKey: ["me"] });
    },
    onError: (err) => toast.error(err),
  });

  const dirty = useMemo(() => {
    if (!matrix.data || !teams.data) return false;
    return teams.data.some((team) => {
      const server = { ...EMPTY_ROW, ...(matrix.data.permissions[String(team.id)] || {}) };
      const local = rows[team.id] || EMPTY_ROW;
      return ACTIONS.some(({ key }) => server[key] !== local[key]);
    });
  }, [rows, matrix.data, teams.data]);

  if (credentials.isPending || teams.isPending) return <Spinner label="cargando matriz…" />;
  if (credentials.isError) return <ErrorState error={credentials.error} />;
  if (teams.isError) return <ErrorState error={teams.error} />;

  const selected = credentials.data.find((c) => c.id === credentialId);

  return (
    <section aria-labelledby="matrix-heading">
      <div className="sect-head" style={{ justifyContent: "flex-start" }}>
        <h3 id="matrix-heading" className="sect-title">
          Matriz de permisos
        </h3>
        {credentials.data.length > 0 && (
          <>
            <span style={{ fontSize: "12.5px", color: "#6f675a" }}>— cuenta:</span>
            <label htmlFor="matrix-credential" className="visually-hidden">
              Credencial de la matriz
            </label>
            <select
              id="matrix-credential"
              className="matrix-cred-select"
              value={credentialId ?? ""}
              onChange={(e) => setCredentialId(Number(e.target.value))}
            >
              {credentials.data.map((credential) => (
                <option key={credential.id} value={credential.id}>
                  {credential.account_label}
                  {credential.is_active ? " (activa)" : ""}
                </option>
              ))}
            </select>
          </>
        )}
      </div>
      <p className="sect-sub">
        Las tres acciones son independientes. “Proveedores” puede subir sin poder ver ni
        descargar.
      </p>

      {!credentials.data.length && (
        <EmptyState title="Conectá una credencial para asignar permisos." />
      )}
      {matrix.isPending && credentialId !== null && <Spinner label="cargando permisos…" />}
      {matrix.isError && <ErrorState error={matrix.error} />}
      {matrix.data && teams.data.length === 0 && (
        <EmptyState title="Creá equipos para poder asignar permisos." />
      )}

      {matrix.data && teams.data.length > 0 && (
        <>
          <div className="matrix">
            <div className="mhead">
              <span>Equipo</span>
              {ACTIONS.map(({ key, label }) => (
                <span key={key} className="center" style={{ textAlign: "center" }}>
                  {label}
                </span>
              ))}
            </div>
            {teams.data.map((team) => (
              <div className="mrow" key={team.id}>
                <div>
                  <div className="mteam-name">{team.name}</div>
                  <div className="mteam-members">
                    {team.members.length
                      ? team.members.map((m) => localPart(m.email)).join(", ")
                      : "sin miembros"}
                  </div>
                </div>
                {ACTIONS.map(({ key, label }) => {
                  const on = rows[team.id]?.[key] ?? false;
                  return (
                    <div className="mcell" key={key}>
                      <button
                        type="button"
                        className={`toggle-cell${on ? " on" : ""}`}
                        role="checkbox"
                        aria-checked={on}
                        aria-label={`${team.name}: ${label}`}
                        onClick={() =>
                          setRows((current) => ({
                            ...current,
                            [team.id]: { ...EMPTY_ROW, ...current[team.id], [key]: !on },
                          }))
                        }
                      >
                        {on ? "✓" : ""}
                      </button>
                    </div>
                  );
                })}
              </div>
            ))}
          </div>
          <div className="matrix-actions">
            <button
              type="button"
              className="btn-save"
              disabled={!dirty || save.isPending}
              onClick={() => save.mutate()}
            >
              {save.isPending ? "Guardando…" : "Guardar permisos"}
            </button>
            {dirty && <span className="dirty-flag">● cambios sin guardar</span>}
            {selected && !selected.is_active && (
              <span className="mono" style={{ fontSize: "10.5px", color: "#a89f8d" }}>
                editando una cuenta inactiva
              </span>
            )}
          </div>
        </>
      )}
    </section>
  );
}
