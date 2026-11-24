"""Apply UK-only registration changes to a disposable, checksum-qualified ScoreMax tree.

The native register(student) handler still performs all password validation,
identity checks, rate limiting, CSRF, email and audit work. The sole extension
sets UK11 as the new student's programme and creates a market record in the
same SQLite transaction. Pakistan runtime/source is not overwritten.
"""
from __future__ import annotations

import os
import sys
from pathlib import Path

DATABASE_ANCHOR = "        if role=='teacher': ensure_referral_code(c,uid)"
DATABASE_REPLACEMENT = """        if role=='student' and os.environ.get('SCOREMAX_UK11_TEST_REGISTRATION')=='1':
            c.execute("UPDATE users SET active_programme='UK11',academic_level='UK11' WHERE id=?",(uid,))
            c.execute("INSERT INTO uk11_learner_markets(student_user_id,market_id,programme_id) VALUES(?,?,?)",
                      (uid,'UK','UK11'))
""" + DATABASE_ANCHOR

TEMPLATE = """<!doctype html><html lang="en-GB"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>Create a UK 11+ account · ScoreMax</title>
<style>body{font:16px system-ui,sans-serif;color:#18313c;background:#f6f8fa;margin:0}
main{max-width:600px;margin:3rem auto;padding:24px;background:white;border:1px solid #d9e2e7;border-radius:14px}
label{display:block;margin:18px 0;font-weight:600}
input{display:block;width:100%;box-sizing:border-box;padding:12px;font:inherit;margin-top:6px}
button{padding:12px 20px;background:#196c78;color:white;border:0;border-radius:8px;font:inherit}
a{color:#196c78}@media(max-width:640px){main{margin:1rem;padding:15px}}
</style></head><body><main><h1>Join ScoreMax UK 11+</h1>
<p>A dedicated UK 11+ learning experience. Parent or guardian involvement is required for child accounts before public launch.</p>
<p>Schools and their admissions requirements are selected after signing in. No admission eligibility is implied.</p>
<form method="post" action="/register/student">
<input type="hidden" name="_csrf_token" value="{{ csrf_token() }}">
<label>Full name<input type="text" name="full_name" required autocomplete="name" maxlength="160"></label>
<label>Email<input type="email" name="email" required autocomplete="email"></label>
<label>Password<input type="password" name="password" required minlength="8" autocomplete="new-password"></label>
<input type="hidden" name="academic_level" value="UK11">
<button type="submit">Create UK 11+ account</button>
</form><p>Already registered? <a href="/login">Sign in</a></p>
</main></body></html>"""


def apply(root: Path):
    root = root.resolve()
    if not (root / ".uk11_disposable_qualification_runtime").is_file():
        raise RuntimeError("UK11_DISPOSABLE_RUNTIME_MARKER_REQUIRED")
    appfile = root / "app.py"
    if not appfile.is_file():
        raise RuntimeError("UK11_NATIVE_APP_NOT_FOUND")
    original = appfile.read_text(encoding="utf-8")
    if original.count(DATABASE_ANCHOR)!=1 or original.count("def register(")!=1:
        raise RuntimeError("UK11_NATIVE_REGISTRATION_ANCHOR_DRIFT database=%d register_sections=%d" % (original.count(DATABASE_ANCHOR), original.count("def register(")))
    revised = original.replace(DATABASE_ANCHOR, DATABASE_REPLACEMENT, 1)
    # Display-only template is specific to student registration. The source
    # patch redirects rendering to this separate student template in test mode.
    template_anchor = "    return render_template('register.html',role=role,institutions=institutions,referral_source=request.args.get('source',''),referral_code=request.args.get('ref',''),selected_programme=request.args.get('programme',''))"
    if revised.count(template_anchor)!=1:
        raise RuntimeError("UK11_NATIVE_REGISTRATION_TEMPLATE_ANCHOR_DRIFT")
    revised = revised.replace(template_anchor,
        "    if role=='student' and os.environ.get('SCOREMAX_UK11_TEST_REGISTRATION')=='1':\n"
        "        return render_template('uk11_register_student.html')\n"
        + template_anchor,1)
    dest = root / "templates" / "uk11_register_student.html"
    if dest.exists():
        raise RuntimeError("UK11_REGISTRATION_TEMPLATE_ALREADY_EXISTS")
    # No partial write until all source anchors have been qualified.
    compile(revised, str(appfile), "exec")
    appfile.write_text(revised,encoding="utf-8")
    dest.write_text(TEMPLATE,encoding="utf-8")
    print("UK11_ISOLATED_NATIVE_REGISTRATION_OVERLAY_APPLIED")
    return root

if __name__ == "__main__":
    if len(sys.argv)!=2:
        raise SystemExit("Usage: apply_registration_overlay.py /disposable/runtime")
    apply(Path(sys.argv[1]))
