"""UK 11+ read-only post-answer help; candidate only, feature OFF by default.

Reuse the installed native written-AI owned_material authority and Power House
canonical version store. No new schema, provider client, official scoring or
mastery writes. Native integration must be replayed before actual activation.
"""
from __future__ import annotations

import json
import os
import sqlite3

from ai_explanation_candidate import ExplanationHold, prepare, PIN_KEYS

POLICY = 'SM-UK11-APPROVED-EXPLANATION-CANDIDATE-20261123-1'
FLAG = 'SCOREMAX_UK11_EXPLAIN_ENABLED_TEST_ONLY'
SUPPORTED_NATIVE_KEYS = frozenset({'SINGLE_OPTION', 'MULTIPLE_OPTIONS', 'BOOLEAN', 'TEXT', 'NUMERIC'})
REJECT_MARKING = frozenset({'AUTO_UNSCORED', 'UNSCORED', 'PENDING', 'PROVISIONAL_PRACTICE_FEEDBACK'})


def enabled(environ=None):
    env = os.environ if environ is None else environ
    return env.get(FLAG, '0') == '1'


def _row_dict(row):
    if row is None:
        return None
    return dict(row)


def _json_object(raw):
    if not isinstance(raw, str) or len(raw) > 200_000:
        raise ExplanationHold('CANONICAL_RECORD_NOT_AVAILABLE')
    try:
        out = json.loads(raw)
    except (TypeError, ValueError):
        raise ExplanationHold('CANONICAL_RECORD_NOT_AVAILABLE') from None
    if not isinstance(out, dict):
        raise ExplanationHold('CANONICAL_RECORD_NOT_AVAILABLE')
    return out


def _get_canonical(c, pin, *, current_market):
    row = c.execute('''SELECT question_id,question_version_id,question_checksum_sha256,
               curriculum_json,content_json,architecture_json,governance_json
               FROM integration_ph_question_version_store
               WHERE question_id=? AND question_version_id=?''',
               (pin['question_id'],pin['question_version_id'])).fetchone()
    doc = _row_dict(row)
    if not doc or doc['question_checksum_sha256'] != pin['question_checksum_sha256']:
        raise ExplanationHold('CANONICAL_VERSION_PIN_MISMATCH')
    curriculum = _json_object(doc['curriculum_json'])
    if curriculum.get('market_id') != 'UK' or current_market != 'UK':
        raise ExplanationHold('UK_ONLY_CANONICAL_CONTENT_REQUIRED')
    content = _json_object(doc['content_json'])
    architecture = _json_object(doc['architecture_json'])
    governance = _json_object(doc['governance_json'])
    return curriculum, content, architecture, governance


def _capsule_for(c, q, subject):
    """Use only explicitly bound, reviewed capsules; no fuzzy topic fallback."""
    capsule_id = str(q.get('capsule_id') or '').strip()
    if not capsule_id:
        return None
    row = c.execute('''SELECT capsule_id,subject,review_status,active,simple_explanation,
                      remember_this,worked_example,common_mistake,memory_tip
                      FROM learning_capsules WHERE capsule_id=? AND active=1
                      AND review_status='Approved' LIMIT 1''',(capsule_id,)).fetchone()
    cap = _row_dict(row)
    if not cap or str(cap.get('subject') or '').casefold() != str(subject or '').casefold():
        return None
    return cap


