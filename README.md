# scrabbly-cloud

Plataforma de Scrabble online en tiempo real, al estilo Lichess: lobby con
emparejamiento, partidas en vivo para espectar, ratings ELO y juego sin
necesidad de registrarse (cuentas de invitado).

## Stack

- **Django 5** + **Channels 4** (ASGI / WebSockets) servido por **Daphne**.
- Motor de Scrabble propio en Python puro (`game/engine.py`) — tablero 15x15,
  distribución española moderna (100 fichas), casillas premium, bonus de
  bingo y validación de jugadas. Reemplaza la antigua dependencia externa.
- Frontend en JavaScript vanilla (sin jQuery), tema oscuro responsive.

## Funcionalidades

- **Multi-idioma**: Scrabble en **español** e **inglés**, cada uno con su
  distribución de fichas, valores de letras y diccionario propios. El idioma
  se elige al crear/emparejar partida (el emparejamiento rápido respeta el
  idioma elegido).
- **Validación con diccionario**: las jugadas se validan contra listas de
  palabras por idioma (ver `dictionaries/`).
- **Lobby / emparejamiento**: partida rápida (quick pairing), crear/unirse a
  partidas abiertas, lista de partidas en vivo.
- **Cuentas de invitado**: cualquier visitante puede jugar al instante; al
  registrarse, su rating e historial se conservan.
- **Ratings ELO**: ranking de jugadores y perfiles con estadísticas.
- **Espectar**: ver partidas en curso en vivo (los atriles rivales nunca se
  envían a oponentes ni espectadores).
- **Relojes**: controles de tiempo estilo Fischer (3–30 min, con incremento)
  con cuenta regresiva en vivo y derrota por tiempo (flag).
- **Tablas y revancha**: ofrecer/aceptar tablas durante la partida; pedir
  revancha al terminar (crea una nueva partida con asientos invertidos).
- **Historial navegable**: revisá la partida jugada por jugada y volvé al vivo.
- **Compartir**: cada partida tiene una URL; botón para copiar el enlace.
- **Tiempo real**: tablero, marcador, registro de jugadas y chat por WebSocket,
  con reconexión automática (backoff exponencial) e indicador de conexión.
- **Calidad de vida**: arrastrar y soltar fichas (con recogida y reposición),
  sonidos opcionales, aviso de turno (notificación + título de pestaña) y
  persistencia de las fichas que estás colocando ante recargas.

- **Lobby**: filtros por idioma y rating, paginación de partidas abiertas y
  listado paginado de partidas recientes (terminadas).
- **Rival IA**: jugá contra la computadora en cinco niveles (principiante,
  fácil, media, difícil y experta). El motor usa un **DAWG** (autómata de
  palabras minimizado) y generación con *cross-checks* tipo Appel-Jacobson:
  encuentra **todas** las jugadas legales del tablero —hooks, extensiones,
  through-plays y jugadas paralelas— en fracciones de segundo. El nivel experto
  rankea por *equity* (puntaje + heurística de fichas que quedan en el atril).
- **Modo correspondencia**: partidas sin reloj jugables a lo largo del tiempo,
  con la sección «Te toca jugar» que lista las partidas que esperan tu turno.
- **Perfiles y avatares**: avatares identicon generados (sin subidas), perfil
  con estadísticas (% de victorias, racha de resultados, historial).
- **Anti-spam**: rate-limiting por usuario en las acciones de juego.
- **Premium (suscripción)**: monetización estilo chess.com con dos niveles —
  **Gold** (temas, estadísticas avanzadas, insignia, partidas ilimitadas) y
  **Diamond** (todo lo de Gold + análisis post-partida). Incluye **prueba
  gratis** (una vez por usuario), **cupones de descuento** y **portal de
  cliente** para autogestión.

## Premium / pagos

Niveles y planes (mensual/anual) definidos en `billing/plans.py`. La capa de
cobro es agnóstica del proveedor:

