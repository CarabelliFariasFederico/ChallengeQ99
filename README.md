# Servicio de credenciales y permisos de Google Drive

Servicio full-stack que administra **una cuenta de Google Drive a la vez** y controla,
**por grupo**, tres acciones independientes sobre ella: **visualizar**, **descargar** y
**subir**. Los permisos se otorgan a grupos (nunca a usuarios sueltos) y son **por
credencial**: lo que un grupo puede hacer con una cuenta es independiente de lo que puede
hacer con otra. El eje del diseño es la **seguridad**: custodia de secretos cifrados,
autorización server-side con _deny-by-default_ y auditoría de todas las acciones sensibles.

```
┌─────────────┐   HTTPS/JSON   ┌──────────────────┐   ORM    ┌────────────┐
│  Frontend   │ ─────────────▶ │  Backend (DRF)   │ ───────▶ │ PostgreSQL │
│ React (SPA) │   JWT header   │  Django · 4 capas│          └────────────┘
│ /admin      │ ◀───────────── │  api/application │   DriveGateway   ☁ Google Drive
│ /files      │                │  domain/infra    │ ───────────────▶ (o fake en memoria)
└─────────────┘                └──────────────────┘
```

---

## Cómo levantar el proyecto (modo demo, sin Google)

Requisito único: **Docker** (con Compose v2). En una máquina limpia:

```bash
cp .env.example .env       # los defaults sirven tal cual para la demo
docker compose up --build
```

Eso levanta tres servicios: `db` (PostgreSQL 16), `backend` (corre migraciones, siembra la
demo y arranca gunicorn) y `frontend` (build de Vite servido por nginx).

| Servicio | URL |
|----------|-----|
| Frontend | <http://localhost:5173> |
| API | <http://localhost:8000> |
| Health | `GET /healthz` (proceso vivo) · `GET /readyz` (DB + cifrado configurado) |

La demo corre con el **gateway de Drive en modo _fake_** (un Drive en memoria, con archivos
precargados), así que **no necesitás credenciales de Google** para recorrer todo de punta a
punta: login, permisos, subida, descarga, matriz, auditoría.

### Usuarios de demo

> Solo para la demo local — los crea un seed que únicamente corre con
> `DJANGO_DEBUG=True`. Password de todos: **`demo12345`**.

| Usuario | Rol | Equipo | Ver | Descargar | Subir | Qué prueba |
|---------|-----|--------|:---:|:---:|:---:|------------|
| `admin@demo.local` | admin | — | ✗ | ✗ | ✗ | Todo `/admin`. **No hereda acciones de Drive**: `/files` le da 403. |
| `editor@demo.local` | member | Editores | ✓ | ✓ | ✓ | El flujo completo en `/files`. |
| `analyst@demo.local` | member | Analistas | ✓ | ✓ | ✗ | Ve y descarga; si fuerza la subida, 403. |
| `provider@demo.local` | member | Proveedores | ✗ | ✗ | ✓ | **El caso emblemático**: sube sin poder ver ni descargar. |

**Recorrido sugerido (5 min):**

1. Entrá como **admin** → *Administración*: tocá la matriz de permisos, creá un equipo,
   asignale gente. Todo queda auditado.
2. Entrá como **provider** → *Archivos*: no hay lista (no tiene lectura) pero sí el botón
   de subir. Subí algo — después no puede ni verlo.
3. Entrá como **editor** → tabla con archivos, descarga por streaming, subida con progreso.
4. Bonus: como member intentá navegar a `/admin` (te redirige) o pegale a la API a mano —
   el backend responde 403 y lo registra en la auditoría.

---

## Cómo probarlo contra Google Drive REAL

La prueba de verdad toma ~10 minutos. Necesitás una cuenta de Google cualquiera.

### 1. Crear la app OAuth en Google Cloud (una sola vez)

1. Entrá a <https://console.cloud.google.com> y creá un proyecto (ej. `drive-permissions`).
2. **APIs y servicios → Biblioteca** → buscá **Google Drive API** → **Habilitar**.
3. **APIs y servicios → Pantalla de consentimiento OAuth**:
   - Tipo **Externo**, completá nombre y tu email.
   - En **Usuarios de prueba** agregá tu propio Gmail. Con la app en modo *Testing* solo
     los test users pueden dar consentimiento — alcanza perfecto para probar.
