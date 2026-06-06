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

- **Lobby / emparejamiento**: partida rápida (quick pairing), crear/unirse a
  partidas abiertas, lista de partidas en vivo.
- **Cuentas de invitado**: cualquier visitante puede jugar al instante; al
  registrarse, su rating e historial se conservan.
- **Ratings ELO**: ranking de jugadores y perfiles con estadísticas.
- **Espectar**: ver partidas en curso en vivo (los atriles rivales nunca se
  envían a oponentes ni espectadores).
- **Tiempo real**: tablero, marcador, registro de jugadas y chat por WebSocket.

## Puesta en marcha

```bash
pip install -r requirements.txt
python manage.py migrate
python manage.py runserver        # dev (HTTP + WS in-memory channel layer)
# o, para ASGI/WebSockets en producción:
daphne config.asgi:application
```

### Configuración (variables de entorno)

- `SECRET_KEY`, `DEBUG`, `ALLOWED_HOSTS`, `CSRF_TRUSTED_ORIGINS`
- `REDIS_URL`: si se define, usa un channel layer Redis (requiere
  `channels-redis`); si no, usa el layer en memoria (single-process).
- `SCRABBLE_DICTIONARY_PATH`: ruta a una lista de palabras válidas (una por
  línea, UTF-8). Sin ella, la validación de palabras queda deshabilitada.

## Tests

```bash
python manage.py test
```
