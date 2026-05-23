"""User admin CLI.

Usage:
    python backend/manage.py create-user <username> [--full-name "Name"]
    python backend/manage.py list-users
    python backend/manage.py reset-password <username>
    python backend/manage.py deactivate-user <username>
    python backend/manage.py reactivate-user <username>
"""
import sys, os, getpass, argparse

sys.path.insert(0, os.path.dirname(__file__))
from database import get_db, init_db
from auth import hash_password


def prompt_password() -> str:
    while True:
        p1 = getpass.getpass("Password: ")
        if len(p1) < 6:
            print("Password must be at least 6 characters.")
            continue
        p2 = getpass.getpass("Confirm: ")
        if p1 != p2:
            print("Passwords don't match. Try again.")
            continue
        return p1


def cmd_create(args):
    init_db()
    conn = get_db()
    existing = conn.execute("SELECT id FROM user WHERE username=?", (args.username,)).fetchone()
    if existing:
        print(f"User {args.username!r} already exists. Use reset-password to change password.")
        sys.exit(1)
    password = prompt_password()
    conn.execute(
        "INSERT INTO user (username, password_hash, full_name) VALUES (?, ?, ?)",
        (args.username, hash_password(password), args.full_name),
    )
    conn.commit()
    print(f"✅ Created user {args.username!r}" + (f" ({args.full_name})" if args.full_name else ""))


def cmd_list(args):
    init_db()
    conn = get_db()
    rows = conn.execute(
        "SELECT id, username, full_name, active, created_at FROM user ORDER BY id"
    ).fetchall()
    if not rows:
        print("No users. Run: python backend/manage.py create-user <username>")
        return
    print(f"{'ID':>3} {'USERNAME':20} {'FULL NAME':25} {'ACTIVE':6} {'CREATED'}")
    for r in rows:
        print(f"{r['id']:>3} {r['username']:20} {(r['full_name'] or ''):25} "
              f"{'yes' if r['active'] else 'no':6} {r['created_at']}")


def cmd_reset(args):
    init_db()
    conn = get_db()
    r = conn.execute("SELECT id FROM user WHERE username=?", (args.username,)).fetchone()
    if not r:
        print(f"User {args.username!r} not found.")
        sys.exit(1)
    password = prompt_password()
    conn.execute("UPDATE user SET password_hash=? WHERE id=?", (hash_password(password), r["id"]))
    conn.commit()
    print(f"✅ Reset password for {args.username!r}")


def cmd_deactivate(args):
    init_db()
    conn = get_db()
    cur = conn.execute("UPDATE user SET active=0 WHERE username=?", (args.username,))
    conn.commit()
    if cur.rowcount:
        print(f"✅ Deactivated {args.username!r}")
    else:
        print(f"User {args.username!r} not found.")


def cmd_reactivate(args):
    init_db()
    conn = get_db()
    cur = conn.execute("UPDATE user SET active=1 WHERE username=?", (args.username,))
    conn.commit()
    if cur.rowcount:
        print(f"✅ Reactivated {args.username!r}")
    else:
        print(f"User {args.username!r} not found.")


def main():
    parser = argparse.ArgumentParser(prog="manage.py")
    sub = parser.add_subparsers(dest="cmd", required=True)

    p_create = sub.add_parser("create-user")
    p_create.add_argument("username")
    p_create.add_argument("--full-name", default=None)
    p_create.set_defaults(func=cmd_create)

    p_list = sub.add_parser("list-users")
    p_list.set_defaults(func=cmd_list)

    p_reset = sub.add_parser("reset-password")
    p_reset.add_argument("username")
    p_reset.set_defaults(func=cmd_reset)

    p_deact = sub.add_parser("deactivate-user")
    p_deact.add_argument("username")
    p_deact.set_defaults(func=cmd_deactivate)

    p_react = sub.add_parser("reactivate-user")
    p_react.add_argument("username")
    p_react.set_defaults(func=cmd_reactivate)

    args = parser.parse_args()
    args.func(args)


if __name__ == "__main__":
    main()
