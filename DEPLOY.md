# Deploying Scrabbly

Scrabbly is a Django ASGI app (Daphne) with Postgres + Redis. The repo
`Dockerfile` builds a production image (installs gettext + DejaVu fonts,
compiles translations, collects static via WhiteNoise).

## Required environment

| Variable | Notes |
|---|---|
| `SECRET_KEY` | Long random string. |
| `DEBUG` | `0` in production. |
| `ALLOWED_HOSTS` | Comma-separated, e.g. `scrabblycloud.com,www.scrabblycloud.com`. |
| `CSRF_TRUSTED_ORIGINS` | Comma-separated `https://…` origins. |
| `POSTGRES_DB`, `POSTGRES_USER`, `POSTGRES_PASSWORD`, `POSTGRES_HOST`, `POSTGRES_PORT` | Postgres connection. |
| `REDIS_URL` | Enables the Redis channel layer + cache (needed for multi-worker WebSockets). |
| `STRIPE_SECRET_KEY`, `STRIPE_PUBLISHABLE_KEY`, `STRIPE_WEBHOOK_SECRET` | Optional; mock billing is used if unset. |
| `EMAIL_*` / `DEFAULT_FROM_EMAIL` | Optional SMTP for transactional email. |
| `PLAUSIBLE_DOMAIN` | Optional analytics. |

## Fly.io (recommended)

```bash
fly launch --no-deploy            # or use the bundled fly.toml
fly postgres create               # attach: sets POSTGRES_* / DATABASE_URL
fly redis create                  # set the connection string as REDIS_URL
fly secrets set SECRET_KEY=$(openssl rand -hex 32) \
  REDIS_URL=redis://… \
  STRIPE_SECRET_KEY=… STRIPE_WEBHOOK_SECRET=…
fly deploy
```

`release_command` in `fly.toml` runs migrations and compiles translations on
each release. WebSockets work over Fly's HTTPS proxy (the app trusts
`X-Forwarded-Proto`).

### Custom domain

```bash
fly certs add scrabblycloud.com
fly certs add www.scrabblycloud.com
```

Then point the domain's A/AAAA (or CNAME) records at Fly as instructed, and make
sure `ALLOWED_HOSTS` / `CSRF_TRUSTED_ORIGINS` include it.

## Railway / Render / any Docker host

Use the same `Dockerfile`, provision managed Postgres + Redis, set the variables
above, and run the release command (`migrate` + `compilemessages`) before
starting `daphne -b 0.0.0.0 -p 8000 config.asgi:application`.

## Stripe webhook

Point a Stripe webhook at `https://<domain>/billing/stripe/webhook/` for
`checkout.session.completed`, `invoice.paid`, `invoice.payment_failed` and
`customer.subscription.deleted`, and set `STRIPE_WEBHOOK_SECRET`.
