# Security

## Authentication

This API does not use request-level authentication. Access is controlled via
CORS origin allowlist and rate limiting (see below).

LLM requests to NVIDIA NIM are authenticated server-side via `CHAT_API_KEY`,
which is stored as a Render environment secret and never exposed to the client.

---

## CORS

Allowed origins are controlled by the `ALLOWED_ORIGINS` environment variable.

- **Dev (unset):** All origins permitted with a logged warning.
- **Production:** Set to your Vercel frontend URL(s) in the Render dashboard:
  ```
  ALLOWED_ORIGINS=https://your-app.vercel.app,https://staging.your-app.vercel.app
  ```

---

## Rate Limiting

The `POST /api/v1/query` endpoint is rate-limited per client IP.

Default: **10 requests/minute** — configurable via `RATE_LIMIT` in the Render
environment variables.

The real client IP is extracted from `X-Forwarded-For` set by Render's proxy
layer. This prevents clients from spoofing the header.

---

## HTTPS

TLS is terminated at **Render's edge**, which forwards plain HTTP to the
container internally. The app itself never handles raw TLS. All traffic to
your `onrender.com` URL is HTTPS by default with no additional configuration.

---

## Security Headers

The following headers are set by nginx on all responses:

| Header | Value |
|--------|-------|
| `X-Content-Type-Options` | `nosniff` |
| `X-Frame-Options` | `DENY` |
| `X-XSS-Protection` | `1; mode=block` |
| `Referrer-Policy` | `strict-origin-when-cross-origin` |

---

## Secrets Management

- All secrets are set as **Render environment variables** in the dashboard — never committed to git
- The `.env.example` file documents all required variables with placeholder values only
- Local development uses a `.env` file (listed in `.gitignore`)

Required Render environment variables for deployment:

| Variable | Description |
|----------|-------------|
| `CHAT_API_KEY` | NVIDIA NIM API key (get from build.nvidia.com) |
| `CHAT_BASE_URL` | NVIDIA NIM endpoint (default: `https://integrate.api.nvidia.com/v1`) |
| `CHAT_MODEL` | Model name to use |
| `DB_IP` | Supabase database host |
| `DB_PASS` | Supabase database password |
| `ALLOWED_ORIGINS` | Comma-separated list of allowed frontend origins |

Required GitHub Secrets for CI/CD:

| Secret | Description |
|--------|-------------|
| `RENDER_DEPLOY_HOOK_URL` | Render deploy hook URL (from service Settings tab) |
