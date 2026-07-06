# Backend — Django + DRF

API del servicio de credenciales y permisos de Drive. Todo lo operativo (levantar, usuarios
de demo, guía completa del modo real con Google Cloud) está en el
[README raíz](../README.md); acá va el detalle técnico: capas, patrones, API, seguridad,
observabilidad y tests.

---

## Arquitectura por capas

Arquitectura **por capas pragmática**: la lógica de permisos y los casos de uso no dependen
de HTTP/DRF y se testean sin red; la persistencia usa el ORM de Django directamente — **los
modelos de Django _son_ el dominio**, sin una capa de entidades paralela. La pureza
hexagonal total queda anotada como evolución para producción, no implementada acá:
coherencia > pureza.

La regla de dependencias va en un solo sentido: `api → application → domain ← infrastructure`
(la infraestructura conoce el dominio; el dominio no conoce a nadie).

```
backend/apps/
├── api/                     ▸ PRESENTACIÓN — habla HTTP, nada más
│   ├── views/               · auth · teams · users · credentials · files · oauth
│   │                          (finas: validar → llamar al service → serializar)
│   ├── serializers.py       · DTOs de entrada/salida (el secreto no es serializable)
│   ├── permissions.py       · IsAdministrator + HasDrivePermission → adaptan la Policy a DRF
│   ├── exceptions.py        · sobre uniforme {code, message, details, request_id}
│   └── urls.py
│
├── application/             ▸ SERVICE LAYER — casos de uso
│   ├── credentials.py       · activate_credential() [Unit of Work] · set_permissions_matrix()
│   ├── files.py             · list / upload / open_download (orquesta gateway + auditoría)
│   ├── oauth.py             · start_connection · consume_state · complete_connection
│   └── audit.py             · registro de acciones sensibles (con IP confiable)
│
├── domain/                  ▸ DOMINIO — reglas puras
│   ├── models/              · user · team · credential · permission · audit · oauth_state
│   │                          (un módulo por agregado, mismo app_label "domain")
│   └── policies.py          · PermissionPolicy
│
└── infrastructure/          ▸ ADAPTERS al mundo externo
    ├── drive/
    │   ├── gateway.py       · interfaz DriveGateway + excepciones tipadas
    │   ├── strategies.py    · OAuthStrategy / ServiceAccountStrategy
    │   ├── factory.py       · DriveClientFactory (+ punto de inyección del fake)
    │   ├── google.py        · implementación real (SDK traducido a excepciones propias)
    │   ├── fake.py          · Drive en memoria — demo y tests, jamás producción
    │   └── oauth_flow.py    · consent URL + intercambio code→token (HTTP puro, mockeable)
    └── crypto/
        └── secret_box.py    · cifrado Fernet con versiones de clave
```

---

## Patrones aplicados

| Patrón | Archivo | Qué resuelve |
|--------|---------|--------------|
| **Policy Object** | `domain/policies.py` | Toda la autorización en un objeto puro: `can(user, action, credential)` con deny-by-default, unión de permisos de los equipos del usuario, una sola query (sin N+1). El rol admin NO da acciones de Drive a propósito. |
| **Gateway / Adapter** | `drive/gateway.py` | Interfaz mínima (`list_files / get_metadata / download / upload`) con excepciones tipadas (`DriveNotFound`, `DriveAuthError`…). El SDK de Google nunca se filtra hacia arriba. |
| **Strategy** | `drive/strategies.py` | Cómo se obtienen credenciales de Google: refresh token OAuth o JSON de service account, misma interfaz `build_credentials()`. Cambiar el método de auth no toca nada más. |
| **Factory** | `drive/factory.py` | De "la credencial ACTIVA" a un gateway listo: descifra el secreto **en memoria** y elige la Strategy según `auth_method`. `DRIVE_GATEWAY_PROVIDER` permite inyectar el fake sin tocar código. |
| **Service Layer** | `apps/application/` | Los casos de uso viven fuera de las views: se testean sin HTTP y las views quedan finas. |
| **Unit of Work** | `application/credentials.py` | `activate_credential()`: desactivar la anterior + activar + auditar en UNA transacción con `select_for_update` — el constraint "a lo sumo una activa" vale en todo momento. |
| **Test Double** | `drive/fake.py` | Drive en memoria coherente (lo subido se lista y se baja). Toda la suite corre sin red. |
| **Error envelope** | `api/exceptions.py` | Punto único de errores: mapea excepciones de infraestructura a HTTP (409/404/502…), sanea mensajes upstream, audita los 403 y estampa `request_id`. |
| **Middleware de correlación** | `config/observability.py` | `X-Request-ID` por request; el mismo id viaja en el header, el sobre de error y cada línea de log. |
| **Seed idempotente** | `domain/management/commands/seed_demo.py` | Datos de demo reproducibles; corre en cada arranque y no duplica ni pisa un setup real. |

---

## API

Todos los errores salen con el sobre `{code, message, details, request_id}`.

