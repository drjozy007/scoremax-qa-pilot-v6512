"""ScoreMax V6.2.1 session-integrity hotfix regression suite."""
from __future__ import annotations

import os
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT))
from smoke_tests_v5_5 import install_framework_stubs


def main() -> None:
    flask, request = install_framework_stubs()
    temp = Path(tempfile.mkdtemp(prefix="scoremax_v621_session_"))
    os.environ["SCOREMAX_DB"] = str(temp / "scoremax.db")
    os.environ["SCOREMAX_ENV"] = "local"

    import app

    checks: list[str] = []

    def ok(name: str, condition: bool = True) -> None:
        if not condition:
            raise AssertionError(name)
        checks.append(name)
        print("PASS:", name)

    app.init()
    c = app.db()
    cur = c.execute(
        """INSERT INTO users(
             system_user_id,role,full_name,dob,email,username,password_hash,
             account_status,session_version
           ) VALUES('STU-V621-1','student','Session Student','2001-01-01',
                    'session@test','session-test',?,'active',0)""",
        (app.generate_password_hash("password123"),),
    )
    user_id = cur.lastrowid
    c.commit()
    c.close()

    # Simulate sign-in followed by the next private browser request.
    request.method = "POST"
    request.remote_addr = "127.0.0.1"
    request.form = {"email": "session@test", "password": "password123"}
    flask.session.clear()
    login_result = app.login()
    ok("login stores valid zero session version", flask.session.get("user_id") == user_id and flask.session.get("session_version") == 0)
    ok("login returns dashboard redirect", login_result == "/dashboard")

    request.method = "GET"
    request.endpoint = "dashboard"
    request.path = "/dashboard"
    request.form = {}
    request.headers = {}
    gate_result = app._v54_security_gate()
    ok("zero-version session survives the next private request", gate_result is None and flask.session.get("user_id") == user_id)

    # A valid non-zero version must also survive.
    c = app.db()
    c.execute("UPDATE users SET session_version=4 WHERE id=?", (user_id,))
    c.commit()
    c.close()
    flask.session["session_version"] = 4
    gate_result = app._v54_security_gate()
    ok("matching non-zero session version remains valid", gate_result is None and flask.session.get("user_id") == user_id)

    # A password reset / security change invalidates an old browser session.
    c = app.db()
    c.execute("UPDATE users SET session_version=5 WHERE id=?", (user_id,))
    c.commit()
    c.close()
    gate_result = app._v54_security_gate()
    ok("stale session version is invalidated", gate_result == "/login" and not flask.session.get("user_id"))

    # Missing or malformed versions are never accepted as zero.
    flask.session.clear()
    flask.session.update(user_id=user_id, role="student", full_name="Session Student")
    gate_result = app._v54_security_gate()
    ok("missing session version is invalidated", gate_result == "/login" and not flask.session.get("user_id"))

    flask.session.clear()
    flask.session.update(user_id=user_id, role="student", full_name="Session Student", session_version="invalid")
    gate_result = app._v54_security_gate()
    ok("malformed session version is invalidated", gate_result == "/login" and not flask.session.get("user_id"))

    # Disabled accounts remain blocked even when their version matches.
    c = app.db()
    c.execute("UPDATE users SET account_status='disabled',session_version=6 WHERE id=?", (user_id,))
    c.commit()
    c.close()
    flask.session.clear()
    flask.session.update(user_id=user_id, role="student", full_name="Session Student", session_version=6)
    gate_result = app._v54_security_gate()
    ok("disabled account cannot retain a valid session", gate_result == "/login" and not flask.session.get("user_id"))

    ok("session parser preserves numeric zero", app._session_version(0, -1) == 0 and app._session_version("0", -1) == 0)
    ok("session parser applies missing fallback only to missing or invalid values", app._session_version(None, -1) == -1 and app._session_version("", -1) == -1)

    print(f"\nV6.2.1 SESSION CHECKS PASSED: {len(checks)}")


if __name__ == "__main__":
    main()
