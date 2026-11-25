"""Opt-in UK11 mounting boundary for a disposable assembled native ScoreMax runtime.

This module does NOT auto-register any route. The existing ScoreMax app's
before_request security gate must remain installed and execute for these routes.
"""
from __future__ import annotations

import os
from pathlib import Path
from uk11_account_preferences import create_uk11_blueprint
from uk11_school_dashboard import create_uk11_dashboard_blueprint
from uk11_guardian_onboarding import create_uk11_guardian_blueprint

MARKER = ".uk11_disposable_qualification_runtime"


def mount_into_disposable_scoremax(app, root, db_factory, school_catalogue, route_resolver):
    """Explicitly mount in a verified disposable runtime. Never auto-migrate."""
    root = Path(root).resolve()
    if os.environ.get("SCOREMAX_UK11_DISPOSABLE_TEST_MODE") != "1":
        raise RuntimeError("UK11_TEST_ONLY_FLAG_REQUIRED")
    if not (root / MARKER).is_file():
        raise RuntimeError("UK11_DISPOSABLE_RUNTIME_MARKER_REQUIRED")
    if "uk11_account" in app.blueprints:
        raise RuntimeError("UK11_DUPLICATE_MOUNT")
    if not app.before_request_funcs.get(None):
        raise RuntimeError("UK11_NATIVE_SECURITY_GATE_NOT_FOUND")
    if not callable(db_factory) or not callable(route_resolver) or not isinstance(school_catalogue, dict):
        raise RuntimeError("UK11_MOUNT_DEPENDENCIES_MISSING")
    if any(not isinstance(k, str) or not k for k in school_catalogue):
        raise RuntimeError("UK11_INVALID_CATALOGUE_KEYS")
    app.register_blueprint(create_uk11_blueprint(db_factory, school_catalogue, route_resolver))
    app.register_blueprint(create_uk11_dashboard_blueprint())
    app.register_blueprint(create_uk11_guardian_blueprint(db_factory))
    return {"mounted": True, "test_only": True, "security_gate_reused": True, "dashboard_read_only": True}
