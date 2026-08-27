#!/usr/bin/env python3
"""Dependency-free verifier for the V6.5.15 credential-log hygiene patch.

Usage:
    python credential_log_hygiene/verify_v6515_credential_log_hygiene.py /path/to/extracted/v6515

This verifier does not import Flask or start ScoreMax. It verifies exact post-patch
file hashes, Python syntax, and rejects known credential/token log patterns. A
separate real-runtime/Render qualification remains mandatory before production
authorization is cleared.
"""
from __future__ import annotations

import ast
import hashlib
import json
from pathlib import Path
import sys

EXPECTED = {
    "app.py": "bd1b6703b8cc0f26588a2236a1451acffb081655e975c08490ddfbbc2e560c21",
    "qa_synthetic_learner.py": "7cca387fd48b42cb21c20c98acb666027acea55a054cd898dce7d489dbccd4b6",
    "provision_qa_synthetic_learners_v6_5_11.py": "e4a165458306e533f094e49983dbc80ac6063728bf5577106d71a98bb1aa912a",
}
SENSITIVE_RUNTIME_NAMES = {
    "bootstrap", "reset_url", "plaintext", "password", "deterministic_password",
    "visual_password", "raw", "token",
}


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def fail(message: str) -> None:
    raise SystemExit("FAIL: " + message)


def main() -> int:
    if len(sys.argv) != 2:
        fail("expected one extracted ScoreMax root path")
    root = Path(sys.argv[1]).resolve()
    sources: dict[str, str] = {}
    for name, expected in EXPECTED.items():
        path = root / name
        if not path.is_file():
            fail(f"missing {name}")
        got = sha256(path)
        if got != expected:
            fail(f"hash mismatch {name}: {got} != {expected}")
        text = path.read_text(encoding="utf-8")
        ast.parse(text)
        sources[name] = text

    app = sources["app.py"]
    qa = sources["qa_synthetic_learner.py"]
    provision = sources["provision_qa_synthetic_learners_v6_5_11.py"]

    prohibited = {
        "app.py": [
            "One-time bootstrap admin created: admin /",
            "New one-time local password: admin /",
            "Local password reset URL:",
        ],
        "qa_synthetic_learner.py": ['"password": plaintext'],
        "provision_qa_synthetic_learners_v6_5_11.py": ["generated credentials are printed"],
    }
    for name, patterns in prohibited.items():
        for pattern in patterns:
            if pattern in sources[name]:
                fail(f"prohibited credential-log pattern remains in {name}: {pattern}")

    if "SCOREMAX_BOOTSTRAP_ADMIN_PASSWORD must be configured" not in app:
        fail("bootstrap admin is not fail-closed on missing secret")
    if "SCOREMAX_LOCAL_RESET_OUTBOX" not in app:
        fail("protected local reset outbox/suppression control is missing")
    if "credential_supplied" not in qa:
        fail("QA provision result does not expose safe credential metadata")
    if "SCOREMAX_QA_DETERMINISTIC_PASSWORD" not in provision or "SCOREMAX_QA_VISUAL_PASSWORD" not in provision:
        fail("QA provisioning no longer requires both configured secrets")

    # Reject print() calls that reference secret-bearing runtime variable names.
    for name, source in sources.items():
        tree = ast.parse(source)
        for node in ast.walk(tree):
            if not (isinstance(node, ast.Call) and isinstance(node.func, ast.Name) and node.func.id == "print"):
                continue
            referenced = {
                n.id
                for arg in node.args
                for n in ast.walk(arg)
                if isinstance(n, ast.Name)
            }
            leaked = sorted(referenced & SENSITIVE_RUNTIME_NAMES)
            if leaked:
                fail(f"{name}:{node.lineno} print() references sensitive runtime variables: {leaked}")

    print(json.dumps({
        "status": "PASS",
        "files": EXPECTED,
        "plaintext_admin_password_logged": False,
        "plaintext_qa_password_returned_or_logged": False,
        "reset_token_logged": False,
        "scope": "dependency-free static/source gate; real runtime logging gate still required",
    }, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
