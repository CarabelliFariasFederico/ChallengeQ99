import { useRef, useState } from "react";
import { useInfiniteQuery, useMutation, useQueryClient } from "@tanstack/react-query";

import { downloadFile, listFiles, uploadFile } from "../api/endpoints.js";
import { useMe } from "../auth/useMe.js";
import { useToast } from "../components/Toast.jsx";
import { ErrorState, Spinner, formatBytes } from "../components/ui.jsx";

const EXT_COLORS = {
  PDF: { bg: "#fbeeee", fg: "#b23b3b" },
  XLS: { bg: "#edf5ee", fg: "#2f6b3f" },
  CSV: { bg: "#edf5ee", fg: "#2f6b3f" },
  DOC: { bg: "#eef2f8", fg: "#22467a" },
  TXT: { bg: "#eef2f8", fg: "#22467a" },
  ZIP: { bg: "#faf1e5", fg: "#a6531a" },
  PNG: { bg: "#faf1e5", fg: "#a6531a" },
  JPG: { bg: "#faf1e5", fg: "#a6531a" },
};

function extOf(file) {
  const raw = (file.name?.split(".").pop() || "").toUpperCase();
  return raw.length > 3 ? raw.slice(0, 3) : raw || "?";
}

function typeLabel(mime) {
  if (!mime) return "—";
  const map = {
    "application/pdf": "PDF",
    "text/plain": "Texto",
    "text/csv": "CSV",
    "image/png": "Imagen",
    "image/jpeg": "Imagen",
  };
  if (map[mime]) return map[mime];
  if (mime.includes("spreadsheet")) return "Excel";
  if (mime.includes("word")) return "Word";
  if (mime.includes("zip")) return "Archivo";
  return mime.split("/").pop().slice(0, 12);
}

function dateLabel(iso) {
  if (!iso) return "—";
  try {
    return new Date(iso).toLocaleDateString("es-AR", { day: "numeric", month: "short" });
  } catch {
    return "—";
  }
}


function useUpload(accountLabel) {
  const toast = useToast();
  const queryClient = useQueryClient();
  const inputRef = useRef(null);
  const [progress, setProgress] = useState(null);

  const mutation = useMutation({
    mutationFn: (file) => uploadFile(file, { onProgress: setProgress }),
    onSuccess: (metadata) => {
      toast.success(
        `Archivo subido a ${accountLabel} — “${metadata.name}”, streaming sin tocar disco del backend.`,
        "201 Created",
      );
      queryClient.invalidateQueries({ queryKey: ["files"] });
    },
    onError: (err) => toast.error(err),
    onSettled: () => {
      setProgress(null);
      if (inputRef.current) inputRef.current.value = "";
    },
  });

  const input = (
    <input
      ref={inputRef}
      type="file"
      className="visually-hidden"
      aria-label="Elegir archivo para subir"
      onChange={(e) => {
        const file = e.target.files?.[0];
        if (file) mutation.mutate(file);
      }}
    />
  );
  return { input, open: () => inputRef.current?.click(), progress, isPending: mutation.isPending };
}

export default function FilesPage() {
  const me = useMe();

  if (me.isPending) return <Spinner label="cargando perfil…" />;
  if (me.isError) return <ErrorState error={me.error} />;

  const { capabilities, active_credential: activeCredential } = me.data;

  return (
    <div className="screen">
      
      <div className="caps-strip">
        <span className="lead">Tus permisos sobre esta cuenta:</span>
        <div className="caps-pills">
          <CapPill label="Ver" on={capabilities.can_view} />
          <CapPill label="Descargar" on={capabilities.can_download} />
          <CapPill label="Subir" on={capabilities.can_upload} />
        </div>
      </div>

      {!activeCredential.present ? (
        <NoCredential />
      ) : !capabilities.can_view ? (
        <NoView canUpload={capabilities.can_upload} accountLabel={activeCredential.account_label} />
      ) : (
        <FileBrowser
          capabilities={capabilities}
          accountLabel={activeCredential.account_label}
        />
      )}
    </div>
  );
}

function CapPill({ label, on }) {
  return (
    <span className={`cap-pill ${on ? "on" : "off"}`}>
      ✓ {label}
    </span>
  );
}

function NoCredential() {
  return (
    <div className="state-nocred">
      <div className="icon">🗂️</div>
      <div className="state-title">No hay una cuenta de Drive activa</div>
      <p className="state-body">
        Un administrador todavía no conectó ni activó una cuenta. Cuando lo haga, tus
        archivos aparecerán acá.
      </p>
    </div>
  );
}


