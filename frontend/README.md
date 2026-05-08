# Frontend

Virginia Tech Capstone 2026 · Frontend 

---

## Overview

AI Trust Metrics's frontend is a React + TypeScript SPA that gives analysts a confidence-aware interface for querying enterprise knowledge bases. Each time a user submits a query, the frontend:

1. Sends the query to the backend RAG pipeline via a typed service layer
2. Renders the answer with a confidence tier badge (HIGH / MEDIUM / LOW) and collapsible source citations
3. Displays grounding and generation signal breakdowns in a live side panel
4. Persists the session and query history to localStorage (max 25 sessions / 50 history items)
5. Collects user feedback (Accept / Review / Reject + thumbs rating) and posts it back to the audit log

---

## Setup

### 1. Install dependencies

```bash
npm install
```

### 2. Configure environment

```bash
cp .env.example .env.local
```

Fill in `.env.local`:

| Variable | Default | Description |
|---|---|---|
| `VITE_API_BASE_URL` | `http://localhost:8000/api` | Backend API base URL |
| `VITE_APP_NAME` | `AI Trust Metrics` | App display name |
| `VITE_ENABLE_ANALYTICS` | `false` | Feature flag for analytics page |

### 3. Start the development server

```bash
npm run dev          # http://localhost:3000
```

The dev server proxies `/api` and `/v1` requests to `http://localhost:8000`, so the backend must be running for full functionality.

### 4. Run tests

```bash
npm run test
```

---

## Available Scripts

| Script | Description |
|---|---|
| `npm run dev` | Start Vite dev server on port 3000 with hot reload |
| `npm run build` | Production build to `dist/` |
| `npm run preview` | Preview production build locally |
| `npm run typecheck` | Run TypeScript type checking without emit |
| `npm run lint` | Run ESLint (strict — max-warnings 0) |
| `npm run lint:fix` | Run ESLint with auto-fix |
| `npm run format` | Format source files with Prettier |
| `npm run format:check` | Check formatting without writing |
| `npm run test` | Run Vitest in watch mode |
| `npm run test:ui` | Open Vitest browser UI |
| `npm run test:coverage` | Run tests with v8 coverage report |

---

## Architecture

```
User Query (ChatInterface)
    │
    ▼
┌─────────────────────────────────────────────────────────┐
│                    Service Layer                         │
│                                                         │
│  services/api.ts                                        │
│  queryService.submit() → POST /api/v1/query             │
│  feedbackService.submit() → POST /api/v1/feedback/{id}  │
│  documentsService, weightsService, metricsService       │
│                                                         │
│  api/client.ts                                          │
│  Axios instance — Bearer token, error normalisation,    │
│  3-minute timeout (Ollama latency headroom)             │
└─────────────────────────────────────────────────────────┘
    │
    ▼  (GroundCheckResponse)
┌─────────────────────────────────────────────────────────┐
│                  Presentation Layer                      │
│                                                         │
│  ChatInterface.jsx — message list + markdown rendering  │
│  RightPanel.jsx    — confidence signal breakdown        │
│  FeedbackWidget.tsx — Accept / Review / Reject + rating │
│  Analytics.jsx     — historical confidence trends       │
│  WeightConfiguration.tsx — live fusion weight editor    │
└─────────────────────────────────────────────────────────┘
    │
    ▼
┌─────────────────────────────────────────────────────────┐
│               Persistence (localStorage)                 │
│                                                         │
│  chatSessions.ts  — up to 25 sessions; custom events   │
│  queryHistory.ts  — up to 50 history items             │
│  SettingsPanel / WeightConfiguration — user prefs      │
└─────────────────────────────────────────────────────────┘
```

---

## Project Structure

