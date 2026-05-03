# Render Deployment Guide — GroundCheck Backend

This guide covers deploying the GroundCheck FastAPI backend to Render as a Web Service.
The frontend is deployed separately on Vercel.

---

## Prerequisites

- A [Render](https://render.com) account
- A [Supabase](https://supabase.com) project with a PostgreSQL database
- A [NVIDIA NIM](https://build.nvidia.com) API key (for `PIPELINE=chat`)
- A [HuggingFace](https://huggingface.co) account and token (free tier is fine)

---

## 1. Create the Render Web Service

1. In the Render dashboard, click **New → Web Service**
2. Connect your GitHub repo (`VT-Capstone-AI-Trust-Metrics`)
3. Configure the service:

| Setting | Value |
|---|---|
| **Name** | `groundcheck-backend` (or your choice) |
| **Region** | US West (Oregon) — matches Supabase pooler region |
| **Branch** | `main` |
| **Root Directory** | `backend` |
| **Runtime** | `Docker` |
| **Instance Type** | **Starter** (512MB RAM minimum — free tier will OOM) |

Render will automatically detect the `Dockerfile` in the `backend/` directory.

---

## 2. Get Your Supabase Pooler Connection Details

The direct Supabase connection string resolves to an IPv6 address that Render cannot reach. You **must** use the connection pooler.

1. Go to your Supabase project → **Project Settings → Database**
2. Scroll to **Connection Pooling**
3. Select **Session mode**
4. Copy the connection string — it will look like:
   ```
   postgresql://postgres.your-project-ref:your-password@aws-0-us-west-2.pooler.supabase.com:6543/postgres
   ```
5. Note the individual parts — you'll need them as separate env vars below:
   - **Host**: `aws-0-us-west-2.pooler.supabase.com` (region may differ)
   - **Port**: `6543` (not 5432)
   - **User**: `postgres.your-project-ref` (note the prefix)
   - **Password**: the password shown in the pooler string

> ⚠️ The pooler password may differ from your Supabase project password. Always copy it from the pooler connection string, not from Project Settings → General.

---

## 3. Set Environment Variables in Render

In your Render service, go to **Environment** and add the following variables:

### Required — Database

| Variable | Value |
|---|---|
| `DB_IP` | `aws-0-us-west-2.pooler.supabase.com` ← from pooler |
| `DB_PORT` | `6543` |
| `DB_NAME` | `postgres` |
| `DB_USER` | `postgres.your-project-ref` ← note the prefix |
| `DB_PASS` | your pooler password |

### Required — LLM Pipeline

| Variable | Value |
|---|---|
| `PIPELINE` | `chat` |
| `CHAT_BASE_URL` | `https://integrate.api.nvidia.com/v1` |
| `CHAT_API_KEY` | your NVIDIA NIM API key |
| `CHAT_MODEL` | `mistralai/mistral-medium-3.5-128b` |

### Required — HuggingFace

| Variable | Value |
|---|---|
| `HF_TOKEN` | your HuggingFace token |
| `HF_HOME` | `/tmp/hf_cache` |
| `SENTENCE_TRANSFORMERS_HOME` | `/tmp/sentence_transformers` |

> The cache path variables redirect model downloads to `/tmp` so they don't fill the container filesystem on Render.

### Optional

| Variable | Value |
|---|---|
| `ALLOWED_ORIGINS` | your Vercel frontend URL, e.g. `https://your-app.vercel.app` |
| `RATE_LIMIT` | `10/minute` (default) |

---

## 4. Deploy

Click **Deploy** (or push to `main` — Render auto-deploys on every push).

Watch the **Logs** tab. A successful deploy will show:

```
==> Build successful
==> Deploying...
Connecting to database at postgresql://...
Database initialized successfully.
INFO: Application startup complete.
==> Your service is live at https://your-service.onrender.com
```

---

## 5. Verify the Deployment

Hit the health endpoint:

```bash
curl https://your-service.onrender.com/v1/health
```

Expected response:
```json
{"status": "ok"}
```

---

## Troubleshooting

### `Network is unreachable` / IPv6 error
You are using the direct Supabase connection string instead of the pooler. Re-check Step 2 and make sure `DB_PORT=6543` and `DB_IP` is the pooler hostname.

### `password authentication failed`
The pooler uses a different password than the direct connection in some Supabase setups. Go back to **Supabase → Connection Pooling → Session mode** and copy the password directly from that connection string.

### Out of memory (OOM)
- Make sure you are on the **Starter** plan or higher (free tier is capped at 512MB and will OOM)
- Confirm `PIPELINE=chat` is set — `ollama` and `vllm` pipelines load large local models and will always OOM on Render
- HuggingFace models (`all-MiniLM-L6-v2` and `cross-encoder/nli-deberta-v3-small`) load lazily on first request — startup RAM should be low

### `No open ports detected`
The app is crashing before it can bind to port 8000, usually due to a DB connection failure or missing env var. Check the logs above the port warning for the actual error.

### Port binding
The `Dockerfile` exposes port `8000` and Render detects this automatically. No manual port configuration should be needed.

---

## Architecture Notes

| Component | Where it runs |
|---|---|
| **Frontend** (React) | Vercel |
| **Backend** (FastAPI) | Render |
| **Database** (PostgreSQL) | Supabase |
| **LLM inference** | NVIDIA NIM API (external) |
| **Embeddings / NLI** | Loaded on-demand in the Render container |
| **ChromaDB** | Ephemeral in-container (persists until redeploy) |
| **Ollama** | Local dev only — not used on Render |

> **Note on ChromaDB persistence:** Render's filesystem is ephemeral — ChromaDB data is lost on each redeploy. For production persistence, consider migrating to a hosted vector DB (e.g. Supabase pgvector, Pinecone, or a Render Persistent Disk).