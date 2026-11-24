"""UK11 student-home extension for a disposable assembled ScoreMax runtime only.

Reuses native /student Jinja template and the authenticated UK account projection.
Never changes Pakistan template bytes in the repository or mounted production code.
Not a practice/marking or mastery entitlement implementation.
"""
from pathlib import Path
from flask import current_app, session

MARKER = ".uk11_disposable_qualification_runtime"

PANEL = """
  {% if uk11_context %}
  <section class="card uk11-home-panel" id="uk11-school-context" aria-label="Your UK 11+ school preparation">
    <p class="eyebrow">MY UK 11+ SCHOOLS</p>
    <h2>Preparing for your chosen schools</h2>
    <p>School selection does not establish admission eligibility. Only evidenced test routes and subjects are shown.</p>
    <h3>Selected schools</h3>
    <ul>{% for school in uk11_context.schools %}<li>{{ school.name or school.school_name or 'School' }}</li>{% endfor %}</ul>
    <h3>Relevant examinations</h3>
    {% if uk11_context.routes %}
      <ul>{% for exam in uk11_context.routes %}<li>{{ exam.name or exam.route_name or 'Assessment route' }}
      {% if exam.evidence_status == 'SYNTHETIC_ONLY' %} — synthetic test route{% endif %}</li>{% endfor %}</ul>
    {% else %}<p>No evidenced assessment available yet.</p>{% endif %}
    <h3>Relevant subjects</h3>
    {% if uk11_context.subjects %}<ul>{% for subject in uk11_context.subjects %}<li>{{ subject }}</li>{% endfor %}</ul>
    {% else %}<p>Subject requirements are pending verification.</p>{% endif %}
    {% if uk11_context.pending %}
      <p role="status">Admissions verification pending for {{ uk11_context.pending|length }} selection(s). No unverified subjects have been added.</p>
    {% endif %}
    <h3>Your six mastery levels</h3>
    <p>Foundation · Exam Ready · Advanced · Distinction · Expert · Elite</p>
    <p><strong>Current UK 11+ status: Not Yet Established</strong></p>
    <p>No question allocation, mock, marks or level are claimed in this qualification view.</p>
    <p><a href="{{ url_for('uk11_school_dashboard.uk11_my_learning') }}">Review your school-specific learning context</a></p>
  </section>
  {% endif %}
"""


def install_disposable_student_home(root, app):
    root = Path(root).resolve()
    if not (root / MARKER).is_file():
        raise RuntimeError("UK11_STUDENT_HOME_DISPOSABLE_MARKER_REQUIRED")
    if "uk11_account.get_schools" not in app.view_functions:
        raise RuntimeError("UK11_ACCOUNT_PROJECTION_REQUIRED")
    if app.jinja_env.globals.get("uk11_home_context") is not None:
        raise RuntimeError("UK11_STUDENT_HOME_ALREADY_INSTALLED")

    template = root / "templates" / "student.html"
    source = template.read_text(encoding="utf-8")
    if "uk11-school-context" in source:
        raise RuntimeError("UK11_STUDENT_HOME_TEMPLATE_ALREADY_PATCHED")
    root_anchor = '<section class="student-home-v2">'
    mastery_anchor = '<article class="mastery-hero-card '
    sections = (
        ('<section class="home-priority-grid">', '<section class="home-section">'),
        ('<section class="home-section">', '<section class="home-two-column">'),
        ('<section class="home-two-column">', '{% if daily_spark and daily_spark.available %}')
    )
    if source.count(root_anchor) != 1 or source.count(mastery_anchor) != 1:
        raise RuntimeError("UK11_STUDENT_HOME_ANCHOR_DRIFT")
    if any(source.count(begin) != 1 or source.count(end) != 1 for begin, end in sections):
        raise RuntimeError("UK11_STUDENT_HOME_SECTION_ANCHOR_DRIFT")

    # Preserve native greeting, navigation and all other baseline structures.
    revised = source.replace(
        root_anchor,
        root_anchor + "\n{% set uk11_context = uk11_home_context() %}" + PANEL, 1
    )
    index = revised.index(mastery_anchor)
    end = revised.index("</article>", index) + len("</article>")
    revised = revised[:index] + "{% if not uk11_context %}\n" + revised[index:end] + "\n{% endif %}" + revised[end:]
    # Prevent unqualified Pakistan programme subjects, plans and exam links
    # appearing in the UK context; retain them unchanged for Pakistan users.
    for begin, after in sections:
        start = revised.index(begin)
        finish = revised.index(after, start)
        revised = revised[:start] + "{% if not uk11_context %}\n" + revised[start:finish] + "{% endif %}\n" + revised[finish:]
    try:
        app.jinja_env.from_string(revised)
    except Exception as exc:
        raise RuntimeError("UK11_STUDENT_HOME_JINJA_INVALID") from exc

    def school_context():
        if session.get("role") != "student" or not isinstance(session.get("user_id"), int):
            return None
        response = current_app.view_functions["uk11_account.get_schools"]()
        if response.status_code != 200:
            return None
        data = response.get_json()
        return data if data.get("school_keys") else None

    original = template.read_bytes()
    try:
        template.write_text(revised, encoding="utf-8", newline="\n")
        app.jinja_env.globals["uk11_home_context"] = school_context
        app.jinja_env.cache.clear()
        app.jinja_env.get_template("student.html")
    except Exception:
        template.write_bytes(original)
        app.jinja_env.globals.pop("uk11_home_context", None)
        app.jinja_env.cache.clear()
        raise
    return {"installed": True, "test_only": True, "legacy_sections_preserved_for_non_uk": True}
