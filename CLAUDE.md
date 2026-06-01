# CLAUDE.md

Guidance for Claude Code (claude.ai/code) when working in this repository.

## Project Overview

Argamag is an Equine Registry Management System (Адууны Бүртгэл) — a full-stack web app for managing horse breeding, training, competition records, and health tracking for a family-scale operation in Mongolia.

**Important convention:** UI strings (labels, buttons, messages) are in Mongolian (Монгол хэл). Everything else — schema, identifiers, API paths, code comments — is in English. Don't translate UI strings to English. Don't leave new identifiers in Mongolian-Latin.

## Architecture

**Backend:** FastAPI (Python) with SQLite
- `backend/main.py` — one large module containing all ~114 API endpoints
- `backend/database.py` — schema definition and DB initialization
- `backend/auth.py` — bcrypt password hashing + signed-cookie sessions
- `backend/manage.py` — CLI for user management (create-user, reset-password, etc.)
- `backend/import_csv.py` — one-off legacy CSV import utility

**Frontend:** Single-file SPA
- `frontend/index.html` — entire app in one file (~7000 lines): HTML, embedded CSS, vanilla JS
- `frontend/uploads/` — user-uploaded photos and files (gitignored)
- No framework, no build step, no bundler

**Database:** SQLite
- Local: `data/horse.db`
- Production (Fly.io): `/data/horse.db` on a persistent volume
- 28 tables total

**Auth:** Session cookies signed with `itsdangerous`, 30-day sliding expiry, bcrypt password hashes. Middleware in `main.py` gates everything under `/api/*` except `/api/auth/{login,logout,me}`. The frontend shows a login overlay until `/api/auth/me` returns 200.

**Hosting:** Fly.io, region `nrt` (Tokyo). See `DEPLOY.md` for full setup. Push to `main` auto-deploys via GitHub Actions.

## Development Commands

### Run locally

```bash
# Initialize a fresh database
cd backend
python3 database.py

# Start the server (serves API + frontend on the same port)
cd backend
uvicorn main:app --reload --host 0.0.0.0 --port 8000
```

API at `http://localhost:8000/api/*`, frontend at `http://localhost:8000/`.

### User management

```bash
# Local
python3 backend/manage.py create-user <username> --full-name '<Full Name>'
python3 backend/manage.py list-users
python3 backend/manage.py reset-password <username>
python3 backend/manage.py deactivate-user <username>

# Production (TTY required — getpass needs interactive shell)
fly ssh console
cd /app
python backend/manage.py create-user ...
```

### CSV import (legacy data migration)

```bash
cd backend
python3 import_csv.py
```

Expects CSV files in `~/Downloads/noots_data/`:
- `Potreros.csv` (herds)
- `Criadores.csv` (contacts/owners)
- `Caballos.csv` (horses)
- `Competencias.csv` (races)
- `Vacunas.csv` (vaccinations)

### Backup

```bash
./backup.sh
```

Writes timestamped copies of `data/horse.db` to `~/Desktop/horse/backups/` and `~/Library/Mobile Documents/com~apple~CloudDocs/ArgamagBackup/`. Keeps 30 days.

### HTML validation

```bash
python3 check_html.py frontend/index.html
```

Always run after editing `frontend/index.html`. Validates `<div>` balance and `#quick-modal` structure.

### Deploy

```bash
fly deploy                 # manual
git push origin main       # auto via GitHub Actions
fly logs                   # tail
fly ssh console            # production shell
```

## Environment variables

| Variable | Local default | Production (Fly) | Purpose |
|---|---|---|---|
| `DB_PATH` | `../data/horse.db` | `/data/horse.db` | SQLite file |
| `UPLOADS_DIR` | `frontend/uploads` | `/data/uploads` | User upload directory |
| `SECRET_KEY` | dev fallback | Fly secret | Session cookie signing |
| `CORS_ORIGINS` | `http://localhost:8000` | `https://argamag.fly.dev` | Comma-separated allowed origins |
| `PORT` | 8000 | 8000 | Server port |

Set production secrets with `fly secrets set KEY=value`.

## Database Schema

### Core entities

- **horse** — main horse registry: name, registration_code, gender, breed, color, birth date, chip, passport, pedigree FKs, status. Self-references via `sire_id` and `dam_id` for pedigree.
- **herd** — herds/pastures where horses live
- **contact** — people: owners, breeders, vets, anyone
- **stable** — stables/barns
- **trainer** — trainers with specializations
- **horse_owner** — many-to-many: horse ↔ contact (ownership over time)
- **horse_trainer** — many-to-many: horse ↔ trainer

### Activity & performance

- **training_session** — training logs (distance, duration, temperature, wind, heart rate)
- **polar_session** — detailed Polar HRM data (zones, recovery, HRV, GPS)
- **training_plan** — scheduled training
- **training_note** — free-text notes per session
- **practice_race** — practice race results (sungaa)
- **race** — official race results (uraldaan)
- **naadam** — naadam festival events

### Health & care

- **health_record** — vaccinations, treatments, deworming, dental
- **measurement** — body measurements (weight, height, cannon bone, chest)
- **hoof_care** — shoeing and hoof maintenance
- **feeding** — feeding schedules
- **eia_test** — Equine Infectious Anemia blood tests

### Breeding & lifecycle

- **breeding_event** — breeding records
- **gelding_event** — castration events (for stallions retired to gelding)
- `horse.sire_id`, `horse.dam_id` — pedigree foreign keys back to `horse`

### Operations