```
frontend/
├── api/                          # Vercel serverless proxy functions
│   ├── v1/[...path].js           # Proxy for /v1/* backend routes
│   └── backend-v1/[...path].js   # Proxy for /api/v1/* backend routes
├── src/
│   ├── api/                      # Typed HTTP layer
│   │   ├── client.ts             # Axios instance with interceptors
│   │   ├── errors.ts             # ApiError class, retry logic
│   │   └── types.ts              # GroundCheckResponse and all API types
│   ├── assets/                   # Static images imported by components
│   ├── components/
│   │   ├── common/               # Reusable, route-agnostic components
│   │   │   ├── ErrorBoundary.tsx
│   │   │   ├── FeedbackWidget.tsx
│   │   │   ├── FeedbackWidget.test.tsx
│   │   │   ├── QueryInput.tsx
│   │   │   └── QueryInput.test.tsx
│   │   ├── dashboard/            # Dashboard-specific components
│   │   │   ├── ChatInterface.jsx
│   │   │   ├── DashboardLayout.tsx
│   │   │   ├── RightPanel.jsx
│   │   │   ├── SettingsPanel.jsx
│   │   │   ├── Sidebar.jsx
│   │   │   ├── TopBar.jsx
│   │   │   └── WeightConfiguration.tsx
│   │   └── layout/               # Page chrome
│   │       ├── Footer.tsx
│   │       ├── Header.tsx
│   │       └── Layout.tsx
│   ├── context/
│   │   └── AppContext.tsx         # Global loading / error state
│   ├── hooks/
│   │   ├── useQuery.ts            # Data-fetching + mutation hooks
│   │   └── useQuery.test.ts
│   ├── pages/                     # Route-level components
│   │   ├── Home.tsx               # Redirect → /dashboard/chat
│   │   ├── AnalystChat.jsx        # Main chat page
│   │   ├── Analytics.jsx          # Confidence trend dashboard
│   │   ├── Documents.tsx          # Document upload / management
│   │   ├── FlaggedOutputs.jsx     # Low-confidence flagged responses
│   │   └── Settings.jsx           # User settings wrapper
│   ├── services/                  # API + storage service modules
│   │   ├── api.ts                 # High-level service functions
│   │   ├── chatSessions.ts        # localStorage session manager
│   │   └── queryHistory.ts        # localStorage query history
│   ├── styles/
│   │   └── index.css              # Tailwind base imports + custom classes
│   ├── test/
│   │   └── setup.ts               # Vitest + jest-dom setup
│   ├── utils/                     # Pure helper functions
│   ├── App.tsx                    # Router config and route tree
│   ├── dashboard-jsx-modules.d.ts # Type stubs for JSX dashboard files
│   ├── main.tsx                   # React DOM entry point
│   └── vite-env.d.ts             # Vite client type declarations
├── .env.example                  # Environment variable template
├── .prettierrc                   # Prettier config (Tailwind plugin)
├── Dockerfile                    # Production Docker image
├── eslint.config.js              # ESLint flat config (JS + TS)
├── index.html                    # HTML entry point
├── nginx.conf                    # Nginx config for Docker deployment
├── postcss.config.js             # PostCSS (Tailwind + autoprefixer)
├── tailwind.config.js            # Tailwind theme (custom primary palette + Inter font)
├── tsconfig.json                 # TypeScript project references
├── tsconfig.app.json             # TypeScript config for src/
├── tsconfig.node.json            # TypeScript config for Vite config
├── vercel.json                   # Vercel routing and function config
└── vite.config.ts                # Vite + Vitest config
```

---

## File Reference

### API Layer (`src/api/`)

| File | Purpose |
|---|---|
| `api/client.ts` | Configured Axios instance. Sets 3-minute timeout (headroom for Ollama latency), attaches Bearer token from `localStorage`, unwraps response data, and normalises all errors to `ApiError`. |
| `api/types.ts` | TypeScript interfaces matching the backend's `GroundCheckResponse` v1.0.0 schema: `GroundCheckResponse`, `ConfidenceData`, `CitationModel`, `ConfidenceSignals`, `ResponseMetadata`, `FeedbackRequest`, `FeedbackResponse`, `ErrorInfo`. |
| `api/errors.ts` | `ApiError` class, type-guard `isApiError()`, `parseApiError()` normaliser, and `withRetry()` utility (exponential back-off, retries on HTTP 429/5xx). |

### Service Layer (`src/services/`)

| File | Purpose |
|---|---|
| `services/api.ts` | High-level service objects wrapping backend endpoints: `queryService.submit()` (POST `/api/v1/query`), `feedbackService.submit()` (POST `/api/v1/feedback/{id}`), `documentsService` (upload / list / delete), `weightsService` (GET / PUT / DELETE `/api/v1/weights`), `metricsService`. |
| `services/chatSessions.ts` | localStorage-based chat session manager. Stores up to 25 sessions; normalises/validates records on load. Manages active session ID and fires custom DOM events when sessions change so the Sidebar re-renders reactively. |
| `services/queryHistory.ts` | localStorage-based query history (max 50 items). Persists query text, answer, confidence score, grounding/generation signal values, and timestamp. Fires update events for the Analytics page. |

### Hooks (`src/hooks/`)

| File | Purpose |
|---|---|
| `hooks/useQuery.ts` | `useQuery<T>()` — data-fetching hook with AbortController cancellation, refetch support, and `onSuccess`/`onError` callbacks. `useMutation<T>()` — POST/PUT/DELETE hook with request lifecycle (loading, error, data) management. |

### State Management (`src/context/`)

| File | Purpose |
|---|---|
| `context/AppContext.tsx` | `AppProvider` + `useAppContext` hook. Holds cross-cutting globals: `isLoading`, `setLoading`, `error`, `setError`. Wraps the app in `main.tsx`. |

### Pages (`src/pages/`)

