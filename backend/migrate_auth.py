"""
Idempotent migration for the auth / role-based access feature. Safe to run
multiple times. Non-destructive: horse.herder_id is copied, never dropped.

  1. user:         add role, phone, contact_id, trainer_id columns
  2. user.phone:   add UNIQUE index (NULLs allowed — SQLite treats them distinct)
  3. horse_herder: create junction table
  4. backfill:     copy existing horse.herder_id -> horse_herder rows

Usage:
    DB_PATH=../data/horse.db python3 migrate_auth.py     # local
    # on Fly:  fly ssh console ; cd /app ; python backend/migrate_auth.py
"""
import os, sqlite3

DB_PATH = os.environ.get("DB_PATH", os.path.join(os.path.dirname(__file__), "../data/horse.db"))


def cols(conn, table):
    return [r[1] for r in conn.execute(f"PRAGMA table_info({table})")]


def main():
    conn = sqlite3.connect(DB_PATH)
    changed = []

    # 1. user: add role / phone / contact_id / trainer_id (UNIQUE added separately)
    ucols = cols(conn, "user")
    for name, ddl in [
        ("role", "role TEXT DEFAULT 'guest'"),
        ("phone", "phone TEXT"),
        ("contact_id", "contact_id INTEGER"),
        ("trainer_id", "trainer_id INTEGER"),
    ]:
        if name not in ucols:
            conn.execute(f"ALTER TABLE user ADD COLUMN {ddl}")
            changed.append(f"user.{name} added")
        else:
            print(f"user.{name} already present — skip")

    # 2. UNIQUE index on user.phone (multiple NULLs allowed)
    conn.execute("CREATE UNIQUE INDEX IF NOT EXISTS idx_user_phone ON user(phone)")

    # 3. horse_herder junction table
    conn.execute("""
        CREATE TABLE IF NOT EXISTS horse_herder (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            horse_id INTEGER, herder_id INTEGER,
            start_date TEXT, end_date TEXT,
            active INTEGER DEFAULT 1
        )
    """)

    # 4. backfill horse.herder_id -> horse_herder (idempotent: skip pairs already there,
    #    non-destructive: horse.herder_id is left untouched)
    if "herder_id" in cols(conn, "horse"):
        rows = conn.execute(
            "SELECT id, herder_id FROM horse "
            "WHERE herder_id IS NOT NULL AND herder_id != ''"
        ).fetchall()
        inserted = 0
        for horse_id, herder_id in rows:
            exists = conn.execute(
                "SELECT 1 FROM horse_herder "
                "WHERE horse_id=? AND herder_id=? AND active=1",
                (horse_id, herder_id),
            ).fetchone()
            if not exists:
                conn.execute(
                    "INSERT INTO horse_herder (horse_id, herder_id, active) VALUES (?,?,1)",
                    (horse_id, herder_id),
                )
                inserted += 1
        if inserted:
            changed.append(f"horse_herder backfilled ({inserted} rows from horse.herder_id)")
        else:
            print("horse_herder: no new herder links to backfill — skip")
    else:
        print("horse.herder_id column not found — skip backfill")

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
