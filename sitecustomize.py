from __future__ import annotations

import atexit
import base64
import builtins
import json
import os
import subprocess
import sys
import zlib
from pathlib import Path


def _argv0() -> str:
    return Path(str(sys.argv[0] or '')).name


def _redact_provisioning_output() -> None:
    original = builtins.print
    def safe_print(*args, **kwargs):
        text = ' '.join(str(x) for x in args)
        if '"identities"' in text or '"password"' in text or "'password'" in text:
            return original('SCOREMAX_QA_PROVISIONING_COMPLETED_REDACTED', **kwargs)
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


def _run_browser_worker() -> None:
    subprocess.check_call([sys.executable, '-m', 'pip', 'install', '--disable-pip-version-check', 'Flask==3.1.3', 'playwright==1.62.0'])
    subprocess.check_call([sys.executable, '-m', 'playwright', 'install', 'chromium'])
    os.environ.setdefault('PLAYWRIGHT_BROWSERS_PATH', '0')
    from qa_orch_browser_worker import app
    app.run(host='0.0.0.0', port=int(os.environ['PORT']), debug=False, threaded=True, use_reloader=False)
    raise SystemExit(0)


if os.getenv('QA_ORCH_BROWSER_WORKER_MODE', '').strip() == '1' and _argv0() == 'qual_server.py':
    _run_browser_worker()

if os.getenv('QA_ORCH_SCOREMAX_OVERLAY', '').strip() == '1':
    if _argv0() == 'provision_qa_synthetic_learners_v6_5_11.py':
        _redact_provisioning_output()
    elif _argv0() == 'stage_qa_synthetic_pilot_fixture_v6_5_11.py':
        atexit.register(_stage_extra_questions)
