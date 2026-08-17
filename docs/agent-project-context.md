
# Agent Project Context

## Source of truth

- Read this file, `docs/phase-1-security-summary.md`, and the latest applicable `docs/phase-*-summary.md` or `docs/phase-*-progress.md` before changing code.
- Verify all handoff claims against the current source, tests, `git status`, and `git diff`; source code wins if they conflict.
- Preserve existing uncommitted changes. Do not commit, push, deploy, reset, or delete data unless the task explicitly authorizes it.

## Architecture

- `frontend/`: React 19 + Vite client; main UI and API calls live in `frontend/src/App.jsx`.
- `backend/`: FastAPI API with async MongoDB access through Motor.
- `backend/app/main.py`: application lifecycle, middleware, endpoints, and exception handling (legacy concentration point; refactor incrementally).
- `backend/app/models.py`: Pydantic request/response schemas and validation.
- `backend/app/auth.py`: bcrypt password handling and JWT authentication.
- `backend/app/database.py`: MongoDB connection lifecycle and database access.
- `backend/app/agent/`: LangGraph/Hugging Face task assistant.
- `backend/app/scheduler.py`: deadline-reminder scheduler.

## Security invariants

- Keep secrets exclusively in environment variables; never log or return passwords, JWTs, OAuth tokens, Hugging Face tokens, SMTP credentials, or raw provider exceptions.
- Keep production config fail-fast and preserve the explicit CORS allowlist; never restore a wildcard CORS regex with credentials.
- Keep development demo login behind `VITE_DEV_DEMO_ENABLED === 'true'`; it must be absent from production paths.
- Preserve authentication, ownership checks, Pydantic validation, and rate limiting added in Phase 1.
- Scope every user-owned MongoDB read/write/delete query by the authenticated `user_id`.

## Data and API conventions

- Existing REST routes use the `/api` prefix. Preserve valid client contracts unless the task explicitly calls for a documented migration.
- Treat task, chat, and user data as user-owned; do not rely on client-supplied user IDs.
- Document database migrations and backward-incompatible API changes before applying them. Never silently delete or mutate existing production data.
- Keep response errors safe for clients; use structured server logging for diagnostic detail.

## Working process

1. Inspect `git status` and relevant code/tests before editing.
2. State the files and behavior expected to change before implementation.
3. Keep the change focused on the assigned task; report blockers instead of silently expanding scope.
4. Add or update targeted tests for changed behavior.
5. Update the active phase handoff/progress document with verified changes, commands, results, migration notes, and remaining work.

## Commands

| Area | Command |
| --- | --- |
| Frontend lint | `cd frontend; npm run lint` |
| Frontend production build | `cd frontend; npm run build` |
| Frontend development server | `cd frontend; npm run dev` |
| Backend tests | `cd backend; .\venv\Scripts\pytest -v` |
| Backend development server | `cd backend; .\venv\Scripts\uvicorn app.main:app --reload --host 0.0.0.0 --port 8000` |

## Delivery format

- Report changed files, observable behavior, tests run and their results, configuration/migration requirements, and unresolved risks.
- Do not state that work is complete without code or test evidence.
