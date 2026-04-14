# AI Trust Metrics — Frontend

React + TypeScript frontend for the VT Capstone AI Trust Metrics project.

## Tech Stack

- **Vite** — build tool and dev server
- **React 18** — UI library
- **TypeScript 5** — static typing
- **React Router v6** — client-side routing
- **Context API** — global state management
- **Tailwind CSS** — utility-first styling
- **Axios** — HTTP client
- **Vitest** + **Testing Library** — unit and component testing

## Getting Started

```bash
# Install dependencies
npm install

# Copy environment template and fill in values
cp .env.example .env.local

# Start development server (http://localhost:3000)
npm run dev
```

## Available Scripts

| Script | Description |
|---|---|
| `npm run dev` | Start Vite dev server on port 3000 |
| `npm run build` | Production build to `dist/` |
| `npm run preview` | Preview production build locally |
| `npm run typecheck` | Run TypeScript type checking |
| `npm run lint` | Run ESLint |
| `npm run lint:fix` | Run ESLint and auto-fix issues |
| `npm run format` | Format source files with Prettier |
| `npm run format:check` | Check formatting without writing |
| `npm run test` | Run tests in watch mode |
| `npm run test:ui` | Open Vitest browser UI |
| `npm run test:coverage` | Run tests with coverage report |

## Project Structure

```
frontend/
├── public/               # Static assets served as-is
├── src/
│   ├── assets/           # Images, fonts, SVGs imported by components
│   ├── components/
│   │   ├── common/       # Reusable generic components (ErrorBoundary, etc.)
│   │   └── layout/       # Page chrome (Header, Footer, Layout wrapper)
│   ├── context/          # React Context providers and hooks (AppContext)
│   ├── hooks/            # Custom React hooks
│   ├── pages/            # Route-level page components
│   ├── services/         # API calls and external integrations
│   ├── styles/           # Global CSS (Tailwind base imports)
│   ├── test/             # Test setup and shared test utilities
│   ├── utils/            # Pure helper functions
│   ├── vite-env.d.ts     # Vite client type declarations
│   ├── App.tsx           # Root component with router config
│   └── main.tsx          # React DOM entry point
├── .env.example          # Environment variable template
├── eslint.config.js      # ESLint flat config (JS + TS rules)
├── .prettierrc           # Prettier config (includes Tailwind plugin)
├── tailwind.config.js    # Tailwind theme and content paths
├── tsconfig.json         # TypeScript project references
├── tsconfig.app.json     # TypeScript config for src/
├── tsconfig.node.json    # TypeScript config for Vite config
├── vite.config.ts        # Vite + Vitest config
└── index.html            # HTML entry point
```

## Tailwind CSS

Tailwind utility classes are available in all `.tsx` and `.ts` files under `src/`.

```tsx
// Example usage
<div className="flex items-center gap-4 rounded-lg bg-primary-600 p-4 text-white">
  Hello Tailwind
</div>
```

Custom theme extensions (colors, fonts, spacing) live in `tailwind.config.js` under `theme.extend`.

## Path Aliases

`@/` maps to `src/`, so you can use clean absolute imports:

```ts
import { apiClient } from '@/services/api';
import Layout from '@/components/layout/Layout';
```

## State Management

Global app state is managed via the Context API. `AppProvider` wraps the app in `main.tsx`; consume state anywhere with the `useAppContext` hook:

```ts
import { useAppContext } from '@/context/AppContext';

const { isLoading, setLoading, error, setError } = useAppContext();
```

## Environment Variables

All client-side env vars must be prefixed with `VITE_`. Copy `.env.example` to `.env.local` and populate values before running the dev server.
