"""Dependency-light rectification gates for ScoreMax V6.5.12.

Closes two systemic risks found while attempting the single-learner runtime gate:
1) qa_student requests must never trigger global integration housekeeping.
2) inherited acceptance must use a central descendant comparison rather than hard-coded
   future-version allowlists (a previously observed repeated failure class).
"""
from __future__ import annotations

import ast
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from release_compatibility import is_compatible_descendant, release_tuple


def test_release_comparator_is_strict_and_future_patch_safe() -> None:
    assert release_tuple("6.5.12") == (6, 5, 12)
    assert is_compatible_descendant("6.5.12", "6.5.10") is True
    assert is_compatible_descendant("6.5.12", "6.5.12") is True
    assert is_compatible_descendant("6.5.9", "6.5.10") is False
    assert is_compatible_descendant("7.0.0", "6.5.10") is False  # major-line break must not auto-pass
    for bad in ("6.5", "v6.5.12", "6.5.12.1", "", "current"):
        try:
            release_tuple(bad)
        except ValueError:
            pass
        else:
            raise AssertionError(f"Malformed release accepted: {bad!r}")


def test_qa_housekeeping_fails_closed_before_any_global_state_work() -> None:
    source = (ROOT / "app.py").read_text(encoding="utf-8")
    tree = ast.parse(source)
    func = next(
        n for n in tree.body
        if isinstance(n, ast.FunctionDef) and n.name == "_integration_housekeeping_tick"
    )
    assert isinstance(func.body[0], ast.If), "qa_student guard must be first executable statement"
    guard = ast.unparse(func.body[0].test)
    assert "session.get('role') == 'qa_student'" in guard or 'session.get("role") == "qa_student"' in guard
    assert len(func.body[0].body) == 1 and isinstance(func.body[0].body[0], ast.Return)
    # No DB/time/global mutation may occur inside the guard before return.
    guard_text = ast.unparse(func.body[0])
    for forbidden in ("db()", "activate_due_releases", "commit", "_INTEGRATION_LAST_TICK", "time.time"):
        assert forbidden not in guard_text


def test_release_identity_and_build_name_are_new_child() -> None:
    source = (ROOT / "app.py").read_text(encoding="utf-8")
    assert "SCOREMAX_RELEASE_VERSION='6.5.12'" in source
    assert "SCOREMAX_BUILD_NAME='ScoreMax Synthetic Learner Isolation Rectification Candidate'" in source


def test_brittle_descendant_allowlists_removed_from_active_smoke_tests() -> None:
    offenders = []
    helper_users = 0
    for path in sorted(ROOT.glob("smoke_tests*.py")):
        text = path.read_text(encoding="utf-8")
        # The historical failure class was current app/integration release identity checked
        # against a manually enumerated set of future versions.
        if "SCOREMAX_RELEASE_VERSION in {" in text or "SCOREMAX_INTEGRATION_RELEASE in {" in text:
            offenders.append(path.name)
        if "['release_version'] in {" in text and "app.healthz" in text:
            offenders.append(path.name)
        if "is_compatible_descendant" in text:
            helper_users += 1
    assert not offenders, f"Brittle release allowlists remain: {sorted(set(offenders))}"
    assert helper_users >= 10, helper_users


def test_v6510_and_pilot_lineage_can_coexist_without_integration_version_forgery() -> None:
    app_source = (ROOT / "app.py").read_text(encoding="utf-8")
    integ_source = (ROOT / "scoremax_integration_v1.py").read_text(encoding="utf-8")
    assert "SCOREMAX_RELEASE_VERSION='6.5.12'" in app_source
    # Synthetic learner rectification does not change the frozen integration protocol release.
    assert "SCOREMAX_INTEGRATION_RELEASE='6.5.10'" in integ_source
    assert is_compatible_descendant("6.5.12", "6.5.10")
    assert is_compatible_descendant("6.5.10", "6.5.10")


def run_all() -> None:
    tests = [
        test_release_comparator_is_strict_and_future_patch_safe,
        test_qa_housekeeping_fails_closed_before_any_global_state_work,
        test_release_identity_and_build_name_are_new_child,
        test_brittle_descendant_allowlists_removed_from_active_smoke_tests,
        test_v6510_and_pilot_lineage_can_coexist_without_integration_version_forgery,
    ]
    for test in tests:
        test()
        print("PASS", test.__name__)
    print(f"PASS ALL {len(tests)} ScoreMax V6.5.12 dependency-light rectification tests")


if __name__ == "__main__":
    run_all()
