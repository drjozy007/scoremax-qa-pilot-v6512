"""Synthetic UK guardian UI contract smoke tests."""
import ast
from pathlib import Path

def test_guardian_pages_have_native_controls():
    source=Path(__file__).with_name("uk11_guardian_onboarding.py").read_text()
    ast.parse(source)
    assert '"/me/guardian-onboarding"' in source
    assert '"/guardian/home"' in source
    assert '"/guardian/students/<int:student_id>/form-decision"' in source
    assert "save_guardian_decision" in source
    assert "_csrf_token" in source

def test_uk_parent_boundary_excludes_legacy_analytics():
    source=Path(__file__).with_name("uk11_native_market_boundary.py").read_text()
    ast.parse(source)
    assert 'uk11_parent_market_route' in source
    assert 'redirect("/uk11/api/guardian/home")' in source
