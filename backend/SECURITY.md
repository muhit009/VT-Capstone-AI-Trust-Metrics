# Security

## Authentication

This API uses **Bearer token authentication** via the `Authorization` header.

Every request to protected endpoints must include:

```
Authorization: Bearer <your-api-key>
```

**Generating a key:**
```bash
python -c "import secrets; print(secrets.token_urlsafe(32))"
```

Set the output as `API_KEY` in your `.env` file (production) or as a GitHub Secret named `API_KEY` inside `DEPLOY_ENV`.

**Dev mode:** If `API_KEY` is not set in `.env`, authentication is disabled and all requests pass through. This is intentional for local development — never deploy to production without a key set.

---

## CORS

Allowed origins are controlled by the `ALLOWED_ORIGINS` environment variable.

- **Dev (unset):** All origins permitted with a logged warning.
- **Production:** Set to a comma-separated list of your actual frontend URLs:
  ```
  ALLOWED_ORIGINS=https://your-app.com,https://staging.your-app.com
  ```

---

## Rate Limiting

The `POST /api/v1/query` endpoint is rate-limited per client IP.

Default: **10 requests/minute** — configurable via `RATE_LIMIT` in `.env`.

The real client IP is extracted from `X-Forwarded-For` set by nginx (which trusts the cloud load balancer). This prevents clients from spoofing the header.

---

## HTTPS

TLS is terminated at the **cloud load balancer** (AWS ALB, GCP, etc.), which forwards plain HTTP to nginx on port 80 inside the VPC. The app itself never handles raw TLS.

The load balancer should:
- Redirect all HTTP → HTTPS (301)
- Use a valid certificate (AWS ACM, Let's Encrypt, etc.)
- Forward `X-Forwarded-Proto: https` so the app can detect the original scheme

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

- All secrets live in `.env` (never committed to git — listed in `.gitignore`)
- Production secrets are stored as **GitHub Actions Secrets** and injected at deploy time
- The `.env.example` file documents all required variables with placeholder values only

Required GitHub Secrets for deployment:

| Secret | Description |
|--------|-------------|
| `DEPLOY_HOST` | IP address of the cloud VM |
| `DEPLOY_USER` | SSH username (e.g. `ubuntu`) |
| `DEPLOY_SSH_KEY` | Contents of the private SSH key |
| `DEPLOY_ENV` | Full contents of the production `.env` file |