### Autenticación

| Método y ruta | Qué hace |
|---|---|
| `POST /api/auth/login` | email + password → `{access, refresh}` (JWT). Throttle 10/min. Audita éxitos y fallos. |
| `POST /api/auth/refresh` | Rota el par (el refresh viejo queda blacklisteado). |
| `GET /api/me` | Perfil + **capacidades efectivas** sobre la credencial activa + modo del gateway. Informativo para la UI — no autoriza nada. |

### Plano de administración — requiere rol `admin`

| Método y ruta | Qué hace |
|---|---|
| `GET/POST /api/admin/teams` · `GET/PATCH/DELETE /api/admin/teams/{id}` | CRUD de equipos (lifecycle auditado; el delete registra qué memberships/permisos cascadeó). |
| `POST/DELETE /api/admin/teams/{id}/members` | Alta/baja de miembros (`{user_id}` en el body). |
| `GET /api/admin/users` | Listado para poblar selects. |
| `GET/POST /api/admin/credentials` | Lista (sin secreto, ni siquiera se SELECTea) / alta por service account (el JSON se cifra antes de guardar). |
| `POST /api/admin/credentials/{id}/activate` | Cambia la cuenta activa. Unit of Work. |
| `GET/PUT /api/admin/credentials/{id}/permissions` | Matriz equipo × {ver, descargar, subir}. El PUT reemplaza la matriz entera y audita el diff. |
| `POST /api/admin/credentials/oauth/initiate` | Genera la URL de consentimiento + state anti-CSRF. |
| `GET /api/admin/credentials/oauth/callback` | Consume el state (un solo uso), cambia code→tokens, guarda el refresh **cifrado** y redirige al frontend. Sin JWT a propósito: el state ES la autenticación del flujo. |

### Plano de datos — requiere el permiso del grupo sobre la credencial activa

| Método y ruta | Permiso | Qué hace |
|---|---|---|
| `GET /api/files` | `can_view` | Lista con paginación por cursor (`page_token`). |
| `GET /api/files/{id}/content` | `can_download` | Descarga como **streaming proxy** (el backend nunca guarda el archivo). |
| `POST /api/files` | `can_upload` | Subida multipart en streaming, con límite de tamaño y MIME configurables. |

Sin credencial activa las rutas de datos responden `409 no_active_credential` (estado del
sistema), distinto del `403` (vos no tenés permiso — y queda auditado).

---

## Modelo de seguridad

| Amenaza | Mitigación |
|---------|-----------|
| Robo de la DB | Secretos cifrados (Fernet + HMAC); la clave vive fuera, por entorno. |
| Escalación vía cliente | La UI nunca autoriza; deny-by-default en el Policy; nada del body decide permisos. |
| Admin "todo poderoso" | Plano admin ≠ plano de datos: un admin sin grant no lista ni descarga nada. |
| CSRF en el connect OAuth | `state` server-side, expira a los 10 min, **un solo uso** (consumido bajo lock), atado al admin que inició. |
| Fuerza bruta de login | Throttle 10/min (429 + `Retry-After`) y auditoría de `login.failed` (email + IP, nunca la password). |
| IP spoofing en auditoría | `REMOTE_ADDR` por defecto; `X-Forwarded-For` solo con `AUDIT_TRUST_X_FORWARDED_FOR=True` (último hop). |
| Borrado de evidencia | AuditLog append-only; los 403 se escriben **fuera** de la transacción del caso de uso (autocommit) — un rollback no los borra. |
| Fugas por logs | Logs JSON con redacción de tokens/passwords/keys (con test que lo verifica). |
| Detalles internos al cliente | Los mensajes de Google se sanean: al cliente va un mensaje fijo, el detalle real al log correlacionado por `request_id`. |

### Cifrado y rotación de clave

`SecretBox` (Fernet) con **versiones de clave**: cada registro guarda `key_version`, así que
rotar la clave maestra es agregar una nueva al mapa sin re-conectar cuentas:

```bash
# generar una clave
docker compose exec backend python manage.py generate_fernet_key

# .env — una sola clave:
FERNET_KEY=<clave>

# .env — rotación (encrypt usa la versión más alta; lo viejo sigue descifrando):
FERNET_KEYS=1:<clave-vieja>,2:<clave-nueva>
```

Sin clave válida, cualquier operación de cifrado falla fuerte (`CryptoConfigError` → 503
accionable) y `readyz` lo reporta. Nunca se opera con cifrado roto en silencio.

### Fake vs real (mecánica)

