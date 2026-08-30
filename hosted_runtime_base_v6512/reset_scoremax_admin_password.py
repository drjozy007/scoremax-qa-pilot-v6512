from __future__ import annotations

import getpass
import os
import shutil
import sqlite3
import sys
from datetime import datetime
from pathlib import Path

try:
    from werkzeug.security import generate_password_hash
except ImportError:
    print("Werkzeug is not installed. Run this utility inside the extracted ScoreMax folder.")
    input("Press Enter to close...")
    raise SystemExit(1)

BASE = Path(__file__).resolve().parent
DB = Path(os.environ.get("SCOREMAX_DB", BASE / "scoremax_v4.db"))

def fail(message: str) -> None:
    print(f"\nERROR: {message}")
    input("\nPress Enter to close...")
    raise SystemExit(1)

if not DB.exists():
    fail(
        f"The ScoreMax database was not found at: {DB}\n"
        "For the standard extracted/local installation, place these utility files beside app.py. "
        "For a custom local database, set SCOREMAX_DB before running the utility."
    )

print("ScoreMax Admin Password Reset")
print("=============================")
print(f"Database: {DB}")

new_password = getpass.getpass("\nEnter a new Admin password: ")
confirm = getpass.getpass("Confirm the new Admin password: ")

if new_password != confirm:
    fail("The passwords did not match.")

if len(new_password) < 10:
    fail("Use a password of at least 10 characters.")

backup = DB.with_name(
    f"{DB.stem}_before_admin_password_reset_{datetime.now():%Y%m%d_%H%M%S}{DB.suffix}"
)
shutil.copy2(DB, backup)

connection = sqlite3.connect(DB)
try:
    connection.row_factory = sqlite3.Row
    admin = connection.execute(
        """
        SELECT id, username, system_user_id, role
        FROM users
        WHERE role='admin' AND lower(username)='admin'
        LIMIT 1
        """
    ).fetchone()

    if not admin:
        fail("The existing Platform Admin account was not found. No database changes were made.")

    columns = {
        row[1] for row in connection.execute("PRAGMA table_info(users)").fetchall()
    }

    assignments = ["password_hash=?"]
    values = [generate_password_hash(new_password)]

    if "session_version" in columns:
        assignments.append("session_version=COALESCE(session_version,0)+1")
    if "account_status" in columns:
        assignments.append("account_status='active'")

    values.append(admin["id"])
    connection.execute(
        f"UPDATE users SET {', '.join(assignments)} WHERE id=?",
        values,
    )
    connection.commit()

    integrity = connection.execute("PRAGMA integrity_check").fetchone()[0]
    if integrity != "ok":
        raise RuntimeError(f"SQLite integrity check returned: {integrity}")

finally:
    connection.close()

print("\nAdmin password reset successfully.")
print(f"Backup created: {backup.name}")
print("\nLog in with either:")
print("  Username: admin")
print("  User ID:  ADM-000001")
print("  Password: the new password you just entered")
print("\nAll existing Admin sessions were invalidated where session-version support is available.")
input("\nPress Enter to close...")
