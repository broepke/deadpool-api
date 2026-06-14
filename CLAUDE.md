# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## What this is

A FastAPI backend for "Deadpool," a yearly game where players draft public figures and score when their picks die. It runs as a single AWS Lambda function behind API Gateway (Mangum adapter), backed by a single DynamoDB table named `Deadpool`.

## Commands

```bash
# Install dev dependencies (full set, for local dev + tests)
pip install -r requirements-dev.txt

# Run locally (serves on http://127.0.0.1:8000, docs at /docs)
python -m src.main

# Run the test suite — must run as a module from the repo root because
# tests use package-relative imports (from ..routers import ...)
python -m pytest src/tests

# Run a single test file / test
python -m pytest src/tests/test_routers.py
python -m pytest src/tests/test_routers.py::test_name -q

# Build the manylinux deployment package and upload to the "Deadpool-app" Lambda
./utilities/deploy_lambda.sh
```

`requirements-lambda.txt` pins the runtime deps that ship to Lambda (`fastapi==0.95.2`, `pydantic==1.10.13`, `mangum`, `rapidfuzz`). **Pydantic is v1** — use v1 model APIs (`Config`, `.dict()`, validators), not v2.

## Architecture

Request flow: API Gateway → `lambda_function.lambda_handler` (Mangum, `lifespan="off"`) → `src/main.py` `app` → `LoggingMiddleware` → router → service → `DynamoDBClient`.

- **`lambda_function.py`** — the real Lambda entrypoint exports `lambda_handler`. (The README's mention of `src.main.handler` is stale; the handler is `lambda_function.lambda_handler`.)
- **`src/main.py`** — FastAPI app, CORS, global exception handler, mounts the two routers. CORS allow-list is hardcoded here for local dev + prod; API Gateway applies its own CORS via stage variables (see README).
- **`src/routers/deadpool.py`** — the bulk of the API under prefix `/api/v1/deadpool` (players, people, picks, draft order, the `/draft` action, leaderboard, profile/phone verification).
- **`src/routers/reporting.py`** — analytics endpoints under `/api/v1/deadpool/reporting`.
- **`src/services/`** — business logic split out from routers: `picks.py`, `reporting.py`, `search.py`.
- **`src/utils/dynamodb.py`** — `DynamoDBClient`, the single gateway to DynamoDB. All key construction/parsing lives here.
- **`src/utils/logging.py` + `src/middleware/logging.py`** — structured JSON logging for CloudWatch Insights (see below).

### DynamoDB single-table design (table: `Deadpool`)

All entities live in one table keyed by composite `PK`/`SK`. Full ADR in `docs/dynamodb-schema.md`. Key patterns:

| Entity | PK | SK |
|---|---|---|
| Player | `PLAYER#{player_id}` | `DETAILS` |
| Person (pickable) | `PERSON#{person_id}` | `DETAILS` |
| Draft order | `YEAR#{year}` | `ORDER#{draft_order}#PLAYER#{player_id}` |
| Player pick | `PLAYER#{player_id}` | `PICK#{year}#{person_id}` |

Conventions that matter when touching `dynamodb.py`:
- Deceased status is implicit: a Person is "deceased" iff the `DeathDate` attribute exists. There is no status field.
- "Get all people" requires a table **scan** with a filter (no GSI) — keep an eye on cost when adding people-wide reads.
- Person IDs can contain `#`, so SK parsing rejoins `parts[2:]`; a `PersonID` attribute is also stored on picks as the source of truth.
- `DynamoDBClient` methods are defensive: `batch_get_*` fall back to individual `GetItem`s, and several methods catch exceptions and return empty/partial results rather than raising. Preserve this — the frontend depends on degraded-but-200 behavior.

### Game logic to know

- **Draft (`POST /draft`)** uses fuzzy name matching (`src/utils/name_matching.py`, rapidfuzz, 0.85 threshold) to find an existing Person and to reject a duplicate pick within the current year. New people are created on draft if no match.
- **Next drafter** rotation: players with `< 20` active (alive) picks, sorted by total pick count then draft order; first one is up.
- **Scoring**: a death scores `50 + (100 - age)` (see `src/services/reporting.py`).
- Year defaults to `datetime.now().year` throughout when not passed explicitly.

### Caching

In-memory TTL cache in `src/utils/caching.py`: `reporting_cache` (5 min) and `next_drafter_cache` (30 s). This is per-Lambda-instance and ephemeral — it warms on cold start and is not shared across concurrent Lambda containers. Don't rely on it for correctness.

### Logging

Use the shared `cwlogger` (`from ..utils.logging import cwlogger, Timer`) for anything that should be queryable in CloudWatch. It emits one JSON object per line with `event_type`, `level`, `data`, and a `request_id` set per-request by `LoggingMiddleware`. New event types should follow the existing `UPPER_SNAKE` naming (`DRAFT_START`, `DB_QUERY`, ...) since `README.md` documents CloudWatch Insights queries that filter on `event_type`. Wrap timed work in `with Timer() as timer:` and log `timer.elapsed_ms`.

## 2026 migration context

The repo is mid-transition from the 2025 to 2026 season. Be aware that several parallel/transitional artifacts exist and may be partially wired in:
- `src/services/picks_improved.py` (`ImprovedPicksService`) is a fixed variant of `picks.py` with year-fallback logic — check which one a router actually imports before editing.
- Top-level `debug_*.py` / `test_picks_endpoint.py` and the `utilities/`, `hotfix/`, `patches/` directories are migration/one-off scripts, not part of the served app.
- `plans/` and `docs/` hold design docs (reporting, name matching, multi-tenancy, migration guides) worth reading before larger changes.
