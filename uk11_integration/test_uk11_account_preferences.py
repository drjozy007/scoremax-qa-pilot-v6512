"""Offline contract tests for isolated UK preference adapter.
Requires Flask and pytest from the existing ScoreMax environment.
Runs only with an in-memory, disposable SQLite DB; no deployments.
"""
import json
import sqlite3
import pytest
from flask import Flask
from uk11_account_preferences import create_uk11_blueprint
from uk11_preferences_migration import DDL


@pytest.fixture
def client(tmp_path):
    dbpath = tmp_path / "uk-only.db"
    c = sqlite3.connect(dbpath)
    c.execute("CREATE TABLE users(id INTEGER PRIMARY KEY, role TEXT, account_status TEXT)")
    c.executemany("INSERT INTO users VALUES(?,?,?)", [(1,"student","active"),(2,"student","active"),(3,"parent","active")])
    c.execute(DDL)
    c.commit()
    c.close()
    def db_factory():
        conn = sqlite3.connect(dbpath)
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA foreign_keys=ON")
        return conn
    app = Flask(__name__)
    app.secret_key="synthetic-uk-test-secret"
    app.config["UK11_TEST_DB_PATH"] = str(dbpath)
    app.config["UK11_BAD_PROJECTION"] = None
    schools={"school:a": {"name":"A"}, "school:b":{"name":"B"}}
    def resolver(keys,year):
        if app.config["UK11_BAD_PROJECTION"] is not None:
            return app.config["UK11_BAD_PROJECTION"]
        return {"schools":[schools[k] for k in keys], "routes":[{"key":"shared"}] if keys else [],
                "subjects":["Maths"] if keys else [],"pending":[],"evidence_revision":"synthetic-only"}
    app.register_blueprint(create_uk11_blueprint(db_factory,schools,resolver))
    app.config["TESTING"]=True
    with app.test_client() as test_client:
        yield test_client


def sign_in(client,uid,role="student"):
    with client.session_transaction() as s:
        s.clear()
        s["user_id"]=uid
        s["role"]=role


def test_requires_student_login(client):
    assert client.get("/uk11/api/me/schools").status_code==403
    sign_in(client,3,"parent")
    assert client.get("/uk11/api/me/schools").status_code==403


def test_roundtrip_and_cross_account_isolation(client):
    sign_in(client,1)
    initial=client.get("/uk11/api/me/schools").json
    assert initial["school_keys"]==[] and initial["revision"]==0
    update=client.post("/uk11/api/me/schools",json={"entry_year":2028,"school_keys":["school:a","school:b"],"revision":0})
    assert update.status_code==200
    assert update.json["revision"]==1
    assert update.json["routes"]==[{"key":"shared"}]
    sign_in(client,2)
    assert client.get("/uk11/api/me/schools").json["school_keys"]==[]
    sign_in(client,1)
    assert client.get("/uk11/api/me/schools").json["school_keys"]==["school:a","school:b"]


def test_optimistic_revision_rejects_stale_save(client):
    sign_in(client,1)
    body={"entry_year":2028,"school_keys":["school:a"],"revision":0}
    assert client.post("/uk11/api/me/schools",json=body).status_code==200
    assert client.post("/uk11/api/me/schools",json=body).status_code==409


@pytest.mark.parametrize("keys,year",[
    (["unknown"],2028), (["school:a","school:a"],2028),
    (["school:a"],"2028"), (["school:a"],2040),
    (["school:a"]*21,2028),
])
def test_invalid_requests_fail_closed(client,keys,year):
    sign_in(client,1)
    assert client.post("/uk11/api/me/schools",json={
        "entry_year":year,"school_keys":keys,"revision":0}).status_code==400


def test_legacy_session_with_missing_identity_cannot_write(client):
    sign_in(client,999)
    assert client.post("/uk11/api/me/schools",json={
        "entry_year":2028,"school_keys":[],"revision":0}).status_code==403


def test_disabled_student_is_denied(client):
    sign_in(client,1)
    with sqlite3.connect(client.application.config["UK11_TEST_DB_PATH"]) as c:
        c.execute("UPDATE users SET account_status='disabled' WHERE id=1")
    assert client.get("/uk11/api/me/schools").status_code == 403
    assert client.post("/uk11/api/me/schools",json={
        "entry_year":2028, "school_keys":["school:a"], "revision":0}).status_code == 403


@pytest.mark.parametrize("invalid_projection", [
    {"schools": [], "routes": [], "subjects": "Maths", "pending": []},
    {"schools": [], "routes": [], "subjects": ["Physics"], "pending": []},
    {"schools": [], "routes": [], "subjects": ["Maths", "Maths"], "pending": []},
])
def test_resolver_failure_does_not_write_preferences(client, invalid_projection):
    sign_in(client,1)
    client.application.config["UK11_BAD_PROJECTION"] = invalid_projection
    with pytest.raises(RuntimeError):
        client.post("/uk11/api/me/schools",json={
            "entry_year":2028, "school_keys":["school:a"], "revision":0})
    with sqlite3.connect(client.application.config["UK11_TEST_DB_PATH"]) as c:
        assert c.execute("SELECT COUNT(*) FROM uk11_student_preferences").fetchone()[0] == 0
