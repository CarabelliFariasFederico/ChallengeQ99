import { useEffect, useRef, useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useSearchParams } from "react-router-dom";

import {
  activateCredential,
  createServiceAccountCredential,
  initiateOAuth,
  listCredentials,
} from "../api/endpoints.js";
import { useToast } from "../components/Toast.jsx";
import { EmptyState, ErrorState, Spinner } from "../components/ui.jsx";

export default function CredentialsSection() {
  const toast = useToast();
  const queryClient = useQueryClient();
  const credentials = useQuery({ queryKey: ["credentials"], queryFn: listCredentials });
  const [searchParams, setSearchParams] = useSearchParams();

  useEffect(() => {
    if (searchParams.get("drive_connected") === "1") {
      toast.success(
        "Cuenta de Google Drive conectada. Activala para empezar a usarla.",
        "oauth/callback",
      );
      queryClient.invalidateQueries({ queryKey: ["credentials"] });
      const next = new URLSearchParams(searchParams);
      next.delete("drive_connected");
      next.delete("credential_id");
      setSearchParams(next, { replace: true });
    }
  }, []);

  const connect = useMutation({
    mutationFn: () => initiateOAuth(),
    onSuccess: (data) => {
      toast.info(
        "Redirigiendo a Google para consentimiento… (state anti-CSRF generado).",
        "oauth/initiate",
      );
      window.location.assign(data.authorization_url);
    },
    onError: (err) => toast.error(err),
  });

  const activate = useMutation({
    mutationFn: activateCredential,
    onSuccess: (credential) => {
      toast.info(
        `Cuenta activa → “${credential.account_label}”. Transacción única + auditada.`,
        "credential.activate",
      );
      queryClient.invalidateQueries({ queryKey: ["credentials"] });
      queryClient.invalidateQueries({ queryKey: ["me"] });
      queryClient.invalidateQueries({ queryKey: ["permissions"] });
      queryClient.invalidateQueries({ queryKey: ["files"] });
    },
    onError: (err) => toast.error(err),
  });

  return (
    <section aria-labelledby="credentials-heading">
      <div className="sect-head">
        <h3 id="credentials-heading" className="sect-title">
          Cuentas de Drive
        </h3>
        <button
          type="button"
          className="btn-navy"
          onClick={() => connect.mutate()}
          disabled={connect.isPending}
        >
          {connect.isPending ? "Redirigiendo…" : "+ Conectar por OAuth"}
        </button>
      </div>

      {credentials.isPending && <Spinner label="cargando credenciales…" />}
      {credentials.isError && <ErrorState error={credentials.error} />}
      {credentials.data?.length === 0 && (
        <EmptyState title="Sin credenciales conectadas todavía." />
      )}

      {credentials.data?.length > 0 && (
        <div className="cred-grid">
          {credentials.data.map((credential) => (
            <div
              key={credential.id}
              className={`cred-card${credential.is_active ? " active" : ""}`}
            >
              <div className="cred-card-row">
                <div className="cred-icon">☁</div>
                <div className="cred-info">
                  <div className="cred-label">{credential.account_label}</div>
                  <div className="cred-method">{credential.auth_method} · conectada</div>
                </div>
                {credential.is_active ? (
                  <span className="badge-active">● Activa</span>
                ) : (
                  <button
                    type="button"
                    className="btn-pill"
                    disabled={activate.isPending}
                    onClick={() => {
                      if (
                        window.confirm(
                          `¿Activar "${credential.account_label}"? Toda la aplicación pasa a operar sobre esa cuenta.`,
                        )
                      ) {
                        activate.mutate(credential.id);
                      }
                    }}
                  >
                    Activar
                  </button>
                )}
              </div>
            </div>
          ))}
        </div>
      )}

      <details className="sa-details">
        <summary>alta alternativa · service account (JSON)</summary>
        <ServiceAccountForm
          onCreated={() => queryClient.invalidateQueries({ queryKey: ["credentials"] })}
        />
      </details>
    </section>
  );
}

function ServiceAccountForm({ onCreated }) {
  const toast = useToast();
  const inputRef = useRef(null);
  const [label, setLabel] = useState("");

  const create = useMutation({
    mutationFn: (payload) => createServiceAccountCredential(payload),
    onSuccess: () => {
      toast.success("Credencial de service account creada (cifrada).", "credential.create");
      setLabel("");
      onCreated();
    },
    onError: (err) => toast.error(err),
    onSettled: () => {
      if (inputRef.current) inputRef.current.value = "";
    },
  });

  async function handleFile(event) {
    const file = event.target.files?.[0];
    if (!file) return;
    try {
      const secret = JSON.parse(await file.text());
      create.mutate({
        account_label: label.trim() || file.name.replace(/\.json$/, ""),
        secret,
      });
    } catch {
      toast.error({ message: "El archivo no es un JSON válido de service account." });
    }
  }

  return (
    <div className="sa-form">
      <label htmlFor="sa-label" className="visually-hidden">
        Nombre de la cuenta
      </label>
      <input
        id="sa-label"
        placeholder="Nombre (ej. Marketing Drive)"
        value={label}
        onChange={(e) => setLabel(e.target.value)}
      />
      <label htmlFor="sa-file" className="visually-hidden">
        Archivo JSON de service account
      </label>
      <input
        id="sa-file"
        ref={inputRef}
        type="file"
        accept=".json,application/json"
        onChange={handleFile}
        disabled={create.isPending}
      />
    </div>
  );
}