- Sin `STRIPE_SECRET_KEY`, un proveedor **mock** activa la suscripción al
  instante (dev/demo y tests), aplicando trial y cupones locales.
- Con `STRIPE_SECRET_KEY`, `STRIPE_PUBLISHABLE_KEY` y `STRIPE_WEBHOOK_SECRET`,
  se usa **Stripe Checkout** (modo suscripción, con `trial_period_days` y
  códigos promocionales nativos), el **Billing Portal** de Stripe para
  autogestión, y el webhook `POST /billing/stripe/webhook/`
  (`checkout.session.completed` / `invoice.paid` / `customer.subscription.deleted`).

Perks por nivel se controlan con `user.has_perk(...)`. Cupones (`Coupon`) y
trial se gestionan desde el admin. Las cuentas gratuitas tienen un tope de
partidas simultáneas (`FREE_CONCURRENT_GAMES`); Premium es ilimitado.

Además: **tier vitalicio** (pago único), **regalar Premium** (códigos de
regalo, `/premium/gift/`), **emails transaccionales** (bienvenida, recibo,
aviso de pago fallido — backend de consola en dev, SMTP por env en prod),
**dunning** (webhook `invoice.payment_failed` marca `past_due` y avisa al
cliente), y un **panel de métricas** staff-only (`/premium/metrics/`: MRR/ARR,
conversión, churn, suscripciones por tier, trials, regalos).

## API pública (solo lectura, JSON)

- `GET /api/games/` — partidas abiertas y en curso (filtrable con `?status=`).
- `GET /api/games/<id>/` — estado completo de una partida.
- `GET /api/leaderboard/` — ranking de jugadores.
- `GET /api/players/<username>/` — estadísticas de un jugador.

## Puesta en marcha (desarrollo)

```bash
pip install -r requirements.txt
python manage.py migrate
python manage.py runserver        # dev (HTTP + WS in-memory channel layer)
# o, para ASGI/WebSockets:
daphne config.asgi:application
```

## Deploy (Docker)

```bash
docker compose up --build
# Sirve en http://localhost:8000 con Daphne (ASGI), Redis como channel layer
# y los estáticos servidos por WhiteNoise.
```

El `docker compose` levanta **Postgres**, **Redis** y la app (Daphne). El
contenedor corre migraciones al iniciar y hace `collectstatic` en el build.
En producción configurá al menos `SECRET_KEY`, `ALLOWED_HOSTS`,
`CSRF_TRUSTED_ORIGINS`, `REDIS_URL` y las variables `POSTGRES_*`; para TLS
activá `SSL_REDIRECT=1` y `HSTS_SECONDS`. Con varios procesos web, `REDIS_URL`
es obligatorio para que el tiempo real funcione entre ellos.

Sin `POSTGRES_DB`, la app usa SQLite (ideal para desarrollo); `DATABASE_DIR`
permite ubicar el archivo SQLite en un volumen.

### Configuración (variables de entorno)

- `SECRET_KEY`, `DEBUG`, `ALLOWED_HOSTS`, `CSRF_TRUSTED_ORIGINS`
- `REDIS_URL`: si se define, usa un channel layer Redis (requiere
  `channels-redis`); si no, usa el layer en memoria (single-process).
- `SCRABBLE_DICTIONARY_DIR`: directorio con los diccionarios por idioma,
  llamados `<lang>.txt` o `<lang>.txt.gz` (una palabra por línea, UTF-8).
  Por defecto `dictionaries/`. Si falta el archivo de un idioma, la
  validación de palabras para ese idioma queda deshabilitada.

## Diccionarios

Los diccionarios viven en `dictionaries/` como archivos gzip por idioma
(`es.txt.gz`, `en.txt.gz`). Las palabras se normalizan en mayúsculas y sin
acentos (la `Ñ` se conserva). Para regenerarlos o usar otra fuente, basta con
dejar un archivo `<lang>.txt` o `<lang>.txt.gz` con una palabra por línea.

## Tests

```bash
python manage.py test
```
