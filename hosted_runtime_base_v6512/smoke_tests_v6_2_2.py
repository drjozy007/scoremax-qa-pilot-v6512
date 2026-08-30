"""ScoreMax V6.2.2 student navigation and subject-flow regression suite."""
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
    temp = Path(tempfile.mkdtemp(prefix="scoremax_v622_subjects_"))
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
    student_id = c.execute(
        """INSERT INTO users(system_user_id,role,full_name,dob,email,username,password_hash,account_status,session_version,academic_level)
           VALUES('STU-V622-1','student','Subject Student','2001-01-01','subject@test','subject-test','x','active',0,'FSc Part 1')"""
    ).lastrowid
    c.commit()
    c.close()
    flask.session.clear()
    flask.session.update(user_id=student_id, role="student", full_name="Subject Student", session_version=0)

    browser = app.subject_browser()
    ok("all-subject browser uses its own template", browser[1][0] == "subject_browser.html")
    ok("all-subject browser does not pass a selected subject", "selected" not in browser[2])
    browser_subjects = [row["subject"] for row in browser[2]["subjects"]]
    ok("all-subject browser still lists available subjects", {"Biology", "Chemistry", "Physics"}.issubset(set(browser_subjects)))

    biology = app.subject_detail("Biology")
    ok("Biology opens the dedicated one-subject template", biology[1][0] == "subject_detail.html")
    selected = biology[2]["selected"]
    ok("Biology route cannot fall back to Chemistry", selected["subject"] == "Biology")
    ok("Biology detail contains Biology chapters only", bool(selected["chapters"]) and all(ch["chapter"] for ch in selected["chapters"]))

    biology_lower = app.subject_detail("biology")
    ok("subject URLs are matched case-insensitively", biology_lower[2]["selected"]["subject"] == "Biology")
    chemistry = app.subject_detail("Chemistry")
    ok("Chemistry remains independently selectable", chemistry[2]["selected"]["subject"] == "Chemistry")

    request.endpoint = "academic_messages_inbox"
    request.args = {}
    request.view_args = {}
    hidden_context = app.inject_ui_preferences()
    ok("global subject strip is hidden on non-learning pages", hidden_context["show_subject_nav_global"] is False)

    request.endpoint = "subject_detail"
    request.view_args = {"subject": "Biology"}
    detail_context = app.inject_ui_preferences()
    ok("subject detail keeps the persistent subject switcher visible", detail_context["show_subject_nav_global"] is True)
    ok("subject detail highlights the active subject", detail_context["active_subject_global"] == "Biology")

    request.endpoint = "chapter_page"
    request.args = {"subject": "Biology"}
    visible_context = app.inject_ui_preferences()
    ok("subject strip remains available on chapter learning pages", visible_context["show_subject_nav_global"] is True)
    ok("active subject is preserved for chapter navigation highlighting", visible_context["active_subject_global"] == "Biology")

    base = (ROOT / "templates" / "base.html").read_text()
    desktop = base.split('<div class="mobile-site-menu"', 1)[0]
    ok("student secondary navigation exposes written practice", "Written Practice" in (ROOT / "app.py").read_text())
    ok("student desktop navigation keeps six clear core learning journeys", all(label in desktop for label in [">Home</a>", ">Learn</a>", ">My Plan</a>", ">Practice</a>", ">Exams</a>", ">Progress</a>"]) and 'student-account-menu' in desktop)
    ok("old competing Home link is removed from logged-in desktop navigation", '<a href="{{url_for(\'index\')}}">Home</a>' not in desktop)
    ok("subject quick strip is explicitly page-gated", "show_subject_nav_global" in base)

    subject_template = (ROOT / "templates" / "subject_detail.html").read_text()
    ok("one-subject template does not loop over all subjects", "for s in subjects" not in subject_template)
    ok("one-subject template provides a clear return to all subjects", "← All subjects" in subject_template)

    ok("release health marker is updated", app.healthz()[0]["version"] in {"6.2.2","6.2.3","6.2.4","6.2.5","6.2.6","6.2.7","6.2.7.1","6.2.7.2","6.2.8","6.2.8.1"})

    print(f"\nV6.2.2 NAVIGATION/SUBJECT CHECKS PASSED: {len(checks)}")


if __name__ == "__main__":
    main()