`DriveClientFactory.build()` corta por `DRIVE_GATEWAY_PROVIDER`: si apunta a un callable
(el default de dev es `apps.infrastructure.drive.fake.default_fake_gateway`), devuelve ese
gateway sin tocar credencial ni crypto; si está **vacía**, arma el `GoogleDriveGateway` real
descifrando el secreto de la credencial activa. La guía paso a paso para conseguir las
credenciales de Google está en el [README raíz](../README.md#cómo-probarlo-contra-google-drive-real).

---

## Observabilidad

- **Logs JSON** a stdout, un objeto por línea: `ts, level, logger, message, request_id` —
  con redacción de material sensible antes de escribir.
- **X-Request-ID**: se genera (o propaga) por request; es el mismo id del sobre de error,
  así el "ref:" que ve el usuario correlaciona 1:1 con la línea de log.
- **Health checks**: `GET /healthz` → 200 si el proceso vive (sin dependencias).
  `GET /readyz` → 200 solo si la DB responde **y** hay clave de cifrado válida; 503 con el
  detalle si no. No consulta Google a propósito (una caída upstream no debe sacar al
  servicio del balanceador).
- **Log de arranque** sin secretos: modo del gateway, crypto configurado, debug.

### Rate limits (env-configurables)

| Ruta | Default | Variable |
|------|---------|----------|
| `POST /api/auth/login` | 10/min | `LOGIN_THROTTLE_RATE` |
| `GET /api/files` | 120/min | `DRIVE_LIST_THROTTLE_RATE` |
| `GET /api/files/{id}/content` | 60/min | `DRIVE_DOWNLOAD_THROTTLE_RATE` |
| `POST /api/files` | 30/min | `DRIVE_UPLOAD_THROTTLE_RATE` |

---

## Tests

```bash
docker compose exec backend pytest      # stack levantado
docker compose run --rm test            # one-shot
```

**129 tests**, sin red (el fake reemplaza a Google y el intercambio OAuth se mockea):

| Suite | Tests | Qué cubre |
|-------|------:|-----------|
| `domain/tests/test_policy.py` | 29 | Puede / **no puede** por acción, unión de equipos, admin sin herencia, aislamiento entre credenciales, sujetos hostiles (anónimo/None/deshabilitado), sin N+1 (query count). |
| `domain/tests/test_seed_demo.py` | 4 | Idempotencia, matriz documentada, freno con `DEBUG=False`. |
| `infrastructure/tests/test_secret_box.py` | 18 | Round-trip, ciphertext ≠ plaintext, rotación por versión, claves inválidas fallan fuerte. |
| `infrastructure/tests/test_drive_gateway.py` | 8 | Contrato del gateway vía el fake: upload→list→download coherente, paginación, errores tipados. |
| `infrastructure/tests/test_factory.py` | 4 | Selección de Strategy, sin-credencial-activa, inyección del fake. |
| `api/tests/` (6 suites) | 66 | Enforcement por acción, caso Proveedores, secreto nunca en respuestas, streaming, OAuth completo (state inválido/vencido/reusado), auditoría de denegados, throttle, observabilidad. |

El Policy además pasó por **mutation testing**: 4 mutaciones de seguridad (confusión de
flags, bypass de elegibilidad, allow-all, activa fantasma) — la suite detectó todas.

Lint y formato:

```bash
docker compose run --rm backend ruff check .
docker compose run --rm backend ruff format --check .
```

---

## Comandos útiles

```bash
docker compose exec backend python manage.py generate_fernet_key   # clave de cifrado
docker compose exec backend python manage.py seed_demo             # re-sembrar la demo
docker compose exec backend python manage.py createsuperuser       # admin propio
# Django admin (inspección): http://localhost:8000/django-admin/
```

---

## Variables de entorno

Ver `.env.example`. Todas tienen default de dev en `docker-compose.yml`.

| Variable | Descripción |
|----------|-------------|
| `DJANGO_SECRET_KEY` · `DJANGO_DEBUG` · `DJANGO_ALLOWED_HOSTS` | Config base de Django |
| `POSTGRES_DB/USER/PASSWORD/HOST/PORT` | Conexión a la base |
| `CORS_ALLOWED_ORIGINS` | Orígenes del frontend |
| `FERNET_KEY` / `FERNET_KEYS` | Clave(s) de cifrado — `FERNET_KEYS` versionada gana |
| `DRIVE_GATEWAY_PROVIDER` | Ruta al fake = demo sin red · **vacía** = Google real |
| `DRIVE_FAKE_SEED_FILES` | Precarga archivos de demo en el fake |
| `GOOGLE_OAUTH_CLIENT_ID/SECRET/REDIRECT_URI` | App OAuth de Google |
| `FRONTEND_URL` | A dónde redirige el callback OAuth |
| `OAUTH_STATE_TTL_SECONDS` | Vida del state anti-CSRF (default 600) |
| `DRIVE_UPLOAD_MAX_BYTES` · `DRIVE_UPLOAD_ALLOWED_MIME_TYPES` | Límites de subida |
| `LOGIN/DRIVE_LIST/DRIVE_DOWNLOAD/DRIVE_UPLOAD_THROTTLE_RATE` | Rate limits |
| `AUDIT_TRUST_X_FORWARDED_FOR` | Solo `True` detrás de un proxy propio |
