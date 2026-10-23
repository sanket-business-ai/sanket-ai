# SanketAI

An autonomous AI business investigator for Nepalese SMEs: follow the evidence from an unusual change to its strongest supported explanation.

This monorepo implements the original proposal's investigation flow with **React + Vite + TypeScript + shadcn/ui + Tailwind CSS**, **FastAPI**, a durable Python worker, **PostgreSQL/SQLite**, and optional **Ollama/Qwen3** reasoning.

Included: a dashboard; question and discovery investigations; a live tool trail; competing hypotheses and counter-evidence; source-backed reports; “Challenge this conclusion”; JSON exports; validated CSV/XLSX/PDF/text ingestion; approval-gated internal tasks; scheduled KPI checks; automatic re-investigation when a target is missed; authenticated sessions; and audit history. Two synthetic HimalayanMart packs are included: a supply pack (eight datasets, four reports) and a margin pack (nine datasets, three documents).

## Run with Docker

From the repository root:

```powershell
python scripts/setup_env.py
docker compose up --build -d
```

Open **http://localhost:5173**. The initial email is `founder@sanketai.local`; the generated password is `SANKET_ADMIN_PASSWORD` in your local `.env`. The setup script preserves an existing file. Change the email/password before the first startup if desired. No default production password is supplied.

Sign in and select **Load demo evidence**, then ask “Why did our sales drop?” or select **Find what is going wrong**. Alternatively, select **Load margin demo** and ask “Revenue increased, so why is our margin falling?”. Each pack loads only into an empty workspace. The demos are explicitly synthetic; the couriers and suppliers are fictional. Actions propose internal tasks; they do not modify a real CRM or notify a team.

Use an existing host Ollama installation:

```powershell
ollama pull qwen3:8b
```

The first model download needs several GB of disk and suitable RAM. Set `SANKET_OLLAMA_MODEL` for your hardware; the model must support structured JSON responses. `auto` mode visibly falls back to deterministic analysis if the model is missing, offline, or invalid. Set `SANKET_AGENT_MODE=ollama` to require model reasoning, or `deterministic` for offline analysis.

To use a hosted OpenAI-compatible model instead of Ollama (for example Groq, Google Gemini or OpenRouter), set these in `.env` and restart the API and worker:

```
SANKET_LLM_PROVIDER=openai
SANKET_LLM_BASE_URL=https://api.groq.com/openai/v1
SANKET_LLM_API_KEY=<your key; never commit it>
SANKET_LLM_MODEL=openai/gpt-oss-120b
SANKET_LLM_REASONING_EFFORT=low
```

Investigation prompts, including business data from your sources, are then sent to that provider; check its data-use terms before uploading real data. Responses use strict JSON-schema output (set `SANKET_LLM_STRICT_SCHEMA=false` for providers that do not support it). Free tiers limit tokens per minute: SanketAI waits up to 60 seconds when the provider returns `Retry-After`, and otherwise falls back visibly to deterministic analysis. Evidence IDs in a model conclusion are validated, but numbers written in its prose are not; the margin bridge and evidence tab hold the calculated figures.

```powershell
docker compose logs -f api worker
docker compose down
```

`down` preserves the PostgreSQL volume. Do not add `--volumes` unless you intend to destroy the database.

## Native development

Requires Node 24 and Python 3.14.

```powershell
python scripts/setup_env.py
python -m venv .venv
.venv\Scripts\python.exe -m pip install -r backend/requirements-dev.txt
npm ci
```

Start the API in one terminal:

```powershell
cd backend
..\.venv\Scripts\python.exe -m alembic upgrade head
..\.venv\Scripts\python.exe -m uvicorn app.main:app --reload
```

Start the worker in a second terminal:

```powershell
cd backend
..\.venv\Scripts\python.exe -m app.worker
```

Start the frontend from the repository root in a third terminal:

```powershell
npm run dev
```

Open http://localhost:5173. API documentation is at http://127.0.0.1:8000/docs. The Vite proxy forwards `/api` to the backend; no browser API key is needed. SQLite is the native default. All settings are loaded from the root `.env`, with process environment variables taking precedence. Linux/macOS use `.venv/bin/python` instead.

Export inspectable synthetic source files if needed:

```powershell
.venv\Scripts\python.exe scripts/export_demo.py
```

For a larger, realistic test set, build the **HimalayanMart Gadgets** dataset: a year of a fictional Nepali mobile-accessories seller (about 28,000 orders across marketplace, website, Facebook & Instagram and TikTok; cash on delivery and wallets; three fictional couriers and four suppliers; the real 2025–26 festival calendar and the monsoon). It contains five scenario packs, each exported on the date its planted problem appears (cash-on-delivery refusals, a margin squeeze, an ad boost that did not pay, monsoon delays and a Dashain stockout), plus a README, data dictionary and answer key:

```powershell
.venv\Scripts\python.exe scripts/export_gadgets.py --out HimalayanMart_Gadgets_Nepal_dataset.zip
```

## Data contracts

Upload complete datasets, with matching IDs across files and ISO dates such as `2026-09-30`. All amounts are NPR and must be non-negative finite numbers. Upload at least 56 days of orders for comparable 28-day windows. Orders with `delivered` or `completed` status contribute recognized revenue; other supported values are `cancelled`, `returned`, `pending`, and `shipped`.

