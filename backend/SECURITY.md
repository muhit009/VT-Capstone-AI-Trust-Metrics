# Security

## Authentication

This API does not use request-level authentication. Access is controlled via
CORS origin allowlist and rate limiting (see below).

LLM requests are authenticated server-side via `CHAT_API_KEY` (NVIDIA NIM) —
stored as a GitHub Actions secret and never exposed to the client.

---

## CORS

Allowed origins are controlled by the `ALLOWED_ORIGINS` environment variable.

- **Dev (unset):** All origins permitted with a logged warning.
- **Production:** Set to your frontend URL(s) in your ECS task definition or environment config:
  ```
  ALLOWED_ORIGINS=https://your-app.vercel.app,https://staging.your-app.vercel.app
  ```

---

## Rate Limiting

The `POST /api/v1/query` endpoint is rate-limited per client IP using `slowapi`.

Default: **10 requests/minute** — configurable via the `RATE_LIMIT` environment variable.

The real client IP is extracted from `X-Forwarded-For` set by the proxy layer. This prevents clients from spoofing the header.

---

## HTTPS

TLS should be terminated at your load balancer or reverse proxy in front of the ECS container. The app itself serves plain HTTP on port 8000 and never handles raw TLS.

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

- All secrets are stored as **GitHub Actions secrets** in the repository settings — never committed to git
- The `.env.example` file documents all required variables with placeholder values only
- Local development uses a `.env` file (listed in `.gitignore`)

---

## CI/CD Pipeline

Deployments are handled by GitHub Actions (`.github/workflows/ci.yml`) on every push to `main`. The pipeline has three jobs:

1. **Test** — runs `pytest tests/` against the backend with a stub DB config
2. **Build** — builds the Docker image and pushes it to AWS ECR (`groundcheck-backend`) with two tags: the commit SHA and `:latest`
3. **Deploy** — forces a new ECS deployment (`cluster: default`, `service: groundcheck-backend`), which pulls the new `:latest` image

Build and deploy jobs only run on pushes to `main`, not on pull requests.

Required GitHub Secrets for CI/CD:

| Secret | Description |
|--------|-------------|
| `AWS_ACCESS_KEY_ID` | IAM user access key with ECR push and ECS deploy permissions |
| `AWS_SECRET_ACCESS_KEY` | Corresponding IAM secret key |

---

## Environment Variables

Required at runtime (set in your ECS task definition):

| Variable | Description |
|----------|-------------|
| `PIPELINE` | LLM backend: `chat` (production), `vllm` (HPC), or `ollama` (local dev) |
| `CHAT_API_KEY` | NVIDIA NIM API key (required when `PIPELINE=chat`; get from build.nvidia.com) |
| `CHAT_BASE_URL` | NVIDIA NIM endpoint (default: `https://integrate.api.nvidia.com/v1`) |
| `CHAT_MODEL` | Model name to use (default: `mistralai/mistral-medium-3.5-128b`) |
| `DB_IP` | Database server hostname or IP |
| `DB_PORT` | Database port (default: `5432`) |
| `DB_NAME` | Database name (default: `postgres`) |
| `DB_USER` | Database username |
| `DB_PASS` | Database password |
| `ALLOWED_ORIGINS` | Comma-separated list of allowed frontend origins |
| `RATE_LIMIT` | Rate limit on `POST /api/v1/query` (default: `10/minute`) |

Optional environment variables:

| Variable | Description |
|----------|-------------|
| `VLLM_BASE_URL` | vLLM server URL (required when `PIPELINE=vllm`; default: `http://localhost:8000`) |
| `VLLM_MODEL` | vLLM model name (default: `mistral-small-24b`) |
| `OLLAMA_BASE_URL` | Ollama server URL (required when `PIPELINE=ollama`; default: `http://localhost:11434`) |
| `OLLAMA_MODEL` | Ollama model tag (default: `mistral:7b-instruct`) |
| `CHROMA_PERSIST_PATH` | ChromaDB persistence directory (default: `./chroma_db`) |
| `CHROMA_COLLECTION_NAME` | ChromaDB collection name (default: `document_embeddings`) |
| `HF_TOKEN` | HuggingFace token for higher rate limits on model downloads |
| `HF_HOME` | HuggingFace cache path (useful in constrained environments: `/tmp/hf_cache`) |
| `SENTENCE_TRANSFORMERS_HOME` | SentenceTransformers cache path |
