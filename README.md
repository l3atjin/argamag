# Argamag — Адууны Бүртгэл

Equine Registry Management System. Tracks horses, breeding, training, competitions, and health records for a small family operation in Mongolia.

UI is in Mongolian. Code, schema, and identifiers are in English.

**Live:** https://argamag.fly.dev/

---

## Stack

- **Backend:** FastAPI (Python 3.11+) — `backend/main.py` is one large module with all endpoints (~114 of them).
- **Frontend:** Single `frontend/index.html` file. Vanilla JS, embedded CSS, no framework, no build step.
- **Database:** SQLite. Production DB lives at `data/horse.db` locally, `/data/horse.db` on Fly.
- **Auth:** bcrypt + signed-cookie sessions (`backend/auth.py`). Login screen overlays the app; everything under `/api/*` is gated except `/api/auth/{login,logout,me}`.
- **Hosting:** Fly.io, region `nrt` (Tokyo), persistent volume at `/data`.
- **Deploy:** push to `main` → GitHub Actions runs `flyctl deploy --remote-only`.

---

## Run locally

Requires Python 3.11+ and `pip`.

```bash
# 1. clone & enter
git clone git@github.com:l3atjin/argamag.git
cd argamag

# 2. install deps (use a venv if you like)
pip install -r requirements.txt

# 3. initialize the database (creates data/horse.db with empty tables)
cd backend
python3 database.py
cd ..

# 4. create a local user so you can log in
python3 backend/manage.py create-user batjargal --full-name 'Батжаргал'
# you'll be prompted for a password twice

# 5. start the server
cd backend
uvicorn main:app --reload --host 0.0.0.0 --port 8000
```

Open http://localhost:8000/ and log in.

### Local env vars (optional)

| Variable | Default | What it does |
|---|---|---|
| `DB_PATH` | `../data/horse.db` (relative to `backend/`) | SQLite file location |
| `UPLOADS_DIR` | `frontend/uploads` | Where uploaded photos/files go |
| `SECRET_KEY` | dev fallback | Session cookie signing key — set in production |
| `CORS_ORIGINS` | `http://localhost:8000` | Comma-separated allowed origins |

---

## Deploy

Hosted on Fly.io. Full setup and day-to-day commands are in **[DEPLOY.md](./DEPLOY.md)**.

Short version once Fly is set up:

```bash
fly deploy              # manual deploy
git push origin main    # auto-deploy via GitHub Actions
fly logs                # tail logs
fly ssh console         # shell into the production machine
```

To create user accounts on the deployed instance:

```bash
fly ssh console
cd /app
python backend/manage.py create-user <username> --full-name '<Full Name>'
```

---

## Common tasks

```bash
# Reset the local DB from scratch (destroys data — back up first!)
cd backend && python3 database.py

# Import legacy CSV data from ~/Downloads/noots_data/
cd backend && python3 import_csv.py

# Local backup (also pushes to iCloud Drive)
./backup.sh

# Verify frontend HTML before committing
python3 check_html.py frontend/index.html
```

---

## Repo layout

```
argamag/
├── backend/
│   ├── main.py              # all API endpoints (~114)
│   ├── database.py          # schema + init
│   ├── auth.py              # bcrypt + cookie sessions
│   ├── manage.py            # CLI: create-user, list-users, reset-password
│   └── import_csv.py        # one-off legacy CSV importer
├── frontend/
│   ├── index.html           # the whole SPA, one file
│   └── uploads/             # user-uploaded photos/files (gitignored)
├── data/
│   └── horse.db             # SQLite (gitignored)
├── Dockerfile               # used by Fly
├── fly.toml                 # Fly app config
├── requirements.txt
├── backup.sh
├── check_html.py
├── DEPLOY.md                # Fly.io deploy guide
├── CLAUDE.md                # context for Claude Code
└── README.md                # this file
```

---

## Working with Claude Code

When you open this repo in Claude Code, it automatically reads `CLAUDE.md` for context (schema, conventions, gotchas). You generally don't need to explain the project — just describe what you want.

Some prompts that work well:

- *"Add a new field `microchip_location` to the `horse` table and surface it on the horse detail page."*
- *"The breeding trend chart on the dashboard isn't loading — find the bug."*
- *"Add a CSV export endpoint for training sessions."*
- *"Walk me through how auth works in this app."*

Two rules to remember:

1. **UI strings stay in Mongolian.** Code identifiers stay in English. Don't let Claude rename UI text to English.
2. **After editing `frontend/index.html`, run `python3 check_html.py frontend/index.html`** to catch unbalanced `<div>` tags.

---

## Backups

`./backup.sh` writes a timestamped copy of `data/horse.db` to:

- `~/Desktop/horse/backups/` (local)
- `~/Library/Mobile Documents/com~apple~CloudDocs/ArgamagBackup/` (iCloud)

It keeps the last 30 days and prunes older ones.

For the production DB on Fly, daily volume snapshots are automatic and retained for 5 days (`fly volumes snapshots list <volume-id>`).