4. **APIs y servicios → Credenciales → Crear credenciales → ID de cliente de OAuth**:
   - Tipo: **Aplicación web**.
   - En **URIs de redirección autorizados** agregá exactamente:
     ```
     http://localhost:8000/api/admin/credentials/oauth/callback
     ```
   - Guardá el **Client ID** y el **Client Secret** que te muestra.

### 2. Configurar el `.env`

```bash
# VACÍA a propósito: desactiva el fake y activa el gateway real
# (el compose usa ${VAR-default}: definirla vacía anula el default)
DRIVE_GATEWAY_PROVIDER=

GOOGLE_OAUTH_CLIENT_ID=<client-id>.apps.googleusercontent.com
GOOGLE_OAUTH_CLIENT_SECRET=<client-secret>

# clave de cifrado propia (no usar la default de dev):
# docker compose exec backend python manage.py generate_fernet_key
FERNET_KEY=<clave-generada>
```

```bash
docker compose up -d backend
```

Para confirmar el cambio de modo: el log de arranque dice `drive_gateway=real(google)` y el
badge del topbar de la UI pasa de `gateway: fake` a `gateway: real`.

### 3. Conectar la cuenta y probar

1. Login como `admin@demo.local` → **Administración** → **"+ Conectar por OAuth"**.
2. Elegí tu cuenta de Google. Como la app está en modo Testing vas a ver la advertencia de
   "app no verificada" → *Avanzado* → *Continuar* → aceptá el permiso de Drive. El
   consentimiento usa `access_type=offline` + `prompt=consent` para garantizar el
   _refresh token_, que queda **cifrado** en la base (nunca en claro).
3. **Activá** la credencial nueva (desactiva la demo — solo puede haber una activa).
4. Ojo: la matriz de permisos es **por credencial**. Los permisos del seed apuntan a la
   demo, así que en **Matriz de permisos** seleccioná tu credencial nueva, tildá los flags
   por equipo y guardá.
5. Login como `editor@demo.local`: vas a ver **tus archivos reales de Drive**, con descarga
   por streaming y subida real (el archivo aparece en tu Drive). Como `provider`: sube pero
   no lista — sobre tu Drive de verdad.

**Verificaciones extra que valen la pena:**
- Revocá el acceso de la app en <https://myaccount.google.com/permissions> → el próximo
  `/files` responde `502 drive_auth_failed` con el mensaje de reconectar (así se ve la
  rotación por token revocado).
- Mirá la credencial en `http://localhost:8000/django-admin/`: el secreto cifrado no
  aparece por ningún lado.
- Para volver al modo demo: borrá la línea `DRIVE_GATEWAY_PROVIDER=` del `.env` (vuelve el
  default fake) y `docker compose up -d backend`.

### Troubleshooting

| Síntoma | Causa / solución |
|---------|------------------|
| Backend en crash-loop con `password authentication failed for user "drive"` | Cambiaste `POSTGRES_PASSWORD` en `.env` con un volumen ya inicializado (Postgres fija la password solo en el **primer** init). Solución: `docker compose down -v && docker compose up -d` — el seed recrea la demo. |
| `/files` da `502 drive_auth_failed` en modo real | La credencial activa es la demo (token ficticio) o el token fue revocado. Conectá/reconectá por OAuth y activá. |
| `readyz` devuelve 503 con `"crypto": "unconfigured"` | Falta `FERNET_KEY` válida en el entorno. Generala con `manage.py generate_fernet_key`. |
| 429 al probar login muchas veces | Rate limit anti fuerza bruta (10/min). Esperá el `Retry-After` o ajustá `LOGIN_THROTTLE_RATE`. |

---

## Arquitectura general

Backend en **4 capas explícitas** (el árbol de carpetas ES la arquitectura):

