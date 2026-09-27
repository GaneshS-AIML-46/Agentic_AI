# Deployment

## Local development

```bash
cp .env.example .env
docker compose up --build
```

Services: `db` (pgvector/pg16), `backend` (FastAPI :8000), `frontend` (Vite :5173).

Health check: `GET http://localhost:8000/api/v1/health`.

## Production-like (single host)

Kubernetes is out of scope for v1. Use Compose on a VM.

1. Copy `deploy/.env.prod.example` → `deploy/.env.prod`
2. Set a strong `POSTGRES_PASSWORD` and your `GEMINI_API_KEY` (or keep `LLM_PROVIDER=mock`)
3. Run:

```bash
docker compose -f docker-compose.prod.yml --env-file deploy/.env.prod up -d --build
```

Nginx listens on port 80 and proxies `/api/` to the backend and `/` to the frontend static/nginx container.

4. Smoke: `GET /api/v1/health` and submit the Product A query in the UI.

## Secrets

Never commit `.env` or `deploy/.env.prod`. Rotate `POSTGRES_PASSWORD` if it leaked. Gemini spend: rate-limit is not enabled in v1; use mock locally.

## Backup

```bash
docker compose exec db pg_dump -U supplychain supplychain > backup.sql
```

Restore with `psql` into a fresh volume.

## TLS (optional)

Put Caddy or nginx + Let’s Encrypt in front of port 80. Not required for the first deploy.

## Logs

All services log to stdout (`docker compose logs -f backend`).
