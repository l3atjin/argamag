"""
One-time migration: rename Mongolian-Latin schema to English on the live DB.

Idempotent — safe to re-run. Each step checks current state before applying.

Run from project root:
    python3 backend/migrate_to_english.py
"""
import sqlite3, os, sys

DB_PATH = os.path.join(os.path.dirname(__file__), "../data/horse.db")

sys.path.insert(0, os.path.dirname(__file__))
from rename_map import TABLES, COMMON_COLUMNS, COLUMNS, DATA_VALUES


def table_exists(conn, name):
    return conn.execute(
        "SELECT 1 FROM sqlite_master WHERE type='table' AND name=?", (name,)
    ).fetchone() is not None


def column_exists(conn, table, column):
    cols = [row[1] for row in conn.execute(f"PRAGMA table_info({table})").fetchall()]
    return column in cols


def rename_table_if_needed(conn, old, new):
    if table_exists(conn, old) and not table_exists(conn, new):
        conn.execute(f"ALTER TABLE {old} RENAME TO {new}")
        print(f"  ✓ table: {old} → {new}")
    elif table_exists(conn, new):
        pass  # already renamed
    else:
        print(f"  ⚠ table {old} not found, skipping")


def rename_column_if_needed(conn, table, old, new):
    if not table_exists(conn, table):
        return
    if column_exists(conn, table, old) and not column_exists(conn, table, new):
        conn.execute(f'ALTER TABLE {table} RENAME COLUMN {old} TO {new}')
        print(f"  ✓ {table}.{old} → {new}")


def migrate_data_value(conn, table, column, old_value, new_value):
    if not table_exists(conn, table) or not column_exists(conn, table, column):
        return
    cur = conn.execute(
        f"UPDATE {table} SET {column}=? WHERE {column}=?", (new_value, old_value)
    )
    if cur.rowcount:
        print(f"  ✓ {table}.{column}: {old_value!r} → {new_value!r}  ({cur.rowcount} rows)")


def main():
    print(f"Migrating: {DB_PATH}")
    if not os.path.exists(DB_PATH):
        print("DB not found — nothing to migrate.")
        return

    conn = sqlite3.connect(DB_PATH)
    conn.execute("PRAGMA foreign_keys = OFF")

    # Step 1 — rename columns BEFORE renaming tables, while old table names still apply.
    print("\n[1/3] Renaming columns...")
    for old_table, new_table in TABLES.items():
        # Common columns that apply to (almost) every table
        for col_old, col_new in COMMON_COLUMNS.items():
            # Skip the aduu_id → horse_id rename on the aduu table itself
            # (the aduu_id column on aduu is the registration code, handled below)
            if old_table == "aduu" and col_old == "aduu_id":
                continue
            rename_column_if_needed(conn, old_table, col_old, col_new)

        # Per-table specific renames
        for col_old, col_new in COLUMNS.get(old_table, {}).items():
            rename_column_if_needed(conn, old_table, col_old, col_new)

    # Step 2 — migrate data values (still using OLD table names for the lookup).
    # We apply UPDATE *after* column renames so we reference the NEW column names.
    print("\n[2/3] Migrating enum data values...")
    for (old_table, col), value_map in DATA_VALUES.items():
        # Compute the new column name in the (still old-named) table
        col_new = COLUMNS.get(old_table, {}).get(col, COMMON_COLUMNS.get(col, col))
        for old_value, new_value in value_map.items():
            migrate_data_value(conn, old_table, col_new, old_value, new_value)

    # Step 3 — rename tables (longest first so compound names like aduu_ezeshigch
    # are handled before their components).
    print("\n[3/3] Renaming tables...")
    sorted_tables = sorted(TABLES.items(), key=lambda kv: -len(kv[0]))
    for old, new in sorted_tables:
        rename_table_if_needed(conn, old, new)

    conn.commit()

    # Sanity dump
    print("\nFinal tables:")
    for row in conn.execute(
        "SELECT name FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%' ORDER BY name"
    ).fetchall():
        print(f"  {row[0]}")

    conn.close()
    print("\n✅ Migration complete.")


if __name__ == "__main__":
    main()
