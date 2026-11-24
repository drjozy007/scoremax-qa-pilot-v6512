"""Mount-boundary tests only; not an exact assembled ScoreMax runtime replay."""
import pytest
from flask import Flask
from uk11_native_mount import mount_into_disposable_scoremax


def make_app():
    a = Flask(__name__)
    a.secret_key = "disposable-only"
    return a


def test_default_disabled_even_with_marker(monkeypatch, tmp_path):
    (tmp_path / ".uk11_disposable_qualification_runtime").write_text("synthetic")
    monkeypatch.delenv("SCOREMAX_UK11_DISPOSABLE_TEST_MODE", raising=False)
    app = make_app()
    with pytest.raises(RuntimeError, match="TEST_ONLY_FLAG"):
        mount_into_disposable_scoremax(app, tmp_path, lambda: None, {}, lambda k, y: {})


def test_requires_disposable_marker(monkeypatch, tmp_path):
    monkeypatch.setenv("SCOREMAX_UK11_DISPOSABLE_TEST_MODE", "1")
    app = make_app()
    with pytest.raises(RuntimeError, match="MARKER_REQUIRED"):
        mount_into_disposable_scoremax(app, tmp_path, lambda: None, {}, lambda k, y: {})


def test_requires_native_security_gate(monkeypatch, tmp_path):
    monkeypatch.setenv("SCOREMAX_UK11_DISPOSABLE_TEST_MODE", "1")
    (tmp_path / ".uk11_disposable_qualification_runtime").write_text("synthetic")
    app = make_app()
    with pytest.raises(RuntimeError, match="SECURITY_GATE_NOT_FOUND"):
        mount_into_disposable_scoremax(app, tmp_path, lambda: None, {}, lambda k, y: {})


def test_mount_once_with_existing_guard(monkeypatch, tmp_path):
    monkeypatch.setenv("SCOREMAX_UK11_DISPOSABLE_TEST_MODE", "1")
    (tmp_path / ".uk11_disposable_qualification_runtime").write_text("synthetic")
    app = make_app()
    @app.before_request
    def example_guard():
        return None
    resolver = lambda keys, year: {"schools": [], "routes": [], "subjects": [], "pending": []}
    result = mount_into_disposable_scoremax(app, tmp_path, lambda: None, {}, resolver)
    assert result["mounted"] and result["test_only"]
    assert "uk11_account" in app.blueprints
    with pytest.raises(RuntimeError, match="DUPLICATE_MOUNT"):
        mount_into_disposable_scoremax(app, tmp_path, lambda: None, {}, resolver)
