"""
Idempotent migration to reconcile a partially-migrated live DB with the clean
English schema in database.py. Safe to run multiple times.

  1. herd:      add missing `stallion_id` column (lead-stallion feature)
  2. hoof_care: rename leftover `dараагийн_ognoo` (half-Cyrillic) -> `next_date`

Usage:
    DB_PATH=../data/horse.db python3 migrate_colfix.py     # local
    # on Fly:  fly ssh console ; cd /app ; python backend/migrate_colfix.py
"""
import os, sqlite3

DB_PATH = os.environ.get("DB_PATH", os.path.join(os.path.dirname(__file__), "../data/horse.db"))


def cols(conn, table):
    return [r[1] for r in conn.execute(f"PRAGMA table_info({table})")]


def main():
    conn = sqlite3.connect(DB_PATH)
    changed = []

    # 1. herd.stallion_id
    if "stallion_id" not in cols(conn, "herd"):
        conn.execute("ALTER TABLE herd ADD COLUMN stallion_id INTEGER")
        changed.append("herd.stallion_id added")
    else:
        print("herd.stallion_id already present — skip")

    # 2. hoof_care.dараагийн_ognoo -> next_date
    hc = cols(conn, "hoof_care")
    if "next_date" in hc:
        print("hoof_care.next_date already present — skip")
    elif "dараагийн_ognoo" in hc:
        conn.execute('ALTER TABLE hoof_care RENAME COLUMN "dараагийн_ognoo" TO next_date')
        changed.append("hoof_care.dараагийн_ognoo -> next_date")
    else:
        print("hoof_care: neither next_date nor legacy column found — skip")

    conn.commit()
    conn.close()

    if changed:
        print("Migration applied:")
        for c in changed:
            print("  -", c)
    else:
        print("Nothing to do — DB already up to date.")


if __name__ == "__main__":
    main()