function NoView({ canUpload, accountLabel }) {
  const upload = useUpload(accountLabel);
  return (
    <div className="state-noview">
      <div className="lock-circle">🔒</div>
      <div className="state-title">No tenés acceso de lectura a esta cuenta</div>
      <p className="state-body">
        Tu equipo no tiene el permiso <b>Visualizar</b> sobre la cuenta activa. Puede que sí
        puedas subir archivos, aunque no listarlos — las acciones son independientes.
      </p>
      {canUpload && (
        <div className="state-action">
          {upload.input}
          <button
            type="button"
            className="btn-upload"
            onClick={upload.open}
            disabled={upload.isPending}
          >
            {upload.isPending
              ? `Subiendo… ${upload.progress ?? 0}%`
              : "↑ Subir un archivo"}
          </button>
        </div>
      )}
    </div>
  );
}

function FileBrowser({ capabilities, accountLabel }) {
  const toast = useToast();
  const upload = useUpload(accountLabel);

  const filesQuery = useInfiniteQuery({
    queryKey: ["files"],
    queryFn: ({ pageParam }) => listFiles({ pageToken: pageParam }),
    initialPageParam: null,
    getNextPageParam: (lastPage) => lastPage.next_page_token ?? undefined,
  });

  const download = useMutation({
    mutationFn: downloadFile,
    onSuccess: (_, file) =>
      toast.success(`Descargando “${file.name}” — stream proxy desde Drive.`, "200 OK"),
    onError: (err) => toast.error(err),
  });

  if (filesQuery.isPending) return <Spinner label="cargando archivos…" />;
  if (filesQuery.isError) {
    if (filesQuery.error.code === "no_active_credential") return <NoCredential />;
    return <ErrorState error={filesQuery.error} />;
  }

  const files = filesQuery.data.pages.flatMap((page) => page.items);

  return (
    <div>
      {capabilities.can_upload && (
        <>
          {upload.input}
          <button
            type="button"
            className="dropzone"
            onClick={upload.open}
            disabled={upload.isPending}
          >
            <div className="dropzone-icon">↑</div>
            <div>
              <div className="dropzone-title">Subir archivo a {accountLabel}</div>
              <div className="dropzone-sub">
                {upload.isPending
                  ? `Subiendo… ${upload.progress ?? 0}%`
                  : "Hacé clic para elegir — límite 25 MB · streaming"}
              </div>
            </div>
            {upload.progress !== null && (
              <progress value={upload.progress} max="100" aria-label="Progreso de subida" />
            )}
          </button>
        </>
      )}

      <div className="ftable">
        <div className="fhead">
          <span>Nombre</span>
          <span>Tipo</span>
          <span>Tamaño</span>
          <span style={{ textAlign: "right" }}>Acción</span>
        </div>
        {files.length === 0 && (
          <div className="frow">
            <span className="ftype">La cuenta no tiene archivos visibles todavía.</span>
          </div>
        )}
        {files.map((file) => {
          const ext = extOf(file);
          const colors = EXT_COLORS[ext] ?? { bg: "#f4f1ea", fg: "#6f675a" };
          return (
            <div className="frow" key={file.id}>
              <div className="fname-cell">
                <div className="fext" style={{ background: colors.bg, color: colors.fg }}>
                  {ext}
                </div>
                <div style={{ minWidth: 0 }}>
                  <div className="fname">{file.name}</div>
                  <div className="fdate">{dateLabel(file.modified_at)}</div>
                </div>
              </div>
              <span className="ftype">{typeLabel(file.mime_type)}</span>
              <span className="fsize">{formatBytes(file.size)}</span>
              <div className="faction">
                {capabilities.can_download ? (
                  <button
                    type="button"
                    className="btn-soft"
                    disabled={download.isPending}
                    onClick={() => download.mutate(file)}
                  >
                    ↓ Descargar
                  </button>
                ) : (
                  <span className="no-perm" title="Tu equipo no tiene permiso de descarga">
                    — sin permiso
                  </span>
                )}
              </div>
            </div>
          );
        })}
      </div>

      {filesQuery.hasNextPage && (
        <button
          type="button"
          className="btn-soft load-more"
          onClick={() => filesQuery.fetchNextPage()}
          disabled={filesQuery.isFetchingNextPage}
        >
          {filesQuery.isFetchingNextPage ? "Cargando…" : "Cargar más"}
        </button>
      )}

      <p className="ftable-note">
        La UI oculta lo que no podés hacer — pero si forzaras la llamada, el backend
        responde 403. La verdad vive en el servidor.
      </p>
    </div>
  );
}
