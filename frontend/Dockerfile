# ── Frontend Dockerfile (multi-stage) ────────────────────────────────────
#
# Stage 1 — builder
#   Installs dependencies with `npm ci` (deterministic, uses package-lock.json)
#   and produces a production build in /app/dist.
#
# Stage 2 — runtime
#   Copies the static build into a minimal nginx image.
#   nginx.conf proxies /api and /v1 to the backend container and handles
#   React Router's client-side navigation.

# ── Stage 1: Build ────────────────────────────────────────────────────────
FROM node:20-alpine AS builder

WORKDIR /app

# Copy manifests first for better layer caching
COPY package.json package-lock.json ./

RUN npm ci --prefer-offline

# Copy source
COPY . .

# Build args let docker-compose inject the backend URL at build time.
# VITE_ prefix makes it available in the browser bundle.
ARG VITE_API_BASE_URL=http://localhost:8000
ARG VITE_APP_NAME="AI Trust Metrics"
ENV VITE_API_BASE_URL=$VITE_API_BASE_URL
ENV VITE_APP_NAME=$VITE_APP_NAME

RUN npm run build

# ── Stage 2: Runtime ──────────────────────────────────────────────────────
FROM nginx:1.27-alpine

# Remove default nginx config
RUN rm /etc/nginx/conf.d/default.conf

# Proxy config (routes /api and /v1 to backend, handles SPA routing)
COPY nginx.conf /etc/nginx/conf.d/default.conf

# Static build output
COPY --from=builder /app/dist /usr/share/nginx/html

EXPOSE 80

HEALTHCHECK --interval=30s --timeout=5s --retries=3 \
    CMD wget -qO- http://localhost:80/ || exit 1

CMD ["nginx", "-g", "daemon off;"]