```
backend/apps/
├── api/              PRESENTACIÓN   habla HTTP y nada más: views finas, serializers,
│                                    permission classes, sobre uniforme de errores
├── application/      SERVICE LAYER  casos de uso: activar credencial, matriz de permisos,
│                                    subir/bajar archivos, flujo OAuth, auditoría
├── domain/           DOMINIO        modelos por agregado + PermissionPolicy (autorización
│                                    pura, sin HTTP ni SDK — se testea sin red)
└── infrastructure/   ADAPTERS       Google Drive detrás de una interfaz (gateway real,
                                     fake en memoria, strategies de auth, factory) + cifrado
```

Las views validan → llaman al service → serializan. El dominio no conoce HTTP ni el SDK de
Google. Es una arquitectura por capas **pragmática**: los modelos de Django *son* el dominio
(sin capa de entidades paralela) — coherencia antes que pureza hexagonal.

El frontend sigue el mismo espíritu: **la UI nunca autoriza**. `GET /api/me` devuelve las
capacidades efectivas del usuario y con eso se pinta la pantalla, pero cada acción se
revalida en el servidor; un 403 forzado se muestra con el mensaje del backend.

**Patrones aplicados** (dónde y para qué, el detalle en cada README):

| Patrón | Dónde | Para qué |
|--------|-------|----------|
| Policy Object | `domain/policies.py` | Autorización deny-by-default, unión de permisos de equipos |
| Gateway / Adapter | `infrastructure/drive/gateway.py` | Aislar Google: el resto del código no conoce el SDK |
| Strategy | `infrastructure/drive/strategies.py` | OAuth vs Service Account con la misma interfaz |
| Factory | `infrastructure/drive/factory.py` | De "la credencial activa" a un cliente listo (descifra en memoria) |
| Service Layer | `apps/application/` | Casos de uso testeables, views finas |
| Unit of Work | `application/credentials.py` | Activar credencial: una transacción con lock |
| Test Double (fake) | `infrastructure/drive/fake.py` | Drive en memoria: demo y tests sin red |
| Error envelope | `api/exceptions.py` | `{code, message, details, request_id}` en todos los errores |

---

## Estructura del repositorio

```
.
├── docker-compose.yml       orquesta db + backend + frontend (defaults de dev incluidos)
├── .env.example             plantilla de configuración (el .env NO se commitea)
├── backend/                 Django + DRF → detalle en backend/README.md
└── frontend/                React + Vite → detalle en frontend/README.md
```

- **[backend/README.md](backend/README.md)** — capas y patrones en detalle, API completa,
  modelo de seguridad, cifrado y rotación, observabilidad, tests, variables de entorno.
- **[frontend/README.md](frontend/README.md)** — UI dirigida por capacidades, auth en el
  cliente, guards, estados por pantalla, desarrollo local.

---

## Tests

```bash
docker compose exec backend pytest      # con el stack levantado
docker compose run --rm test            # one-shot (no necesita el backend arriba)
```

**129 tests**: el núcleo de autorización (cada acción con su "puede" y su "**no** puede"),
cifrado y rotación de clave, contrato del gateway, y toda la superficie de la API — OAuth
con su state anti-CSRF, streaming, límites, auditoría de denegados y observabilidad. El
Policy además fue validado con mutation testing (4 mutaciones de seguridad, todas detectadas
por la suite).

---

## Seguridad — resumen

- **Secretos de Drive cifrados en reposo** (Fernet con rotación de clave por versión); la
  clave vive fuera de la DB y el secreto jamás sale por API, logs ni admin.
- **Enforcement 100% server-side**, deny-by-default: la autorización se deriva del token,
  nunca del body.
- **admin ≠ plano de datos**: el rol admin administra; no le da acceso a los archivos.
- **OAuth con `state` anti-CSRF** server-side, de un solo uso y con expiración.
- **Auditoría append-only**; los 403 se registran en transacción propia (un rollback no
  borra la evidencia).
- **Rate limiting** (login y rutas de datos), **IP no spoofeable**, **logs JSON con
  redacción de secretos** y `request_id` correlacionable entre cliente y servidor.

El detalle completo está en `backend/README.md`.


## Stack

Django · Django REST Framework · PostgreSQL 16 · SimpleJWT · cryptography (Fernet) ·
google-api-python-client · React 19 · Vite · React Router · React Query · pnpm ·
docker compose · pytest · ruff.
