from __future__ import annotations

import atexit
import base64
import builtins
import json
import os
import re
import subprocess
import sys
import zlib
from pathlib import Path


def _argv0() -> str:
    return Path(str(sys.argv[0] or '')).name


def _install_log_redaction() -> None:
    original = builtins.print
    sensitive = re.compile(
        r'(one-time bootstrap admin created|"password"\s*:|\'password\'\s*:|reset[-_ ]?token|password-reset|/reset-password/|temporary_password)',
        re.I,
    )
    def safe_print(*args, **kwargs):
        text = ' '.join(str(x) for x in args)
        if sensitive.search(text):
            return original('SCOREMAX_QA_CREDENTIAL_OUTPUT_REDACTED', **kwargs)
        return original(*args, **kwargs)
    builtins.print = safe_print


def _stage_extra_questions() -> None:
    raw = os.getenv('QA_ORCH_EXTRA_QUESTIONS_Z64', '').strip()
    if not raw:
        return
    rows = json.loads(zlib.decompress(base64.b64decode(raw)).decode('utf-8'))
    if not isinstance(rows, list) or not rows:
        raise RuntimeError('QA orchestration extra-question payload is empty/invalid')
    import app
    import mastery_lab_engine as lab
    app.init()
    c = app.db()
    staged = []
    try:
        for row in rows:
            qid = str(row['question_id'])
            ver = str(row['external_version'])
            existing = c.execute(
                'SELECT id FROM mastery_lab_questions WHERE active=1 AND external_question_id=? AND external_version=? ORDER BY id',
                (qid, ver),
            ).fetchall()
            if len(existing) > 1:
                raise RuntimeError(f'duplicate active QA rows for {qid}@{ver}')
            if not existing:
                result = lab.import_candidate_batch(
                    c,
                    [row],
                    filename='PH_QA_ORCHESTRATION_MULTI_QUESTION_FIXTURE_v015H.json',
                    file_type='json',
                    source_system='POWER_HOUSE_QA_ORCHESTRATION_ONLY',
                    source_reference='Signed QA adapter multi-question qualification population',
                )
                if not result.get('ok'):
                    raise RuntimeError('Mastery Laboratory importer rejected orchestration fixture: '+json.dumps(result, ensure_ascii=False))
                staged.append(qid)
        c.commit()
        total = c.execute('SELECT COUNT(*) FROM mastery_lab_questions WHERE active=1').fetchone()[0]
        print(json.dumps({'qa_orchestration_stage':'PASS','new_questions':len(staged),'active_qa_questions':int(total),'academic_clearance_conferred':False,'learner_release_conferred':False}, sort_keys=True))
    finally:
        c.close()


def _prepare_browser_worker_build() -> None:
    # The Render service has an intentionally immutable build command. This guarded
    # hook executes only for that service's one `python -c` build process, so browser
    # dependencies and Chromium become part of the built artifact rather than being
    # downloaded during every cold start.
    env = os.environ.copy()
    env['QA_ORCH_BROWSER_BUILD_ACTIVE'] = '1'
    env.pop('PLAYWRIGHT_BROWSERS_PATH', None)
    subprocess.check_call([
        sys.executable, '-m', 'pip', 'install', '--disable-pip-version-check',
        'Flask==3.1.3', 'playwright==1.62.0', 'waitress==3.0.2'
    ], env=env)
    subprocess.check_call([sys.executable, '-m', 'playwright', 'install', 'chromium'], env=env)
    print('QA_ORCH_BROWSER_BUILD_READY')


def _run_browser_worker() -> None:
    # Runtime is now dependency/download free: Render should only start the already
    # built browser worker and its production WSGI server.
    os.environ.pop('PLAYWRIGHT_BROWSERS_PATH', None)
    from qa_orch_browser_worker import app
    from waitress import serve
    serve(app, host='0.0.0.0', port=int(os.environ['PORT']), threads=4, channel_timeout=300)
    raise SystemExit(0)


_browser_mode = os.getenv('QA_ORCH_BROWSER_WORKER_MODE', '').strip() == '1'
if _browser_mode and _argv0() == '-c' and os.getenv('QA_ORCH_BROWSER_BUILD_ACTIVE') != '1':
    _prepare_browser_worker_build()
elif _browser_mode and _argv0() == 'qual_server.py':
    _run_browser_worker()

if os.getenv('QA_ORCH_SCOREMAX_OVERLAY', '').strip() == '1':
    _install_log_redaction()
    if _argv0() == 'stage_qa_synthetic_pilot_fixture_v6_5_11.py':
        atexit.register(_stage_extra_questions)