| Type | Required columns |
| --- | --- |
| orders | id, date, customer_id, product_id, quantity, revenue, status |
| products | id, name, category, price, cost |
| inventory | date, product_id, supplier_id, stock |
| suppliers | id, name, product_id, promised_date, received_date |
| deliveries | order_id, promised_date, delivered_date, route; optional: courier, fee |
| marketing | date, channel, spend, impressions, clicks |
| customers | id, segment, location, signup_date |
| expenses | date, category, amount |
| purchases | date, supplier_id, product_id, quantity, unit_cost |

`received_date` and `delivered_date` may be blank for pending shipments. The `courier` and `fee` delivery columns may be omitted entirely or left blank; record courier fees there, and stock purchases in `purchases`, but not again in `expenses`, or the contribution estimate counts them twice. Cost of goods uses the latest purchase `unit_cost` on or before each sale and falls back to the current catalog `cost` when no purchase exists. XLSX reads the first worksheet; dates must be ISO text and formulas must be exported as values. Documents support text PDFs, TXT, and Markdown. Scanned PDFs need OCR before uploading. Limits: 10 MB/file, 50,000 dataset rows, 100 PDF pages, and 500 document chunks. Extra table columns are ignored.

New investigations use the newest upload for each table type; older source versions remain attached to existing reports. Documents accumulate as evidence. Sources cannot be edited in place; to correct data, upload a complete corrected file. Deleting a source (the trash button on the Sources page) removes it permanently; if it was the current version, the previous version of that type becomes current again. Investigations that used the source, and their actions, are deleted with it after a confirmation that lists them, because a report cannot outlive its evidence; deletion is refused while such an investigation is still running, and every deletion is recorded in the audit trail. On the Sources page, the download button exports a dataset as CSV (the normalized snapshot SanketAI analyses) or a document as its extracted text; cells that spreadsheets would run as formulas are prefixed with an apostrophe.

**Live Google Sheets.** On the Sources page, **Connect Google Sheet** imports one tab as a dataset and checks it again daily, every 6 hours, hourly, or only when you select **Sync now**. Share the sheet as *Anyone with the link: Viewer*, keep one dataset per tab with the contract's column names in the first row, and paste the tab's link (it ends in `#gid=…`). Each sync that finds changed data stores a new source version (same validation as uploads); unchanged data adds nothing, and earlier reports keep the version they used. Anyone with the link can view such a sheet; private sheets (Google sign-in) are not supported yet. The server only fetches `docs.google.com` and Google's `*.googleusercontent.com` export hosts. Disconnecting stops syncing and keeps the imported data. Daraz and accounting-software connectors are not implemented yet.

Do not mix demo files with real datasets. Demo loading is available only in an empty workspace and can be disabled with `SANKET_DEMO_ENABLED=false`. To switch demos, use **Reset workspace** on the Workspace & audit page: it deletes all sources, investigations, actions and live connections (the audit trail and sign-in are kept), requires typing RESET, waits for running investigations, and is unavailable whenever demo loading is disabled, so never in production.

## Checks

```powershell
.venv\Scripts\python.exe -m pytest backend/tests -q
.venv\Scripts\python.exe -m ruff check backend
.venv\Scripts\python.exe -m ruff format --check backend
npm run format:check
npm run build
npx playwright install chromium
npm run test:e2e
docker compose config --quiet
```

Playwright starts isolated API/worker/frontend services on ports 8011/5174 with an expendable SQLite database in `.cache`; it never touches your configured business database. It exercises sign-in, the demo, investigation, source inspection, approval, stale-data protection, challenge, and mobile navigation. GitHub Actions runs the Python, frontend, and browser checks.

## Deployment and boundaries

This is a production-oriented **single-business foundation**, not a public multi-tenant service. Before deployment, set `SANKET_FRONTEND_ORIGIN` to the exact HTTPS origin, terminate TLS at your reverse proxy, and use:

```powershell
docker compose -f compose.yaml -f compose.production.yaml up --build -d
```

Production mode enforces secure cookies, HTTPS configuration, and disabled demo loading. Preserve the database volume, configure backups and resource limits, and pin tested image digests. Migration runs as a separate startup service. Monitor API/worker logs; `/api/health` checks the database and the workspace runtime screen shows worker heartbeat status.

To change the administrator password after bootstrap:

```powershell
cd backend
..\.venv\Scripts\python.exe -m app.manage reset-password
```

This revokes existing sessions. Changing the bootstrap environment password alone does not change an existing account.

Current boundaries: document retrieval is lexical; model reasoning is observational and can be wrong; confidence is qualitative, not a probability; the deterministic explanation covers two scenarios (supplier delay → stockout → revenue, and courier/supplier price rises → contribution) and leaves other domains inconclusive. Revenue difference is not automatically attributable loss. External CRM/email/workflow connectors, vector search, a separate MCP server, OCR, public signup, and multi-tenant access are deferred. Scheduled outcome checks need a complete newer 28-day window and do not prove action causality.

See [architecture and tradeoffs](docs/architecture.md) and the downloaded [Vercel React skill](docs/skills/vercel-react-best-practices/SKILL.md). The Vercel skill was sourced from the official repository through the [skills.sh listing](https://skills.sh/vercel-labs/agent-skills/vercel-react-best-practices); two relevant rule files are included under `docs/skills/`.

## License

SanketAI is open source under the [MIT License](LICENSE).
