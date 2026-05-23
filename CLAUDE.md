# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

Argamag is an Equine Registry Management System (Адууны Бүртгэл) - a full-stack web application for managing horse breeding, training, competition records, and health tracking. The application is written in Mongolian (Монгол хэл).

## Architecture

**Backend**: FastAPI (Python) with SQLite database
- Location: `backend/`
- Main API server: `backend/main.py` (very large file: ~35k tokens, 1971+ lines)
- Database schema & initialization: `backend/database.py`
- CSV import utility: `backend/import_csv.py`

**Frontend**: Single-page application (SPA)
- Location: `frontend/`
- Main file: `frontend/index.html` (single monolithic HTML file with embedded CSS and JavaScript)
- Static uploads: `frontend/uploads/`

**Database**: SQLite
- Production DB: `data/horse.db`
- Schema includes 20+ tables for horses (aduu), herds (surg), owners (holboo), competitions (sungaa), health records (eruul_mend), training logs (mori_soikh), and more

## Development Commands

### Running the Application

```bash
# Initialize/reset database
cd backend
python3 database.py

# Start the FastAPI server (from project root)
cd backend
uvicorn main:app --reload --host 0.0.0.0 --port 8000
```

The server serves both:
- API endpoints at `http://localhost:8000/api/*`
- Frontend at `http://localhost:8000/`

### Database Operations

```bash
# Initialize fresh database
cd backend
python3 database.py

# Import CSV data (from legacy system)
cd backend
python3 import_csv.py
```

CSV files should be located in `~/Downloads/noots_data/` with filenames:
- `Potreros.csv` (herds/pastures)
- `Criadores.csv` (breeders/owners)
- `Caballos.csv` (horses)
- `Competencias.csv` (competitions)
- `Vacunas.csv` (vaccinations)

### Backup

```bash
# Run backup script (creates local + iCloud backups)
./backup.sh
```

Backups are stored in:
- Local: `$HOME/Desktop/horse/backups/`
- iCloud: `$HOME/Library/Mobile Documents/com~apple~CloudDocs/ArgamagBackup/`

### HTML Validation

```bash
# Validate HTML div tag balance before committing
python3 check_html.py frontend/index.html
```

This script checks:
- Matching `<div>` opening/closing tags
- Modal div structure integrity
- Specific checks for `#quick-modal` structure

## Database Schema Highlights

### Core Tables

- **aduu**: Main horse registry (name, ID, gender, breed, color, birth date, pedigree, chip, passport, etc.)
- **surg**: Herds/pastures where horses are kept
- **holboo**: Contacts (owners, breeders, trainers)
- **uyaach**: Trainers with specializations
- **zuchee**: Horse lineages/bloodlines

### Activity Tracking

- **mori_soikh**: Training sessions (distance, duration, temperature, wind, heart rate)
- **polar_soikh**: Detailed Polar HRM data (heart rate zones, recovery, HRV, GPS tracks)
- **sungaa**: Competition/race results
- **uraldaan**: Legacy race records (from old system)

### Health & Care

- **eruul_mend**: Health records (vaccinations, treatments, deworming, dental)
- **hemjilt**: Body measurements (weight, height, cannon bone, chest)
- **tah**: Hoof care/shoeing records
- **tejeel**: Feeding schedules
- **aie_shinjilgee**: AIE blood test results (Equine Infectious Anemia)

### Breeding

- **nokhon_urjikh**: Breeding events
- **aduu** foreign keys: `eceg_id` (sire), `eh_id` (dam) for pedigree tracking
- Legacy import IDs: `orig_id`, `orig_eceg_id`, `orig_eh_id` for data migration

### Planning & Management

- **mori_soikh_plan**: Training schedule planning
- **ajil**: Task management (status: 'todorhoi' = pending, 'duusan' = completed)
- **notification**: System notifications
- **sankhuu**: Financial records (income/expenses per horse)

## Key API Patterns

The FastAPI backend follows REST conventions:

- **GET** `/api/{resource}` - List with optional filters
- **GET** `/api/{resource}/{id}` - Get single record
- **POST** `/api/{resource}` - Create new record
- **PUT** `/api/{resource}/{id}` - Update existing record
- **DELETE** `/api/{resource}/{id}` - Delete record

### Important Filters

Most list endpoints support filtering:
- Horse list (`/api/aduu`): filter by name, ID, gender (huis), status, herd (surg_id), breed (ugshil_id), color (zus_id), owner, birth date range, chip, etc.
- Training logs (`/api/mori_soikh`): filter by horse, trainer, date range, type
- Competitions (`/api/sungaa`): filter by horse, competition type, location, date range

### Special Endpoints

- `/api/aduu/{id}/udam` - Get full pedigree tree (ancestors and descendants)
- `/api/aduu/{id}/ur_tol` - Get offspring list
- `/api/aduu/hongol_eligible` - List horses eligible for breeding retirement
- `/api/polar/import` - Import Polar training data
- `/api/dashboard/*` - Various analytics endpoints (breeding stats, age distribution, competition statistics, training trends)

## Data Model Notes

### Horse Gender (huis)
- `azarga`: Stallion
- `guu`: Mare
- `morini`: Gelding
- `unaga_er`: Male foal
- `unaga_em`: Female foal

### Status Fields
- Most tables have `idevhtei` (INTEGER, default 1): Active status flag (1=active, 0=archived)
- Horses have additional `status` field: 'idevhtei' (active) / 'hongolson' (retired) / 'eceslesen' (deceased)

### Configuration System
The `tohiruulga` table stores configurable dropdowns:
- `turul` (type): 'zus' (colors), 'ugshil' (breeds), 'senas_bie' (body markings), etc.
- `ner` (name): The actual value
- Used throughout the system for consistent dropdown values

## Frontend Architecture

`frontend/index.html` is a single-file SPA with:
- Embedded CSS (CSS variables for theming in `:root`)
- Vanilla JavaScript (no framework)
- Modal-based UI pattern for all forms and detail views
- Global state management via JavaScript variables
- Direct `fetch()` calls to backend API

**Note**: When editing `index.html`, always run `check_html.py` afterwards to verify div tag balance.

## File Locations

- Database: `data/horse.db` (production) or `backend/horse.db` (old/test)
- Uploads: `frontend/uploads/` (horse photos, documents)
- Backups: Auto-managed by `backup.sh` (keeps 30 days)
- CSV import source: `~/Downloads/noots_data/`

## Language & Terminology

All code comments, variable names, UI text, and database values are in Mongolian. Key terms:
- aduu = horse
- surg = herd
- uyaach = trainer
- ezeshigch = owner
- sungaa/uraldaan = competition/race
- naadam = festival/competition
- eruul mend = health
- mori soikh = horse training
- hongol = retirement (breeding retirement)
- unaga = foal
- eceg = father/sire
- eh = mother/dam
- udam = pedigree/lineage
