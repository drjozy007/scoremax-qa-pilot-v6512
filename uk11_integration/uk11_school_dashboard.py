"""UK11 read-only school-aware dashboard, candidate for disposable native ScoreMax.

It reuses the account endpoint's session-scoped canonical projection, without
forking learner identity, permissions, route resolution or persistence.
This view is NOT a test allocation or mastery grant.
"""
from flask import Blueprint, current_app, render_template_string, session, abort

TEMPLATE = """<!doctype html>
<html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>My UK 11+ learning · ScoreMax</title>
<style>
:root{font-family:system-ui,sans-serif;color:#1b3544;background:#f6f8fa}
body{max-width:1060px;margin:0 auto;padding:24px}
a{color:#185b7c}section{background:white;border:1px solid #d7e0e7;padding:20px;border-radius:12px;margin:14px 0}
ul{padding-left:22px}li{margin:8px 0}.level{display:inline-block;padding:8px;margin:5px 4px 5px 0;border:1px solid #acbdc8;border-radius:7px}
.notice{border-left:5px solid #a96a19;padding:10px;background:#fff9ec}
@media(max-width:480px){body{padding:12px}section{padding:13px}}
</style></head><body><main>
<p><a href="/student">ScoreMax student home</a></p>
<h1>My UK 11+ learning</h1>
<p>Your preparation follows the schools you have selected. School selection does not establish admission eligibility.</p>
<section aria-labelledby="schools"><h2 id="schools">My selected schools</h2>
{% if context.schools %}
<ul>{% for school in context.schools %}<li><strong>{{ school.name or school.school_name or 'School' }}</strong></li>{% endfor %}</ul>
{% else %}<p>No target schools selected yet.</p>{% endif %}
</section>
<section aria-labelledby="tests"><h2 id="tests">Relevant tests</h2>
{% if context.routes %}<ul>{% for route in context.routes %}
<li>{{ route.name or route.route_name or 'Assessment route' }}
{% if route.evidence_status == 'SYNTHETIC_ONLY' %}<strong> — synthetic testing only</strong>{% endif %}</li>
{% endfor %}</ul>{% else %}<p>No verified tests to show.</p>{% endif %}
</section>
<section aria-labelledby="subjects"><h2 id="subjects">Relevant subjects</h2>
{% if context.subjects %}<ul>{% for subject in context.subjects %}<li>{{ subject }}</li>{% endfor %}</ul>
{% else %}<p>Subject requirements are not established yet.</p>{% endif %}
</section>
{% if context.pending %}<section aria-labelledby="pending"><h2 id="pending">Admission details requiring confirmation</h2>
<p class="notice">These schools or test requirements are pending verification and do not add assumed subjects.</p>
<ul>{% for item in context.pending %}<li>{{ item.message or item.name or 'Official verification pending' }}</li>{% endfor %}</ul></section>{% endif %}
<section aria-labelledby="mastery"><h2 id="mastery">Your six mastery levels</h2>
<div aria-label="ScoreMax mastery progression">{% for level in levels %}<span class="level">{{ level }}</span>{% endfor %}</div>
<p><strong>Current UK 11+ status:</strong> Not Yet Established</p>
<p>Your next learning action will be provided when approved learning content and independent mastery evidence are available. This view does not award levels.</p>
</section>
</main></body></html>"""


def create_uk11_dashboard_blueprint():
    bp = Blueprint("uk11_school_dashboard", __name__)

    @bp.get("/uk11/my-learning")
    def uk11_my_learning():
        if session.get("role") != "student" or not isinstance(session.get("user_id"), int):
            abort(403)
        # Invoke the very same session-authorised API projection, not a second
        # or independently implemented school/exam route mapping.
        endpoint = current_app.view_functions.get("uk11_account.get_schools")
        if endpoint is None:
            raise RuntimeError("UK11_ACCOUNT_PROJECTION_MISSING")
        result = endpoint()
        if result.status_code != 200:
            return result
        context = result.get_json()
        return render_template_string(
            TEMPLATE, context=context,
            levels=("Foundation","Exam Ready","Advanced","Distinction","Expert","Elite")
        )

    return bp