| File | Purpose |
|---|---|
| `pages/Home.tsx` | Redirects immediately to `/dashboard/chat`. |
| `pages/AnalystChat.jsx` | Main chat interface. Manages session state, message history, and draft input. Submits queries via `queryService`, saves results to `queryHistory`, persists sessions via `chatSessions`, and passes the latest `GroundCheckResponse` to `RightPanel`. |
| `pages/Analytics.jsx` | Reads query history from localStorage and renders confidence trend charts (bar charts + stat cards: average score, query count, tier distribution). |
| `pages/Documents.tsx` | Document CRUD page. Calls `documentsService` to upload PDFs/text files and delete documents. Displays list with ingestion stats (chunk count, page count, upload date). |
| `pages/FlaggedOutputs.jsx` | Placeholder page for low-confidence / policy-flagged responses. Not yet fully implemented. |
| `pages/Settings.jsx` | Thin wrapper that renders `SettingsPanel`. |

### Components — Layout (`src/components/layout/`)

| File | Purpose |
|---|---|
| `layout/Layout.tsx` | Outer page shell. Renders `Header`, an `<Outlet>` for child route content, and `Footer`. Used by the top-level public routes. |
| `layout/Header.tsx` | Top navigation bar with the "AI Trust Metrics" logo and primary nav links. |
| `layout/Footer.tsx` | Simple copyright footer. |

### Components — Common (`src/components/common/`)

| File | Purpose |
|---|---|
| `common/ErrorBoundary.tsx` | Class-component error boundary. Catches render errors, shows a fallback UI, and exposes a reset handler. |
| `common/QueryInput.tsx` | Controlled textarea for query input (max 4096 chars). Uses `react-hook-form` for validation. Exposes submit and clear actions. |
| `common/FeedbackWidget.tsx` | Feedback collection UI attached to a `queryId`. Decision buttons (Accept / Review / Reject), optional thumbs-up/down rating, and a free-text comment field. Prevents duplicate submissions by tracking submitted IDs in localStorage. |

### Components — Dashboard (`src/components/dashboard/`)

| File | Purpose |
|---|---|
| `dashboard/DashboardLayout.tsx` | Dashboard shell. Composes `Sidebar`, `TopBar`, and an `<Outlet>` for nested routes. Derives dynamic page title and description from the active route. |
| `dashboard/Sidebar.jsx` | Left navigation panel. Lists nav items (Chat, Analytics, Documents, Settings), renders the chat session list (title + relative timestamp), provides a "New Chat" button, and supports collapse/expand toggle. |
| `dashboard/TopBar.jsx` | Top bar for dashboard pages. Shows the current page title and description on the left; user profile avatar (initials) and display name on the right. |
| `dashboard/ChatInterface.jsx` | Message list renderer. Displays user messages and assistant responses with full Markdown support (`react-markdown` + `remark-gfm`), confidence tier badges, citation pills with similarity scores, a copy-to-clipboard button, and expandable source links. |
| `dashboard/RightPanel.jsx` | Side panel for the active response. Shows the fused confidence score and tier, grounding vs. generation signal breakdown with progress bars, warning flags for degraded-mode responses, and processing metadata (latency, chunks retrieved). |
| `dashboard/SettingsPanel.jsx` | User profile editor. Fields for display name, onboarding track, experience level, aircraft focus, preferred units, and explanation style. Persists all settings to localStorage. |
| `dashboard/WeightConfiguration.tsx` | Interactive confidence weight editor. Dual sliders for grounding weight vs. generation confidence weight (must sum to 1.0). Includes Conservative / Balanced / Default presets and a live preview of the fusion formula output. Saves to the backend via `weightsService` with a localStorage fallback. |

### Root Files (`src/`)

| File | Purpose |
|---|---|
| `App.tsx` | React Router v6 route tree. Defines `/` (Home) and `/dashboard` with nested child routes: `chat` (AnalystChat), `flagged` (FlaggedOutputs), `analytics` (Analytics), `documents` (Documents), `settings` (Settings). |
| `main.tsx` | React DOM entry point. Mounts the app inside `<BrowserRouter>`, `<AppProvider>`, and `<App>`. |
| `dashboard-jsx-modules.d.ts` | Type stubs that give `.jsx` dashboard files a compatible module type for TypeScript/ESLint. |
| `vite-env.d.ts` | Augments `ImportMeta` with `VITE_*` environment variable types. |

### Vercel Serverless Proxy (`api/`)

| File | Purpose |
|---|---|
| `api/v1/[...path].js` | Catch-all Vercel function that forwards `/v1/*` requests to the backend, injecting the `BACKEND_URL` environment variable. |
| `api/backend-v1/[...path].js` | Catch-all Vercel function that forwards `/api/v1/*` requests to the backend. |

### Styling (`src/styles/`)

