# Frontend — React SPA

SPA con dos áreas separadas por rol: **`/admin`** (gestión de equipos, credenciales y
permisos) y **`/files`** (archivos de la cuenta activa). Principio rector, no negociable:
**el frontend nunca autoriza**. Refleja las capacidades que el backend ya decidió
(`GET /api/me`) para no mostrar acciones imposibles, pero **cada acción se revalida en el
servidor**; un `403`/`409` se maneja con su estado o toast, nunca se asume "no puede pasar".

---

## Stack

React 19 · Vite · React Router 7 · **React Query 5** (estado de servidor) · **pnpm**.
Sin librería de UI: estilos propios con design tokens (Space Grotesk + IBM Plex Sans +
JetBrains Mono; navy `#22467a`, verde `#2f6b3f`, ámbar `#a6531a`, canvas `#f6f3ee`).

---

## Desarrollo

Lo normal es levantar todo con `docker compose up` desde la raíz (el contenedor sirve el
build estático con nginx). Para iterar el frontend con hot-reload:

```bash
corepack enable        # una vez; usa el pnpm pinneado en package.json
cd frontend
pnpm install
pnpm dev               # http://localhost:5173, contra el backend dockerizado
pnpm build             # build de producción
```

Builds reproducibles: lockfile `pnpm-lock.yaml` + `--frozen-lockfile` en el Dockerfile +
versión de pnpm fijada por `packageManager`.

| Variable | Descripción |
|----------|-------------|
| `VITE_API_URL` | Base del backend (default `http://localhost:8000`). Se hornea al build. Solo URLs públicas — **sin secretos en el bundle**. |

---

## Estructura

```
frontend/src/
├── main.jsx                 QueryClient + AuthProvider + ToastProvider + Router
├── App.jsx                  rutas con guards
├── styles.css               design tokens + estilos
├── api/
│   ├── client.js            tokens, interceptor 401→refresh, ApiError (sobre del backend)
│   └── endpoints.js         un wrapper por endpoint (upload con progreso incluido)
├── auth/
│   ├── AuthContext.jsx      sesión: boot, login, logout
│   ├── useMe.js             query ["me"]: perfil + capabilities
│   └── guards.jsx           RequireAuth + RequireAdmin
├── components/
│   ├── Layout.jsx           sidebar + topbar (pill "cuenta activa" + badge gateway)
│   ├── Toast.jsx            toasts con tag + request_id del backend
│   └── ui.jsx               Spinner / EmptyState / ErrorState / helpers
├── pages/
│   ├── LoginPage.jsx        split 2-col + accesos rápidos a las cuentas demo
│   ├── FilesPage.jsx        pills de capacidades + estados dedicados + tabla + subida
│   └── AdminPage.jsx        credenciales → matriz de permisos → equipos
└── admin/
    ├── CredentialsSection.jsx   conectar por OAuth · activar · alta por service account
    ├── PermissionsMatrix.jsx    grilla equipo × {ver, descargar, subir} → PUT
    └── TeamsSection.jsx         CRUD de equipos + miembros
```

---

## Patrones del cliente

| Patrón | Dónde | Detalle |
|--------|-------|---------|
| Interceptor de auth | `api/client.js` | Ante un 401 intenta **un** refresh y reintenta; single-flight (varios 401 concurrentes comparten un solo round-trip). Si el refresh falla, la sesión termina y el router lleva a `/login`. |
| Tokens en dos niveles | `api/client.js` | Access token **solo en memoria** (nunca storage); refresh en `sessionStorage` (sobrevive F5 en la misma pestaña, no cruza pestañas — menos superficie que `localStorage`). Si el backend pasara a cookie httpOnly, solo cambia este módulo. |
| UI dirigida por capacidades | `auth/useMe.js` | `/api/me` es **la** fuente para pintar (botones ocultos, link de admin, estados) — y solo para pintar. |
| Route guards | `auth/guards.jsx` | `RequireAuth` (sin sesión → `/login`) y `RequireAdmin` (member → `/files`). Es UX: el backend exige `IsAdministrator` en cada `/api/admin/*` igual. |
| Server-state con React Query | todas las vistas | Keys por recurso (`["me"]`, `["files"]`, `["teams"]`, `["credentials"]`, `["permissions", id]`); las mutaciones invalidan lo derivado — activar una credencial invalida credenciales, me, permisos y archivos, porque cambia la cuenta de todo el sistema. |
| Sobre de errores | `Toast.jsx` + `ui.jsx` | Todo error muestra el `message` del backend con su `request_id` (el "ref:" correlaciona con los logs del server). Sin retry en errores 4xx: si el backend dijo que no, es que no. |
| Upload con progreso | `api/endpoints.js` | XHR (único camino con eventos de progreso) con el JWT en el header; los límites de tamaño/MIME los responde el backend y se muestran tal cual. |
| Descarga autenticada | `api/endpoints.js` | `fetch` con JWT → blob → `<a download>`: el streaming real pasa en el backend; acá solo se dispara el save del browser. |

---

## Pantallas y estados

**Login** — split 2 columnas: panel de marca + formulario. Los chips de cuentas demo
autocompletan email y password (el login igual pasa por el `POST /api/auth/login` real).

**Archivos (`/files`)** — arriba, la franja "Tus permisos sobre esta cuenta" con las tres
pills (verde = concedido). Después, estados excluyentes, cada uno con su render dedicado:

1. **Sin credencial activa** (`me.active_credential.present = false`) → card punteada:
   "No hay una cuenta de Drive activa". No es un error rojo: es un estado del sistema.
2. **Con credencial pero sin `can_view`** → card ámbar con candado ("sin acceso de
   lectura") y, si tiene `can_upload`, el botón de subir. Este es el caso *provider*:
   sube sin poder listar.
3. **Con `can_view`** → dropzone de subida (solo si `can_upload`) + tabla con ícono por
   extensión, tamaño, fecha y "↓ Descargar" solo si `can_download` (si no, "— sin
   permiso"). Paginación por cursor con "Cargar más".

Al pie de la tabla queda explícito: la UI oculta lo que no podés hacer, pero si forzás la
llamada el backend responde 403 — la verdad vive en el servidor.

**Administración (`/admin`, solo admin)** — tres secciones:
- **Cuentas de Drive**: cards con la activa marcada, "+ Conectar por OAuth" (redirige a
  Google; al volver con `?drive_connected=1` refresca y avisa), activar con confirmación
  (cambia la cuenta de todo el sistema), y alta alternativa por JSON de service account.
- **Matriz de permisos**: grilla equipo × {Visualizar, Descargar, Subir} con toggles
  independientes ("sube pero no baja" es simplemente upload tildado y download no),
  indicador de cambios sin guardar y PUT de la matriz completa.
- **Equipos**: cards con miembros (agregar/quitar), crear, renombrar y eliminar.

---