def read_explanation(c, native, *, attempt_id, question_id, student_id, owned):
    """Resolve only a previously owned submitted wrong answer.

    The caller provides the *native* owned_material result. All approved flags
    are recomputed from immutable stored governance and never accepted via HTTP.
    """
    if not enabled():
        raise ExplanationHold('UK_EXPLANATION_FEATURE_DISABLED')
    if not callable(owned):
        raise ExplanationHold('NATIVE_OWNERSHIP_AUTHORITY_REQUIRED')
    row, q, pin = owned(c, attempt_id, question_id, student_id)
    row = _row_dict(row)
    q = _row_dict(q)
    if not row or not q or not isinstance(pin, dict):
        raise ExplanationHold('SUBMITTED_ANSWER_REQUIRED')
    if int(row.get('is_correct') if row.get('is_correct') is not None else -1) != 0:
        raise ExplanationHold('INCORRECT_ANSWER_REQUIRED')
    if not isinstance(row.get('selected_answer'), str) or not row['selected_answer'].strip():
        raise ExplanationHold('SUBMITTED_ANSWER_REQUIRED')
    if row.get('marks_awarded') is None or str(row.get('marking_status') or '').upper() in REJECT_MARKING:
        raise ExplanationHold('CONFIRMED_NATIVE_MARK_REQUIRED')
    if any(not isinstance(pin.get(k), str) or not pin[k] for k in PIN_KEYS):
        raise ExplanationHold('GOVERNED_RELEASE_PIN_REQUIRED')
    row_pin = {key:row.get('ph_'+key) for key in ('question_id','question_version_id','question_checksum_sha256','release_id','release_version','release_checksum_sha256')}
    if any(pin[k] != row_pin[k] for k in PIN_KEYS):
        raise ExplanationHold('SAVED_ANSWER_PIN_MISMATCH')
    if pin.get('market_id') != 'UK':
        raise ExplanationHold('UK_RELEASE_PIN_REQUIRED')
    membership = c.execute("""SELECT 1 FROM integration_ph_release_question_membership
            WHERE release_id=? AND release_version=?
            AND question_id=? AND question_version_id=? LIMIT 1""",
            (pin['release_id'],pin['release_version'],pin['question_id'],pin['question_version_id'])).fetchone()
    if membership is None:
        raise ExplanationHold('EXACT_ROUTE_MEMBERSHIP_REQUIRED')
    _, content, architecture, governance = _get_canonical(c,pin,current_market=str(q.get('ph_market_id') or ''))
    governance_gate = getattr(getattr(native,'integration_v1',None),'_governance_ready',None)
    if not callable(governance_gate):
        raise ExplanationHold('NATIVE_GOVERNANCE_GATE_MISSING')
    ready, _ = governance_gate({'governance':governance,'architecture':architecture})
    if ready is not True:
        raise ExplanationHold('ACADEMIC_GOVERNANCE_NOT_READY')
    if q.get('ph_is_auto_markable') not in (1, True):
        raise ExplanationHold('NATIVE_SCORING_MODE_UNQUALIFIED')
    key_type = (content.get('marking') or {}).get('key_type')
    if key_type not in SUPPORTED_NATIVE_KEYS:
        raise ExplanationHold('UNQUALIFIED_RESPONSE_TYPE')
    stem = content.get('stem')
    approved_solution = (content.get('marking') or {}).get('explanation')
    if not isinstance(stem,str):
        raise ExplanationHold('GOVERNED_STEM_REQUIRED')
    # Fail closed for all unresolved stimulus/visual types in this initial text-only lane.
    if content.get('stimulus_ref') or content.get('inline_stimulus') or str(q.get('stimulus_type') or '').upper() in (
       'DIAGRAM','IMAGE','IMAGE_REFERENCE','DIAGRAM_REFERENCE','MIXED','VISUAL','NONVERBAL'):
        raise ExplanationHold('STIMULUS_EXPLANATION_NEEDS_QUALIFICATION')
    cap = _capsule_for(c, q, q.get('subject'))
    question = {'question':stem, 'answer':str((content.get('marking') or {}).get('key') or ''),
                'explanation':approved_solution if approved_solution is not None else '',
                'topic':q.get('topic') or '', 'qtype':q.get('qtype') or ''}
    output=prepare(attempt_status='submitted', is_correct=False, academic_approved=True,
                   release_active=True,rights_approved=True,attempt_pin=pin,version_pin=pin,
                   question=question,capsule=cap)
    return output['student_view']


def install(native):
    """Register a narrow GET route alongside existing native result review."""
    app=native.app
    # The result template must always have the guard, even when this feature is OFF.
    app.jinja_env.globals['uk11_explanation_available'] = enabled
    if not enabled():
        return {'enabled':False,'routes_registered':0,'provider_calls':0}
    if app.extensions.get('scoremax_uk11_explain'):
        raise RuntimeError('UK_EXPLANATION_ALREADY_INSTALLED')
    if not callable(app.extensions.get('scoremax_written_ai_owned_material')):
        raise RuntimeError('UK_EXPLANATION_REQUIRES_NATIVE_OWNED_MATERIAL')
    if not callable(getattr(native,'require',None)):
        raise RuntimeError('UK_EXPLANATION_REQUIRES_NATIVE_STUDENT_AUTH')
    from flask import abort, render_template, session, url_for
    app.extensions['scoremax_uk11_explain']={'policy':POLICY,'provider_calls':0,
                                            'official_score_changes':False,'mastery_changes':False}

    @app.route('/uk11/result/<int:attempt_id>/question/<int:question_id>/explain',methods=['GET'])
    def uk11_explain_mistake(attempt_id,question_id):
        if not native.require('student'):
            abort(403)
        user_id=session.get('user_id')
        if not isinstance(user_id,int):
            abort(403)
        c=native.db()
        try:
            view=read_explanation(c,native,attempt_id=attempt_id,question_id=question_id,
                                  student_id=user_id,
                                  owned=app.extensions['scoremax_written_ai_owned_material'])
        except (ExplanationHold,ValueError,TypeError,KeyError,sqlite3.DatabaseError):
            abort(404)  # Do not reveal internal source or student-detail existence.
        finally:
            c.close()
        return render_template('uk11_explain_mistake.html',explanation=view,
                               result_url=url_for('result',aid=attempt_id))
    return {'enabled':True,'routes_registered':1,'provider_calls':0,
            'official_score_changes':False,'mastery_changes':False}
