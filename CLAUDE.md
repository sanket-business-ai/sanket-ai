# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

SanketAI is an AI business investigator for Nepalese SMEs. It is a monorepo with a FastAPI backend plus a separate worker process (`backend/`) and a React + Vite + shadcn/ui + Tailwind v4 frontend (`frontend/`, an npm workspace of the root). The original product proposal is no longer in the repo; its loop and the deferred items are summarised in `docs/architecture.md`. Read it before you add infrastructure.

## Commands

The project needs Node 24 and Python 3.14. The virtualenv lives at the repo root in `.venv`, and all settings load from the root `.env` (run `python scripts/setup_env.py` to create it). On Linux/macOS, use `.venv/bin/python` in place of `.venv\Scripts\python.exe`.

```powershell
# Native dev: three processes
cd backend; ..\.venv\Scripts\python.exe -m alembic upgrade head
cd backend; ..\.venv\Scripts\python.exe -m uvicorn app.main:app --reload   # API on :8000, docs at /docs
cd backend; ..\.venv\Scripts\python.exe -m app.worker                      # investigation/monitor worker
npm run dev                                                                # frontend on :5173, proxies /api -> :8000

# Checks (these match CI in .github/workflows/ci.yml)
.venv\Scripts\python.exe -m pytest backend/tests -q
.venv\Scripts\python.exe -m pytest backend/tests/test_investigations.py::test_challenge_keeps_source_snapshot_after_new_upload -q
.venv\Scripts\python.exe -m ruff check backend
.venv\Scripts\python.exe -m ruff format --check backend
npm run format:check        # prettier; `npm run format` to fix
npm run build               # tsc -b + vite build (the only frontend type check)
npm run test:e2e            # Playwright; add `-- -g "<title>"` for a single test

# Docker (PostgreSQL); add -f compose.ollama.yaml to run Ollama in a container
docker compose up --build -d
```

Admin password reset: `cd backend; ..\.venv\Scripts\python.exe -m app.manage reset-password`. This revokes all sessions.

## Architecture

**Investigation pipeline.** `POST /api/investigations` (`app/main.py`) calls `jobs.enqueue`. That function snapshots the currently active source IDs onto the `Investigation` row and returns 202. The worker (`app/worker.py`, `process_one`) claims the job with an atomic UPDATE that carries a lease token, then runs `agent.investigate`, committing each tool step as it goes. The frontend polls for progress. A crashed job is re-claimable after its 30-minute lease expires, with at most 3 attempts. The lease token stops a superseded worker from overwriting the result. The API never runs investigations inline.

**Agent (`app/agent.py`) and tools (`app/analysis.py`).** The `Tools` class holds the allowlist of read-only analysis functions; `TOOL_NAMES` and the `SYSTEM` prompt must stay in sync with it. `SANKET_AGENT_MODE` selects the mode:
- `ollama`: the model plans with schema-validated JSON (`app/schemas.py`).
- `deterministic`: `fallback_conclusion` runs and no LLM is used.
- `auto`: uses Ollama and visibly falls back to deterministic.

A mandatory verification pass runs the core tools even if the planner stops early. `validate_conclusion` rejects hypotheses that cite evidence IDs which were never collected. Confidence is capped at medium. The deterministic path explains two scenarios: supplier → stockout → revenue (`supply_conclusion`), and courier/supplier price rise → contribution decline (`margin_conclusion`, which needs a measured rise and a document naming the same party). `choose_scenario` routes by question keywords, or by anomalies in discover mode. Other domains return inconclusive. This is intentional: don't make it "smarter" by inventing causes.

**Data (`app/ingestion.py`).** Uploads are validated against `CONTRACTS` plus header-optional `OPTIONAL_COLUMNS` (the column table is in README.md), normalized to a JSON snapshot, and stored as immutable, checksummed `Source` rows. Duplicate uploads reuse the existing source. New investigations use the latest source of each table type plus all documents. Challenged and completed investigations keep their original source IDs. Money is handled as `Decimal` throughout analysis, and revenue counts only orders with status `delivered` or `completed`. Comparisons are the latest 28 days against the preceding 28 days.

**Actions and monitoring (`app/actions.py`, `worker.monitor_due_actions`).** Approval is idempotent; a conflicting decision returns 409. On each idle cycle the worker checks due actions. A check requires a complete new 28-day window. If that window isn't available, the check is rescheduled for one day later. A missed KPI target enqueues a fresh investigation against the latest sources.

**Auth (`app/auth.py`).** There is a single bootstrap admin created from env vars. Sessions are opaque cookies. Every mutation needs the `X-CSRF-Token` header (`frontend/src/lib/api.ts` sends it automatically) and passes an origin check. The design is single-business, not multi-tenant.

**Schema changes.** Outside production, the API runs `Base.metadata.create_all` at startup, but Docker/production and CI run `alembic upgrade head`. Any change to a model in `app/db.py` needs a new migration in `backend/migrations/versions/`.

**Frontend.** Pages live in `src/pages/`; routing and the shell are in `App.tsx`. Data fetching uses TanStack Query over the `api`/`post` helpers in `src/lib/api.ts`. API types are hand-written in `src/lib/types.ts`, so keep them in sync with backend responses. `@/` maps to `src/`. React code should follow the vendored Vercel rules in `docs/skills/vercel-react-best-practices/`.

## Testing notes

- `backend/tests/conftest.py` forces deterministic mode and creates a fresh SQLite database per test under `.cache/test-dbs`. The `seeded` fixture loads the supply demo pack; `test_margin.py` loads the margin pack with `POST /api/demo {"pack": "margin"}`. Tests drive the worker synchronously by calling `process_one(factory)` and `monitor_due_actions(factory)`; they don't start a worker process. Model orchestration is tested by monkeypatching `agent.model_json`.
- Playwright (`frontend/playwright.config.ts`) starts `scripts/e2e-services.cjs`, which runs an isolated API and worker on port 8011 with a throwaway SQLite database in `.cache`. It also runs Vite on port 5174. It needs `.venv` to exist; set `E2E_PYTHON` to override the interpreter.
- The demo pack (`app/demo.py`, synthetic "HimalayanMart") can only be loaded into an empty workspace. Production config rejects `demo_enabled`.