- **task** — task management. `status` is `'pending'` (todorhoi) or `'done'` (duusan)
- **notification** — system notifications
- **finance_record** — income/expenses per horse
- **photo**, **attachment** — media linked to horses
- **option** — configurable dropdown values (see below)

### Auth

- **user** — `id`, `username` (unique), `password_hash` (bcrypt), `full_name`, `created_at`, `active`

### The `option` table (dropdown config)

Stores configurable dropdown values used app-wide:
- `type` (e.g. `'color'`, `'breed'`, `'body_marking'`)
- `name` — the value shown in the dropdown

When adding a new dropdown, populate via this table rather than hardcoding values.

## Data model notes

### Horse gender (`gender` field)

Stored as Mongolian-Latin enum values (UI displays Mongolian, code reads these strings):

- `azarga` — stallion
- `guu` — mare
- `morini` — gelding
- `unaga_er` — male foal
- `unaga_em` — female foal

### Horse status (`status` field)

- `active` — in service
- `retired` — retired (was `hongolson`)
- `deceased` — deceased (was `eceslesen`)

Most tables also have `active` (INTEGER, default 1) for soft-delete/archive.

### Pedigree tracking

`horse.sire_id` and `horse.dam_id` are nullable FKs to `horse.id`. Legacy import columns `orig_id`, `orig_sire_id`, `orig_dam_id` exist for matching CSV imports to internal IDs.

## API Patterns

REST conventions throughout:

- `GET /api/{resource}` — list (most support query-string filters)
- `GET /api/{resource}/{id}` — single record
- `POST /api/{resource}` — create
- `PUT /api/{resource}/{id}` — update
- `DELETE /api/{resource}/{id}` — delete

### Auth endpoints (public — not gated)

- `POST /api/auth/login` — body: `{username, password}` → sets session cookie
- `POST /api/auth/logout` — clears cookie
- `GET /api/auth/me` — returns current user or 401

### Filters worth knowing

- `/api/horses` supports: name, registration_code, gender, status, herd_id, breed_id, color_id, owner, birth date range, chip
- `/api/training_sessions` supports: horse, trainer, date range, type
- `/api/practice_races` supports: horse, race type, location, date range

### Specialized endpoints

- `/api/horses/{id}/pedigree` — full ancestor + descendant tree
- `/api/horses/gelding_eligible` — horses eligible for gelding/retirement
- `/api/polar/import` — import Polar training file
- `/api/dashboard` and `/api/dashboard/{foaling,naadam,composition,growth,age_distribution,naadam_stats,breeding_trend}` — analytics

## Frontend conventions

`frontend/index.html` is a single-file SPA:

- Embedded CSS with theme variables in `:root`
- Vanilla JS, no framework
- Modal-based UI for forms and detail views
- Global JS variables for state
- Direct `fetch()` calls via the `api()` wrapper, which sends `credentials: 'include'` and redirects to the login overlay on 401
- Login overlay (`#login-screen`) covers the app until auth succeeds; `bootApp()` runs after login
- Sidebar footer shows current user + logout link

**After every edit to `index.html`, run `python3 check_html.py frontend/index.html`.** Unbalanced divs are easy to introduce in a file this big.

## Common gotchas

- **Schema is English, UI is Mongolian.** Don't translate UI labels to English. Don't introduce new Mongolian-Latin identifiers (`aduu`, `surg`, etc.) — that's the worst of both worlds.
- **Some enum *values* are still Mongolian-Latin** (e.g. `gender` = `'azarga'`/`'guu'`/`'morini'`). These are kept as-is because they're domain-specific terms; the columns themselves are English.
- **`getpass` requires a TTY.** Use interactive `fly ssh console`, not `fly ssh console -C "..."`.
- **bcrypt 5+ has a 72-byte input limit.** `auth.py` handles this by truncating before hashing. Don't switch to passlib — it's incompatible with bcrypt 5+ (`AttributeError: module 'bcrypt' has no attribute '__about__'`).
- **CORS is strict in prod.** `allow_origins=["*"]` is gone. Update `CORS_ORIGINS` via `fly secrets set` when adding domains.
- **The `sum` column on `practice_race`.** It collides with Python's `sum()` builtin in some contexts — be careful with bulk renames or `from ... import *` patterns.

## File locations

| Path | Purpose |
|---|---|
| `data/horse.db` | Production DB (local dev + Fly volume) |
| `frontend/uploads/` | User uploads (gitignored) |
| `backend/manage.py` | User CLI |
| `Dockerfile`, `fly.toml` | Fly.io config |
| `.github/workflows/fly-deploy.yml` | Auto-deploy on push to `main` |
| `DEPLOY.md` | Full Fly.io setup guide |
| `~/Desktop/horse/backups/` | Local backups (from `backup.sh`) |
| `~/Downloads/noots_data/` | CSV source for legacy import |

## Mongolian ↔ English glossary

UI uses the Mongolian terms; code uses the English ones. Useful when reading the UI to figure out which endpoint a feature maps to.

| Mongolian | English |
|---|---|
| aduu | horse |
| surg | herd |
| uyaach | trainer |
| ezeshigch / ezen | owner |
| holboo | contact |
| sungaa | practice_race |
| uraldaan | race |
| naadam | naadam (kept) |
| eruul mend | health_record |
| mori soikh | training_session |
| hongol | gelding/retirement |
| unaga | foal |
| eceg | sire (father) |
| eh | dam (mother) |
| udam | pedigree |
| zus | color |
| ugshil | breed |
| hemjilt | measurement |
| tah | hoof_care |
| tejeel | feeding |
| ajil | task |
| sankhuu | finance |
| tohiruulga | option (settings) |