| File | Purpose |
|---|---|
| `styles/index.css` | Imports Tailwind's `base`, `components`, and `utilities` layers. Defines custom `.btn-primary`, `.btn-secondary`, and `.card` utility classes. |

### Tests (`src/`)

| File | What it tests |
|---|---|
| `components/common/QueryInput.test.tsx` | Renders with placeholder, validates empty submit, enforces 4096-char limit, calls `onSubmit` with trimmed value. |
| `components/common/FeedbackWidget.test.tsx` | Decision button rendering, rating display on selection, duplicate-submission prevention via localStorage, submit callback invocation. |
| `hooks/useQuery.test.ts` | `useQuery` loading/success/error state transitions, AbortController cancellation, refetch triggering. |

---

## Data Flow: Full Query Lifecycle

```
User types query → QueryInput (react-hook-form validation)
    │
    ├─ 1. AnalystChat.jsx calls queryService.submit(query)
    │       → POST /api/v1/query  { "query": "..." }
    │       → api/client.ts (Axios, Bearer token, 3-min timeout)
    │
    ├─ 2. Backend returns GroundCheckResponse JSON
    │       { query_id, query, answer, confidence, citations, metadata, status }
    │
    ├─ 3. ChatInterface.jsx renders the response
    │       → Markdown answer + confidence tier badge
    │       → Citation pills with similarity scores
    │       → Copy-to-clipboard button
    │
    ├─ 4. RightPanel.jsx renders signal breakdown
    │       → Fused score (0–100) + tier (HIGH / MEDIUM / LOW)
    │       → Grounding signal (weight 0.70) progress bar
    │       → Generation confidence signal (weight 0.30) progress bar
    │       → Degraded-mode warning if one signal failed
    │
    ├─ 5. queryHistory.ts.save(response)        → localStorage (max 50)
    │      chatSessions.ts.updateSession(...)    → localStorage (max 25)
    │
    └─ 6. FeedbackWidget renders below the answer
            → User selects Accept / Review / Reject
            → Optional thumbs rating + comment
            → feedbackService.submit(query_id, { status, rating, comment })
                → POST /api/v1/feedback/{query_id}
```

---

## Key Routes

| Path | Component | Description |
|---|---|---|
| `/` | `Home.tsx` | Redirects to `/dashboard/chat` |
| `/dashboard` | `DashboardLayout.tsx` | Dashboard shell with Sidebar and TopBar |
| `/dashboard/chat` | `AnalystChat.jsx` | Main query interface |
| `/dashboard/analytics` | `Analytics.jsx` | Confidence trend charts from query history |
| `/dashboard/documents` | `Documents.tsx` | Document upload and management |
| `/dashboard/flagged` | `FlaggedOutputs.jsx` | Flagged low-confidence outputs |
| `/dashboard/settings` | `Settings.jsx` | User profile and preferences |

---

## Confidence Display Reference

| Tier | Score Range | UI Treatment |
|---|---|---|
| HIGH | ≥ 70 | Green badge — answer well-supported |
| MEDIUM | 40 – 69 | Yellow badge — review recommended |
| LOW | < 40 | Red badge — do not act without review |

Signal breakdown shown in `RightPanel`:
- **Grounding score** — NLI-based document support (default weight 0.70)
- **Generation confidence** — token-probability mean (default weight 0.30)
- Weights are editable live in `WeightConfiguration` and persisted to the backend

---

## Deployment

The frontend is containerized (Dockerfile) and served by Nginx in production. For Vercel deployments, the `api/` directory provides serverless proxy functions that forward requests to the backend, and `vercel.json` configures routing so all non-asset paths fall through to the SPA.

---

## Dependencies (key packages)

| Package | Purpose |
|---|---|
| `react@^18.3.1` | UI library |
| `react-dom@^18.3.1` | React DOM rendering |
| `react-router-dom@^6.28.0` | Client-side routing |
| `axios@^1.7.9` | HTTP client |
| `react-hook-form@^7.72.0` | Form state management and validation |
| `react-markdown@^10.1.0` | Markdown rendering for LLM responses |
| `remark-gfm@^4.0.1` | GitHub-flavored Markdown plugin |
| `lucide-react@^0.575.0` | Icon library |
| `tailwindcss@^3.4.17` | Utility-first CSS |
| `typescript@^5.9.3` | Static typing |
| `vite@^6.0.5` | Build tool and dev server |
| `vitest@^2.1.8` | Unit test runner |
| `@testing-library/react@^16.1.0` | React component testing |
| `@testing-library/jest-dom@^6.6.3` | DOM matchers for Vitest |
| `prettier@^3.4.2` | Code formatter |
| `prettier-plugin-tailwindcss@^0.6.9` | Automatic Tailwind class sorting |
| `eslint@^9.19.0` | Linting (strict, max-warnings 0) |
