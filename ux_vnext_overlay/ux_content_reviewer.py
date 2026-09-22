from __future__ import annotations

import json
import os
import secrets
import sqlite3
from datetime import datetime
from pathlib import Path

from flask import abort, flash, redirect, render_template, request, session, url_for
from werkzeug.security import generate_password_hash

REVIEWER_EMAIL='ux-content-reviewer@scoremax.test'
REVIEWER_ID='CRV-900001'
REVIEWER_USERNAME='ux-content-reviewer'
REVIEWER_NAME='ScoreMax Content Reviewer'

FLAG_REASONS={
    'WRONG_KEY':('Wrong answer / key','HIGH'),
    'FACTUAL_ERROR':('Factual or scientific error','HIGH'),
    'AMBIGUOUS':('Ambiguous question','HIGH'),
    'EXPLANATION':('Explanation problem','MEDIUM'),
    'WORDING':('Wording / clarity problem','LOW'),
    'SYLLABUS':('Syllabus / curriculum problem','HIGH'),
    'DUPLICATE':('Duplicate / near duplicate','MEDIUM'),
    'FORMAT_MEDIA':('Formatting / image / rendering problem','MEDIUM'),
    'OTHER':('Other academic concern','MEDIUM'),
}


def _db_path() -> Path:
    return Path(os.environ.get('SCOREMAX_DB','/tmp/scoremax-ux-vnext/state/scoremax.db'))


def _connect() -> sqlite3.Connection:
    conn=sqlite3.connect(_db_path(),timeout=5)
    conn.row_factory=sqlite3.Row
    conn.execute('PRAGMA foreign_keys=ON')
    conn.execute('PRAGMA busy_timeout=5000')
    return conn


def _cols(conn,table):
    return {r['name'] for r in conn.execute(f'PRAGMA table_info({table})').fetchall()}


def _ensure_col(conn,table,name,definition):
    if name not in _cols(conn,table):
        conn.execute(f'ALTER TABLE {table} ADD COLUMN {name} {definition}')


def _ensure_reviewer_schema_and_account() -> None:
    # Legacy single-account hook is retained only for compatibility. The governed
    # five-account seed lives in ux_reviewer_accounts and is driven by explicit envs.
    conn=_connect()
    try:
        _ensure_col(conn,'users','content_reviewer_enabled','INTEGER DEFAULT 0')
        if 'pilot_feedback' in {r['name'] for r in conn.execute("SELECT name FROM sqlite_master WHERE type='table'").fetchall()}:
            _ensure_col(conn,'pilot_feedback','context_json',"TEXT DEFAULT '{}'")
            _ensure_col(conn,'pilot_feedback','page_path',"TEXT DEFAULT ''")
        password=os.environ.get('SCOREMAX_STAGING_REVIEWER_PASSWORD','').strip()
        if password:
            row=conn.execute("SELECT id FROM users WHERE lower(COALESCE(email,''))=?",(REVIEWER_EMAIL,)).fetchone()
            ph=generate_password_hash(password)
            if row:
                conn.execute("""UPDATE users SET system_user_id=?,username=?,full_name=?,password_hash=?,role='student',
                  academic_level='FSc Part 1',subjects='Biology,Chemistry,Physics',account_status='active',active_programme='FSc Part 1',
                  content_reviewer_enabled=1 WHERE id=?""",
                  (REVIEWER_ID,REVIEWER_USERNAME,REVIEWER_NAME,ph,row['id']))
            else:
                conn.execute("""INSERT INTO users(system_user_id,role,full_name,email,username,password_hash,province,board,academic_level,subjects,
                  account_status,active_programme,login_provider,content_reviewer_enabled)
                  VALUES(?,'student',?,?,?,?,?,?,?,'Biology,Chemistry,Physics','active','FSc Part 1','password',1)""",
                  (REVIEWER_ID,REVIEWER_NAME,REVIEWER_EMAIL,REVIEWER_USERNAME,ph,'Punjab','Punjab Board','FSc Part 1'))
        conn.commit()
    finally:
        conn.close()


def _is_reviewer(user_id=None) -> bool:
    uid=user_id or session.get('user_id')
    role=str(session.get('role') or '').lower()
    if not uid:
        return False
    # Platform admins may inspect governed staged content but gain no release,
    # materialisation, mastery or learner-activation authority from this capability.
    if role=='admin':
        return True
    if role!='student':
        return False
    conn=_connect()
    try:
        row=conn.execute("SELECT COALESCE(content_reviewer_enabled,0) enabled FROM users WHERE id=?",(uid,)).fetchone()
        return bool(row and int(row['enabled'] or 0)==1)
    finally:
        conn.close()


def _require_reviewer():
    if not _is_reviewer():
        abort(403)


def _question_live_clause(conn,alias='q'):
    cols=_cols(conn,'questions')
    parts=[]
    if 'active' in cols: parts.append(f'COALESCE({alias}.active,1)=1')
    if 'scoremax_ready' in cols: parts.append(f'COALESCE({alias}.scoremax_ready,1)=1')
    if 'status' in cols: parts.append(f"COALESCE({alias}.status,'Approved') NOT IN ('Withdrawn','Archived')")
    return ' AND '.join(parts) if parts else '1=1'


def _question_dict(row):
    d=dict(row)
    d['public_id']=d.get('question_id') or d.get('ph_question_id') or f"Q-{d.get('id')}"
    d['is_withdrawn']=str(d.get('status') or '').upper()=='WITHDRAWN' or ('active' in d and not int(d.get('active') or 0))
    return d


def _has_exact_ph_lineage(q: dict) -> bool:
    required=('ph_question_id','ph_question_version_id','ph_question_checksum_sha256','ph_release_id','ph_release_version','ph_release_checksum_sha256')
    return str(q.get('ph_projection_owner') or '')=='POWER_HOUSE' and all(str(q.get(k) or '').strip() for k in required)



# SCOREMAX_STAGED_DELIVERY_REVIEWER_V1
def _table_exists(conn, name: str) -> bool:
    return bool(conn.execute("SELECT 1 FROM sqlite_master WHERE type='table' AND name=?",(str(name),)).fetchone())


def _staged_rows(conn):
    exclusion = """
      AND NOT EXISTS (
        SELECT 1 FROM ph_bridge_staged_withdrawal_exclusions_v6611e e
        WHERE e.release_id=m.release_id AND e.release_version=m.release_version
          AND e.question_id=m.question_id AND e.question_version_id=m.question_version_id
      )
    """ if _table_exists(conn,'ph_bridge_staged_withdrawal_exclusions_v6611e') else ""
    sql = """SELECT m.id membership_id,m.ordinal,m.release_id,m.release_version,
                    v.question_id,v.question_version_id,v.question_version_number,
                    v.question_checksum_sha256,v.scoremax_projection_json,v.content_json,
                    r.package_checksum_sha256 release_checksum_sha256,
                    r.market_id release_market_id,r.programme_id release_programme_id,
                    r.subject_id release_subject_id,r.chapter_id release_chapter_id,
                    r.local_status
             FROM integration_ph_release_question_membership m
             JOIN integration_ph_question_version_store v
               ON v.question_id=m.question_id AND v.question_version_id=m.question_version_id
             JOIN integration_ph_content_releases r
               ON r.release_id=m.release_id AND r.release_version=m.release_version
             WHERE r.local_status='STAGED' """ + exclusion + """
             ORDER BY r.admitted_at,m.ordinal,m.id"""
    return conn.execute(sql).fetchall()


def _staged_question_dict(row):
    try:
        q=json.loads(row['scoremax_projection_json'] or '{}')
    except Exception:
        q={}
    q=dict(q or {})
    try:
        _content=json.loads(row['content_json'] or '{}')
    except Exception:
        _content={}
    _exam=str(_content.get('exam_question_type') or '').upper()
    _family=str(_content.get('question_family_type') or '').upper()
    _matching=('MATCHING' in _exam or 'MATCHING' in _family)
    q['_source_content']=_content
    if _matching:
        q['qtype']='Matching'
        q['_matching_key']=(_content.get('marking') or {}).get('key')
    q.update({
      'membership_id':int(row['membership_id']),
      'public_id':str(row['question_id'] or ''),
      'ph_projection_owner':'POWER_HOUSE',
      'ph_question_id':str(row['question_id'] or ''),
      'ph_question_version_id':str(row['question_version_id'] or ''),
      'ph_question_checksum_sha256':str(row['question_checksum_sha256'] or '').lower(),
      'ph_release_id':str(row['release_id'] or ''),
      'ph_release_version':str(row['release_version'] or ''),
      'ph_release_checksum_sha256':str(row['release_checksum_sha256'] or '').lower(),
      'ph_market_id':str(q.get('ph_market_id') or row['release_market_id'] or ''),
      'ph_programme_id':str(q.get('ph_programme_id') or row['release_programme_id'] or ''),
      'ph_subject_id':str(q.get('ph_subject_id') or row['release_subject_id'] or ''),
      'ph_chapter_id':str(q.get('ph_chapter_id') or row['release_chapter_id'] or ''),
      'review_source':'STAGED_POWER_HOUSE',
      'is_withdrawn':False,
      'status':'Staged',
    })
    return q



def _staged_learner_render_context(q: dict) -> dict:
    """Use ScoreMax's own runtime type adapter and learner-template inputs."""
    import app as scoremax
    q['id']=int(q.get('membership_id') or q.get('id') or 0)
    def _obj(value):
        if isinstance(value,dict):
            return dict(value)
        return scoremax.safe_json(value,{})
    answer_cfg=_obj(q.get('answer_config'))
    marking_cfg=_obj(q.get('marking_config'))
    options=answer_cfg.get('options') or [
      {'id':code,'text':q.get(key)}
      for code,key in [('A','option_a'),('B','option_b'),('C','option_c'),('D','option_d')]
      if str(q.get(key) or '').strip()
    ]
    qtype=scoremax.canonical_question_type(q)

    # Matching remains governed by the same canonical learner renderer. When the
    # staged projection carries the visible surface rather than materialised
    # answer_config, adapt that governed surface into the runtime's existing
    # left_items/right_options contract; no second renderer is created.
    if qtype=='matching' and (not answer_cfg.get('left_items') or not answer_cfg.get('right_options')):
        from ux_matching_support import parse_matching_surface
        parsed=parse_matching_surface(q.get('stimulus_data') or '',q.get('_matching_key') or q.get('answer'))
        if parsed.get('valid'):
            answer_cfg=dict(answer_cfg)
            answer_cfg['left_items']=list(parsed.get('left') or [])
            answer_cfg['right_options']=list(parsed.get('right') or [])

    # Canonical ordering renderer contract: ordering_items[{id,text}].
    # Adapt the governed PH visible ordering surface into that existing runtime
    # contract. This is a type adapter only; it does not alter question content.
    if qtype=='ordering' and not answer_cfg.get('ordering_items'):
        source=dict(q.get('_source_content') or {})
        raw_items=[]
        statements=source.get('statements') or []
        if isinstance(statements,list):
            raw_items=[str(x).strip() for x in statements if str(x).strip()]
        if not raw_items:
            source_options=source.get('options') or []
            if isinstance(source_options,list):
                raw_items=[str(x.get('text') or '').strip() for x in source_options
                           if isinstance(x,dict) and str(x.get('text') or '').strip()]
        if raw_items:
            answer_cfg=dict(answer_cfg)
            answer_cfg['ordering_items']=[
              {'id':f'O{i+1}','text':text} for i,text in enumerate(raw_items)
            ]

    return {
      'qtype':qtype,'options':options,'answer_cfg':answer_cfg,'marking_cfg':marking_cfg,
      'answers':{},'saved_struct':{},'saved_positions':{},'confidence':{},'response_times':{},
      'qa_sandbox':True,'qa_session_id':'STAGED-POWER-HOUSE',
      'qa_render_checksum':str(q.get('ph_question_checksum_sha256') or ''),
      'assessment':{'mode':'review'},'exam_meta':{},
    }


def _staged_canonical_surface_probe(q: dict):
    ctx=_staged_learner_render_context(q)
    html=render_template('_learner_question_surface.html',q=q,**ctx)
    interactive=any(token in html for token in (
      '<input','<textarea','<select','draggable=','data-order','name="match::','name="order::'
    ))
    unsupported=('interactive renderer is not active yet' in html.lower())
    return ctx,bool(interactive and not unsupported),html


def _staged_question(conn, membership_id: int):
    rows=[r for r in _staged_rows(conn) if int(r['membership_id'])==int(membership_id)]
    return _staged_question_dict(rows[0]) if len(rows)==1 else None


CROSS50_RELEASE_PREFIX='REL::CROSS50-QA13::'


def _filter_staged_rows(rows, batch: str):
    batch=str(batch or '').strip().lower()
    if batch=='cross50':
        return [r for r in rows if str(r['release_id'] or '').startswith(CROSS50_RELEASE_PREFIX)]
    return list(rows)


def _ensure_staged_human_review_schema(conn) -> None:
    conn.execute("""CREATE TABLE IF NOT EXISTS staged_human_review_decisions_v1(
      id INTEGER PRIMARY KEY AUTOINCREMENT,
      membership_id INTEGER NOT NULL,
      reviewer_user_id INTEGER NOT NULL,
      question_id TEXT NOT NULL,
      question_version_id TEXT NOT NULL,
      release_id TEXT NOT NULL,
      release_version TEXT NOT NULL,
      decision TEXT NOT NULL CHECK(decision IN ('APPROVED','REJECTED')),
      reason_code TEXT NOT NULL DEFAULT '',
      note TEXT NOT NULL DEFAULT '',
      decided_at TEXT NOT NULL,
      UNIQUE(membership_id,reviewer_user_id)
    )""")
    conn.execute("""CREATE INDEX IF NOT EXISTS idx_staged_human_review_v1_reviewer
      ON staged_human_review_decisions_v1(reviewer_user_id,membership_id)""")


def _staged_decision(conn, reviewer_user_id: int, membership_id: int):
    row=conn.execute("""SELECT * FROM staged_human_review_decisions_v1
      WHERE reviewer_user_id=? AND membership_id=?""",(int(reviewer_user_id),int(membership_id))).fetchone()
    return dict(row) if row else None


def _staged_decision_stats(conn, reviewer_user_id: int, membership_ids):
    ids=[int(x) for x in membership_ids]
    if not ids:
        return {'total':0,'reviewed':0,'approved':0,'rejected':0,'remaining':0}
    marks=','.join('?' for _ in ids)
    rows=conn.execute(f"""SELECT membership_id,decision FROM staged_human_review_decisions_v1
      WHERE reviewer_user_id=? AND membership_id IN ({marks})""",[int(reviewer_user_id)]+ids).fetchall()
    by_id={int(r['membership_id']):str(r['decision']) for r in rows}
    approved=sum(1 for v in by_id.values() if v=='APPROVED')
    rejected=sum(1 for v in by_id.values() if v=='REJECTED')
    reviewed=len(by_id)
    return {'total':len(ids),'reviewed':reviewed,'approved':approved,'rejected':rejected,'remaining':max(0,len(ids)-reviewed)}


def _staged_flags(conn, reviewer_user_id: int, question_version_id: str):
    rows=conn.execute("""SELECT * FROM pilot_feedback
      WHERE reporter_user_id=? AND category='ACADEMIC_CONTENT'
      ORDER BY id DESC LIMIT 250""",(reviewer_user_id,)).fetchall()
    out=[]
    for row in rows:
        d=dict(row)
        try: ctx=json.loads(d.get('context_json') or '{}')
        except Exception: ctx={}
        if str(ctx.get('review_source') or '')=='STAGED_POWER_HOUSE' and str(ctx.get('ph_question_version_id') or '')==str(question_version_id):
            out.append(d)
    return out


def _queue_staged_incident(conn, q: dict, code: str, reason: str, severity: str, description: str, context: dict) -> str:
    import scoremax_ph_bridge_v6611d as ph_bridge_v6611d
    import scoremax_integration_v1 as integration_v1
    required=('ph_question_id','ph_question_version_id','ph_question_checksum_sha256',
              'ph_release_id','ph_release_version','ph_release_checksum_sha256')
    if str(q.get('ph_projection_owner') or '')!='POWER_HOUSE':
        return ''
    if any(not str(q.get(k) or '').strip() for k in required):
        return ''
    if len(str(q.get('ph_question_checksum_sha256') or ''))!=64 or len(str(q.get('ph_release_checksum_sha256') or ''))!=64:
        return ''
    payload={
      'incident_id':'SMINC::'+ph_bridge_v6611d._sha_text(code+'|'+str(q['ph_question_version_id']))[:32],
      'scoremax_feedback_code':str(code),
      'category':str(reason or 'OTHER')[:120],
      'severity':str(severity or 'MEDIUM').upper()[:20],
      'description':ph_bridge_v6611d._redact_free_text(description),
      'source':'SCOREMAX_DELIVERY_REVIEWER',
      'page_path':ph_bridge_v6611d._safe_page_path(context.get('page')),
      'question':{
        'question_id':str(q['ph_question_id']),
        'question_version_id':str(q['ph_question_version_id']),
        'question_checksum_sha256':str(q['ph_question_checksum_sha256']).lower(),
        'release_id':str(q['ph_release_id']),
        'release_version':str(q['ph_release_version']),
        'release_checksum_sha256':str(q['ph_release_checksum_sha256']).lower(),
        'market_id':str(q.get('ph_market_id') or ''),
        'programme_id':str(q.get('ph_programme_id') or ''),
        'subject_id':str(q.get('ph_subject_id') or ''),
        'chapter_id':str(q.get('ph_chapter_id') or ''),
        'rendered_question_sha256':ph_bridge_v6611d._sha_text(str(q.get('question') or '')),
      },
      'reporter_identity_included':False,
      'student_pii_included':False,
      'release_authority_conferred':False,
    }
    idem='content-incident::'+str(code)+'::'+str(q['ph_question_version_id'])
    env=integration_v1._envelope(ph_bridge_v6611d.INCIDENT,'POWER_HOUSE',idem,str(code),payload,ph_bridge_v6611d.RELEASE,'INTERNAL')
    return integration_v1._queue(conn,env,str(code),'PILOT_FEEDBACK',str(code))


def _staged_boundary_snapshot(conn):
    staged=conn.execute("SELECT release_id,release_version FROM integration_ph_content_releases WHERE local_status='STAGED' ORDER BY id").fetchall()
    membership=0; eligible=0; materialised=0; learner_active=0; authorizations=0
    for rel in staged:
        rid=str(rel['release_id']); ver=str(rel['release_version'])
        membership += int(conn.execute("SELECT COUNT(*) FROM integration_ph_release_question_membership WHERE release_id=? AND release_version=?",(rid,ver)).fetchone()[0])
        if _table_exists(conn,'ph_bridge_staged_withdrawal_exclusions_v6611e'):
            eligible += int(conn.execute("""SELECT COUNT(*) FROM integration_ph_release_question_membership m
              WHERE m.release_id=? AND m.release_version=?
                AND NOT EXISTS (
                  SELECT 1 FROM ph_bridge_staged_withdrawal_exclusions_v6611e e
                  WHERE e.release_id=m.release_id AND e.release_version=m.release_version
                    AND e.question_id=m.question_id AND e.question_version_id=m.question_version_id
                )""",(rid,ver)).fetchone()[0])
        else:
            eligible += int(conn.execute("SELECT COUNT(*) FROM integration_ph_release_question_membership WHERE release_id=? AND release_version=?",(rid,ver)).fetchone()[0])
        materialised += int(conn.execute("""SELECT COUNT(*) FROM questions
          WHERE ph_projection_owner='POWER_HOUSE' AND ph_release_id=? AND ph_release_version=?""",(rid,ver)).fetchone()[0])
        learner_active += int(conn.execute("""SELECT COUNT(*) FROM questions
          WHERE ph_projection_owner='POWER_HOUSE' AND ph_release_id=? AND ph_release_version=? AND COALESCE(active,0)=1""",(rid,ver)).fetchone()[0])
        authorizations += int(conn.execute("""SELECT COUNT(*) FROM integration_ph_product_activation_authorizations
          WHERE release_id=? AND release_version=?""",(rid,ver)).fetchone()[0])
    return {'staged_releases':len(staged),'membership':membership,'eligible':eligible,
            'materialised':materialised,'learner_active':learner_active,'activation_authorizations':authorizations}


def _reviewer_nav_patch() -> str:
    return r'''<style id="ux-content-reviewer-nav-style">.ux-review-nav{background:#fff7e6!important;color:#6f4a00!important;border-radius:9px!important;font-weight:900!important}.ux-reviewer-badge{display:inline-flex;align-items:center;gap:5px;padding:4px 7px;border-radius:999px;background:#fff7e6;color:#6f4a00;font-size:.62rem;font-weight:900}</style><script id="ux-content-reviewer-nav">(function(){function add(){const nav=document.querySelector('.site-header .desktop-nav');const account=nav&&nav.querySelector('.student-account-menu');if(nav&&account&&!nav.querySelector('.ux-review-nav')){const a=document.createElement('a');a.className='ux-review-nav'+(location.pathname.startsWith('/student/content-review')?' active':'');a.href='/student/content-review';a.textContent='Review';nav.insertBefore(a,account);}const menu=document.querySelector('.student-account-dropdown');if(menu&&!menu.querySelector('.ux-review-menu')){const a=document.createElement('a');a.className='ux-review-menu';a.href='/student/content-review';a.textContent='Review Questions';menu.insertBefore(a,menu.firstElementChild?.nextSibling||null);}}function later(){setTimeout(add,30);setTimeout(add,180);}if(document.readyState==='loading')document.addEventListener('DOMContentLoaded',later);else later();})();</script>'''


def install_content_reviewer(app) -> None:
    if getattr(app,'_ux_content_reviewer_installed',False): return
    _ensure_reviewer_schema_and_account()
    _review_schema_conn=_connect()
    try:
        _ensure_staged_human_review_schema(_review_schema_conn)
        _review_schema_conn.commit()
    finally:
        _review_schema_conn.close()

    @app.route('/student/content-review',methods=['GET'],endpoint='ux_content_review')
    def ux_content_review():
        _require_reviewer()
        subject=(request.args.get('subject') or '').strip()
        chapter=(request.args.get('chapter') or '').strip()
        search=(request.args.get('q') or '').strip()
        status=(request.args.get('status') or 'live').strip().lower()
        conn=_connect()
        try:
            clauses=[]; params=[]
            if status=='withdrawn':
                qcols=_cols(conn,'questions')
                withdrawn=[]
                if 'status' in qcols: withdrawn.append("UPPER(COALESCE(q.status,''))='WITHDRAWN'")
                if 'active' in qcols: withdrawn.append('COALESCE(q.active,1)=0')
                clauses.append('('+' OR '.join(withdrawn)+')' if withdrawn else '0=1')
            else:
                clauses.append(_question_live_clause(conn,'q'))
            if subject: clauses.append('lower(q.subject)=lower(?)'); params.append(subject)
            if chapter: clauses.append('lower(q.chapter)=lower(?)'); params.append(chapter)
            if search:
                clauses.append("(lower(COALESCE(q.question_id,'')) LIKE ? OR lower(COALESCE(q.question,'')) LIKE ?)")
                token='%'+search.lower()+'%'; params.extend([token,token])
            where=' AND '.join(clauses) if clauses else '1=1'
            rows=conn.execute(f"SELECT q.* FROM questions q WHERE {where} ORDER BY q.id ASC LIMIT 120",params).fetchall()
            questions=[_question_dict(r) for r in rows]
            subjects=[r['subject'] for r in conn.execute("SELECT DISTINCT subject FROM questions WHERE COALESCE(subject,'')<>'' ORDER BY subject").fetchall()]
            chapters=[r['chapter'] for r in conn.execute("SELECT DISTINCT chapter FROM questions WHERE COALESCE(chapter,'')<>'' ORDER BY chapter").fetchall()]
            latest={r['question_id']:dict(r) for r in conn.execute("""SELECT pf.* FROM pilot_feedback pf JOIN (
                SELECT question_id,MAX(id) max_id FROM pilot_feedback WHERE reporter_user_id=? AND category='ACADEMIC_CONTENT' GROUP BY question_id
                ) x ON x.max_id=pf.id""",(session['user_id'],)).fetchall()} if 'pilot_feedback' in {r['name'] for r in conn.execute("SELECT name FROM sqlite_master WHERE type='table'").fetchall()} else {}
            for q in questions: q['latest_flag']=latest.get(q['id'])
            live_count=conn.execute(f"SELECT COUNT(*) n FROM questions q WHERE {_question_live_clause(conn,'q')}").fetchone()['n']
            flagged_count=conn.execute("SELECT COUNT(*) n FROM pilot_feedback WHERE reporter_user_id=? AND category='ACADEMIC_CONTENT'",(session['user_id'],)).fetchone()['n']
            open_count=conn.execute("SELECT COUNT(*) n FROM pilot_feedback WHERE reporter_user_id=? AND category='ACADEMIC_CONTENT' AND status NOT IN ('RESOLVED','CLOSED')",(session['user_id'],)).fetchone()['n']
            withdrawn_count=conn.execute("SELECT COUNT(*) n FROM questions WHERE UPPER(COALESCE(status,''))='WITHDRAWN'").fetchone()['n']
        finally: conn.close()
        return render_template('ux_content_review.html',questions=questions,subjects=subjects,chapters=chapters,filters={'subject':subject,'chapter':chapter,'q':search,'status':status},stats={'live':live_count,'flagged':flagged_count,'open':open_count,'withdrawn':withdrawn_count})

    @app.route('/student/content-review/question/<int:question_id>',methods=['GET'],endpoint='ux_content_review_question')
    def ux_content_review_question(question_id):
        _require_reviewer()
        mode=(request.args.get('view') or 'student').strip().lower()
        if mode not in {'student','reviewer'}: mode='student'
        conn=_connect()
        try:
            row=conn.execute('SELECT * FROM questions WHERE id=?',(question_id,)).fetchone()
            if not row: abort(404)
            q=_question_dict(row)
            flags=[dict(r) for r in conn.execute("SELECT * FROM pilot_feedback WHERE question_id=? AND category='ACADEMIC_CONTENT' ORDER BY id DESC",(question_id,)).fetchall()]
            prev_row=conn.execute('SELECT id FROM questions WHERE id<? ORDER BY id DESC LIMIT 1',(question_id,)).fetchone()
            next_row=conn.execute('SELECT id FROM questions WHERE id>? ORDER BY id ASC LIMIT 1',(question_id,)).fetchone()
        finally: conn.close()
        return render_template('ux_content_review_question.html',q=q,mode=mode,flags=flags,reasons=FLAG_REASONS,prev_id=prev_row['id'] if prev_row else None,next_id=next_row['id'] if next_row else None)

    @app.route('/student/content-review/question/<int:question_id>/flag',methods=['POST'],endpoint='ux_content_review_flag')
    def ux_content_review_flag(question_id):
        _require_reviewer()
        reason=(request.form.get('reason') or '').strip().upper()
        if reason not in FLAG_REASONS:
            flash('Choose a valid reason for the flag.','error'); return redirect(url_for('ux_content_review_question',question_id=question_id,view='reviewer'))
        notes=(request.form.get('notes') or '').strip()[:3000]
        conn=_connect()
        try:
            qrow=conn.execute('SELECT * FROM questions WHERE id=?',(question_id,)).fetchone()
            if not qrow: abort(404)
            q=_question_dict(qrow)
            if not _has_exact_ph_lineage(q):
                flash('This question does not have complete Power House lineage, so no flag was created.','error')
                return redirect(url_for('ux_content_review_question',question_id=question_id,view='reviewer'))
            label,severity=FLAG_REASONS[reason]
            code='CRF-'+datetime.now().strftime('%Y%m%d%H%M%S')+'-'+secrets.token_hex(2).upper()
            page=f'/student/content-review/question/{question_id}'
            context={
              'source':'SCOREMAX_DELIVERY_REVIEWER','reason_code':reason,'reason_label':label,'question_db_id':question_id,
              'question_id':q.get('question_id'),'subject':q.get('subject'),'chapter':q.get('chapter'),'question_version':q.get('question_version'),
              'ph_question_id':q.get('ph_question_id'),'ph_question_version_id':q.get('ph_question_version_id'),
              'ph_release_id':q.get('ph_release_id'),'ph_release_version':q.get('ph_release_version'),
              'ph_question_checksum_sha256':q.get('ph_question_checksum_sha256'),'requested_action':'POWER_HOUSE_EXCEPTION',
              'withdrawal_authority':'POWER_HOUSE','reviewer_can_withdraw':False,'reviewer_can_edit':False,'page':page,
            }
            description=(f'{label}. '+notes).strip()
            import scoremax_ph_bridge_v6611d as ph_bridge_v6611d
            import scoremax_integration_v1 as integration_v1
            outbox_message_id=ph_bridge_v6611d.queue_reported_question_incident(conn,q,code,reason,severity,description,context)
            if not outbox_message_id:
                conn.rollback()
                flash('Power House incident handoff could not be queued. Nothing was changed.','error')
                return redirect(url_for('ux_content_review_question',question_id=question_id,view='reviewer'))
            conn.execute("""INSERT INTO pilot_feedback(feedback_code,reporter_user_id,category,severity,description,question_id,routing_target,status,context_json,page_path)
              VALUES(?,?,?,?,?,?,'Power House','QUEUED',?,?)""",
              (code,session['user_id'],'ACADEMIC_CONTENT',severity,description,question_id,json.dumps(context,sort_keys=True),page))
            conn.commit()
            dispatch=integration_v1.dispatch_due(conn,limit=20,timeout=8)
            row=conn.execute("SELECT status,last_error_code FROM integration_outbox WHERE message_id=?",(outbox_message_id,)).fetchone()
            delivery=str(row['status'] if row else 'UNKNOWN')
            error=str(row['last_error_code'] if row else '')
            local_status='DELIVERED_TO_POWER_HOUSE' if delivery=='DELIVERED' else ('QUEUED' if delivery in {'PENDING','RETRY','IN_FLIGHT'} else delivery)
            conn.execute("UPDATE pilot_feedback SET status=? WHERE feedback_code=?",(local_status,code)); conn.commit()
        finally: conn.close()
        if delivery=='DELIVERED':
            flash(f'Flag {code} delivered to Power House. ScoreMax made no academic change.','success')
        else:
            flash(f'Flag {code} is safely queued for Power House ({delivery}{": "+error if error else ""}). ScoreMax made no academic change.','warning')
        return redirect(url_for('ux_content_review_question',question_id=question_id,view='reviewer'))


    @app.route('/student/content-review/staged',methods=['GET'],endpoint='ux_content_review_staged')
    def ux_content_review_staged():
        _require_reviewer()
        subject=(request.args.get('subject') or '').strip()
        chapter=(request.args.get('chapter') or '').strip()
        search=(request.args.get('q') or '').strip().lower()
        batch=(request.args.get('batch') or '').strip().lower()
        conn=_connect()
        try:
            batch_rows=_filter_staged_rows(_staged_rows(conn),batch)
            questions=[]
            for row in batch_rows:
                q=_staged_question_dict(row)
                if subject and str(q.get('subject') or '').lower()!=subject.lower(): continue
                if chapter and str(q.get('chapter') or '').lower()!=chapter.lower(): continue
                if search and search not in str(q.get('public_id') or '').lower() and search not in str(q.get('question') or '').lower(): continue
                q['review_decision']=_staged_decision(conn,session['user_id'],q['membership_id'])
                questions.append(q)
                if len(questions)>=120: break
            all_q=[_staged_question_dict(r) for r in batch_rows]
            subjects=sorted({str(q.get('subject') or '') for q in all_q if str(q.get('subject') or '')})
            chapters=sorted({str(q.get('chapter') or '') for q in all_q if str(q.get('chapter') or '')})
            snap=_staged_boundary_snapshot(conn)
            human=_staged_decision_stats(conn,session['user_id'],[q['membership_id'] for q in all_q])
            flagged_count=conn.execute("SELECT COUNT(*) FROM pilot_feedback WHERE reporter_user_id=? AND category='ACADEMIC_CONTENT' AND context_json LIKE '%STAGED_POWER_HOUSE%'",(session['user_id'],)).fetchone()[0]
            open_count=conn.execute("SELECT COUNT(*) FROM pilot_feedback WHERE reporter_user_id=? AND category='ACADEMIC_CONTENT' AND context_json LIKE '%STAGED_POWER_HOUSE%' AND status NOT IN ('RESOLVED','CLOSED')",(session['user_id'],)).fetchone()[0]
        finally:
            conn.close()
        return render_template('ux_staged_content_review.html',questions=questions,subjects=subjects,chapters=chapters,
          filters={'subject':subject,'chapter':chapter,'q':request.args.get('q') or '','batch':batch},
          stats={'staged':len(all_q),'membership':len(all_q),'flagged':flagged_count,'open':open_count,
                 'reviewed':human['reviewed'],'approved':human['approved'],'rejected':human['rejected'],'remaining':human['remaining']},
          boundary=snap)

    @app.route('/student/content-review/staged/<int:membership_id>',methods=['GET'],endpoint='ux_content_review_staged_question')
    def ux_content_review_staged_question(membership_id):
        _require_reviewer()
        mode=(request.args.get('view') or 'student').strip().lower()
        batch=(request.args.get('batch') or '').strip().lower()
        if mode not in {'student','reviewer'}: mode='student'
        conn=_connect()
        try:
            q=_staged_question(conn,membership_id)
            if not q: abort(404)
            rows=_filter_staged_rows(_staged_rows(conn),batch)
            ids=[int(r['membership_id']) for r in rows]
            if int(membership_id) not in ids:
                abort(404)
            try: idx=ids.index(int(membership_id))
            except ValueError: idx=-1
            prev_id=ids[idx-1] if idx>0 else None
            next_id=ids[idx+1] if idx>=0 and idx+1<len(ids) else None
            flags=_staged_flags(conn,session['user_id'],q['ph_question_version_id'])
            decision=_staged_decision(conn,session['user_id'],membership_id)
            position=(idx+1) if idx>=0 else None
            total=len(ids)
            render_ctx,render_supported,_render_probe=_staged_canonical_surface_probe(q)
        finally:
            conn.close()
        return render_template('ux_staged_content_review_question.html',q=q,mode=mode,flags=flags,reasons=FLAG_REASONS,
          prev_id=prev_id,next_id=next_id,decision=decision,batch=batch,position=position,total=total,
          render_supported=render_supported,**render_ctx)

    @app.route('/student/content-review/staged/<int:membership_id>/decision',methods=['POST'],endpoint='ux_content_review_staged_decision')
    def ux_content_review_staged_decision(membership_id):
        _require_reviewer()
        decision=(request.form.get('decision') or '').strip().upper()
        batch=(request.form.get('batch') or '').strip().lower()
        reason=(request.form.get('reason') or '').strip().upper()
        note=(request.form.get('notes') or '').strip()[:3000]
        if decision not in {'APPROVED','REJECTED'}:
            flash('Choose Approve or Reject.','error')
            return redirect(url_for('ux_content_review_staged_question',membership_id=membership_id,view='reviewer',batch=batch))
        if decision=='REJECTED' and reason not in FLAG_REASONS:
            flash('Choose a valid rejection reason.','error')
            return redirect(url_for('ux_content_review_staged_question',membership_id=membership_id,view='reviewer',batch=batch))
        conn=_connect()
        delivery='NOT_REQUIRED'; error=''; code=''
        try:
            q=_staged_question(conn,membership_id)
            if not q:
                abort(404)
            batch_rows=_filter_staged_rows(_staged_rows(conn),batch)
            ids=[int(r['membership_id']) for r in batch_rows]
            if int(membership_id) not in ids:
                abort(404)
            if decision=='APPROVED':
                _ctx,_render_supported,_probe=_staged_canonical_surface_probe(q)
                if not _render_supported:
                    flash('Cannot approve this item: the canonical ScoreMax learner renderer did not produce an interactive response control.','error')
                    return redirect(url_for('ux_content_review_staged_question',membership_id=membership_id,view='reviewer',batch=batch))
            now=datetime.utcnow().replace(microsecond=0).isoformat()+'Z'
            if decision=='REJECTED':
                label,severity=FLAG_REASONS[reason]
                code='CRF-'+datetime.now().strftime('%Y%m%d%H%M%S')+'-'+secrets.token_hex(2).upper()
                page=f'/student/content-review/staged/{membership_id}'
                context={
                  'source':'SCOREMAX_DELIVERY_REVIEWER','review_source':'STAGED_POWER_HOUSE',
                  'human_review_decision':'REJECTED','reason_code':reason,'reason_label':label,
                  'staged_membership_id':membership_id,'ph_question_id':q['ph_question_id'],
                  'ph_question_version_id':q['ph_question_version_id'],'ph_release_id':q['ph_release_id'],
                  'ph_release_version':q['ph_release_version'],'ph_question_checksum_sha256':q['ph_question_checksum_sha256'],
                  'requested_action':'POWER_HOUSE_EXCEPTION','withdrawal_authority':'POWER_HOUSE',
                  'reviewer_can_withdraw':False,'reviewer_can_edit':False,'page':page,
                }
                description=(f'{label}. '+note).strip()
                outbox_message_id=_queue_staged_incident(conn,q,code,reason,severity,description,context)
                if not outbox_message_id:
                    conn.rollback()
                    flash('Power House rejection handoff could not establish exact staged lineage. Nothing was changed.','error')
                    return redirect(url_for('ux_content_review_staged_question',membership_id=membership_id,view='reviewer',batch=batch))
                conn.execute("""INSERT INTO pilot_feedback(feedback_code,reporter_user_id,category,severity,description,question_id,routing_target,status,context_json,page_path)
                  VALUES(?,?,?,?,?,NULL,'Power House','QUEUED',?,?)""",
                  (code,session['user_id'],'ACADEMIC_CONTENT',severity,description,json.dumps(context,sort_keys=True),page))
            conn.execute("""INSERT INTO staged_human_review_decisions_v1(
              membership_id,reviewer_user_id,question_id,question_version_id,release_id,release_version,decision,reason_code,note,decided_at
              ) VALUES(?,?,?,?,?,?,?,?,?,?)
              ON CONFLICT(membership_id,reviewer_user_id) DO UPDATE SET
                question_id=excluded.question_id,question_version_id=excluded.question_version_id,
                release_id=excluded.release_id,release_version=excluded.release_version,
                decision=excluded.decision,reason_code=excluded.reason_code,note=excluded.note,decided_at=excluded.decided_at""",
              (membership_id,session['user_id'],q['ph_question_id'],q['ph_question_version_id'],
               q['ph_release_id'],q['ph_release_version'],decision,reason if decision=='REJECTED' else '',
               note if decision=='REJECTED' else '',now))
            conn.commit()
            if decision=='REJECTED':
                import scoremax_integration_v1 as integration_v1
                integration_v1.dispatch_due(conn,limit=20,timeout=8)
                row=conn.execute("SELECT status,last_error_code FROM integration_outbox WHERE message_id=?",(outbox_message_id,)).fetchone()
                delivery=str(row['status'] if row else 'UNKNOWN')
                error=str(row['last_error_code'] if row else '')
                local_status='DELIVERED_TO_POWER_HOUSE' if delivery=='DELIVERED' else ('QUEUED' if delivery in {'PENDING','RETRY','IN_FLIGHT'} else delivery)
                conn.execute("UPDATE pilot_feedback SET status=? WHERE feedback_code=?",(local_status,code))
                conn.commit()
            try: idx=ids.index(int(membership_id))
            except ValueError: idx=-1
            next_id=ids[idx+1] if idx>=0 and idx+1<len(ids) else None
        finally:
            conn.close()
        if decision=='APPROVED':
            flash('Human QA decision recorded: Approved. No learner activation or release authority was conferred.','success')
        elif delivery=='DELIVERED':
            flash(f'Human QA decision recorded: Rejected. {code} delivered to Power House.','success')
        else:
            flash(f'Human QA decision recorded: Rejected. {code} queued for Power House ({delivery}{": "+error if error else ""}).','warning')
        if next_id:
            return redirect(url_for('ux_content_review_staged_question',membership_id=next_id,view='reviewer',batch=batch))
        return redirect(url_for('ux_content_review_staged',batch=batch))


    @app.route('/student/content-review/staged/<int:membership_id>/flag',methods=['POST'],endpoint='ux_content_review_staged_flag')
    def ux_content_review_staged_flag(membership_id):
        _require_reviewer()
        reason=(request.form.get('reason') or '').strip().upper()
        if reason not in FLAG_REASONS:
            flash('Choose a valid reason for the flag.','error')
            return redirect(url_for('ux_content_review_staged_question',membership_id=membership_id,view='reviewer'))
        notes=(request.form.get('notes') or '').strip()[:3000]
        label,severity=FLAG_REASONS[reason]
        conn=_connect()
        try:
            q=_staged_question(conn,membership_id)
            if not q:
                flash('This staged question is no longer eligible for review.','error')
                return redirect(url_for('ux_content_review_staged'))
            code='CRF-'+datetime.now().strftime('%Y%m%d%H%M%S')+'-'+secrets.token_hex(2).upper()
            page=f'/student/content-review/staged/{membership_id}'
            context={
              'source':'SCOREMAX_DELIVERY_REVIEWER','review_source':'STAGED_POWER_HOUSE',
              'reason_code':reason,'reason_label':label,'staged_membership_id':membership_id,
              'ph_question_id':q['ph_question_id'],'ph_question_version_id':q['ph_question_version_id'],
              'ph_release_id':q['ph_release_id'],'ph_release_version':q['ph_release_version'],
              'ph_question_checksum_sha256':q['ph_question_checksum_sha256'],
              'requested_action':'POWER_HOUSE_EXCEPTION','withdrawal_authority':'POWER_HOUSE',
              'reviewer_can_withdraw':False,'reviewer_can_edit':False,'page':page,
            }
            description=(f'{label}. '+notes).strip()
            outbox_message_id=_queue_staged_incident(conn,q,code,reason,severity,description,context)
            if not outbox_message_id:
                conn.rollback()
                flash('Power House incident handoff could not establish exact staged lineage. Nothing was changed.','error')
                return redirect(url_for('ux_content_review_staged_question',membership_id=membership_id,view='reviewer'))
            conn.execute("""INSERT INTO pilot_feedback(feedback_code,reporter_user_id,category,severity,description,question_id,routing_target,status,context_json,page_path)
              VALUES(?,?,?,?,?,NULL,'Power House','QUEUED',?,?)""",
              (code,session['user_id'],'ACADEMIC_CONTENT',severity,description,json.dumps(context,sort_keys=True),page))
            conn.commit()
            import scoremax_integration_v1 as integration_v1
            integration_v1.dispatch_due(conn,limit=20,timeout=8)
            row=conn.execute("SELECT status,last_error_code FROM integration_outbox WHERE message_id=?",(outbox_message_id,)).fetchone()
            delivery=str(row['status'] if row else 'UNKNOWN')
            error=str(row['last_error_code'] if row else '')
            local_status='DELIVERED_TO_POWER_HOUSE' if delivery=='DELIVERED' else ('QUEUED' if delivery in {'PENDING','RETRY','IN_FLIGHT'} else delivery)
            conn.execute("UPDATE pilot_feedback SET status=? WHERE feedback_code=?",(local_status,code)); conn.commit()
        finally:
            conn.close()
        if delivery=='DELIVERED':
            flash(f'Flag {code} delivered to Power House. ScoreMax made no academic or learner-state change.','success')
        else:
            flash(f'Flag {code} is safely queued for Power House ({delivery}{": "+error if error else ""}). ScoreMax made no academic or learner-state change.','warning')
        return redirect(url_for('ux_content_review_staged_question',membership_id=membership_id,view='reviewer'))


    @app.after_request
    def _ux_content_reviewer_nav(response):
        if not response.is_sequence or 'text/html' not in (response.content_type or '').lower(): return response
        if not _is_reviewer(): return response
        html=response.get_data(as_text=True)
        if 'ux-content-reviewer-nav-style' not in html:
            patch=_reviewer_nav_patch(); html=html.replace('</body>',patch+'</body>',1) if '</body>' in html else html+patch
            response.set_data(html); response.content_length=len(response.get_data())
        return response

    _diag_conn=_connect()
    try:
        _diag=_staged_boundary_snapshot(_diag_conn)
        print('SCOREMAX_STAGED_REVIEWER_BOUNDARY '+json.dumps(_diag,sort_keys=True,separators=(',',':')),flush=True)
        _matching=[]
        _rows=_diag_conn.execute("""SELECT m.id membership_id,v.question_id,v.question_version_id,v.content_json
          FROM integration_ph_release_question_membership m
          JOIN integration_ph_question_version_store v
            ON v.question_id=m.question_id AND v.question_version_id=m.question_version_id
          JOIN integration_ph_content_releases r
            ON r.release_id=m.release_id AND r.release_version=m.release_version
          WHERE r.local_status='STAGED'
            AND NOT EXISTS (
              SELECT 1 FROM ph_bridge_staged_withdrawal_exclusions_v6611e e
              WHERE e.release_id=m.release_id AND e.release_version=m.release_version
                AND e.question_id=m.question_id AND e.question_version_id=m.question_version_id
            )
          ORDER BY m.ordinal,m.id""").fetchall()
        for _r in _rows:
            try: _c=json.loads(_r['content_json'] or '{}')
            except Exception: _c={}
            _family=str(_c.get('question_family_type') or '')
            _exam=str(_c.get('exam_question_type') or '')
            _ped=str(_c.get('pedagogical_type') or '')
            _tokens='|'.join((_family,_exam,_ped)).upper()
            if 'MATCH' not in _tokens:
                continue
            _opts=[x for x in (_c.get('options') or []) if isinstance(x,dict)]
            _stmts=[str(x) for x in (_c.get('statements') or []) if str(x).strip()]
            _mark=_c.get('marking') or {}
            _matching.append({
              'membership_id':int(_r['membership_id']),
              'question_id':str(_r['question_id']),
              'question_version_id':str(_r['question_version_id']),
              'question_family_type':_family,
              'exam_question_type':_exam,
              'pedagogical_type':_ped,
              'key_type':str(_mark.get('key_type') or ''),
              'options_count':len(_opts),
              'nonempty_option_text_count':sum(1 for x in _opts if str(x.get('text') or '').strip()),
              'statements_count':len(_stmts),
              'option_ids':[str(x.get('option_id') or '') for x in _opts],
              'stimulus_ref':str(_c.get('stimulus_ref') or ''),
              'stimulus_type':type(_c.get('inline_stimulus')).__name__,
              'stimulus_keys':sorted(list((_c.get('inline_stimulus') or {}).keys())) if isinstance(_c.get('inline_stimulus'),dict) else [],
              'stimulus_text':str(((_c.get('inline_stimulus') or {}).get('text') if isinstance(_c.get('inline_stimulus'),dict) else '') or '')[:4000],
              'resolved_stimulus':None,
              'marking_key':_mark.get('key'),
              'accepted_answers':list(_mark.get('accepted_answers') or []),
            })
        if _matching:
            _stim_lookup={}
            _srows=_diag_conn.execute("""SELECT s.stimulus_id,s.stimulus_version_id,s.immutable_payload_json
              FROM integration_ph_stimulus_version_store s""").fetchall()
            for _sr in _srows:
                try: _sp=json.loads(_sr['immutable_payload_json'] or '{}')
                except Exception: _sp={}
                _stim_lookup[str(_sr['stimulus_id'])]={'stimulus_version_id':str(_sr['stimulus_version_id']),'payload':_sp}
            for _m in _matching:
                _ref=str(_m.get('stimulus_ref') or '')
                if _ref and _ref in _stim_lookup:
                    _sp=dict(_stim_lookup[_ref]['payload'] or {})
                    _content=_sp.get('content')
                    _m['resolved_stimulus']={
                      'stimulus_version_id':_stim_lookup[_ref]['stimulus_version_id'],
                      'payload_keys':sorted(list(_sp.keys())),
                      'content_type':type(_content).__name__,
                      'content':_content,
                    }
        print('SCOREMAX_STAGED_MATCHING_STRUCTURE_DIAG '+json.dumps({'count':len(_matching),'items':_matching},sort_keys=True,separators=(',',':')),flush=True)
    finally:
        _diag_conn.close()
    _render_diag_conn=_connect()
    try:
        _cross50=[_staged_question_dict(x) for x in _filter_staged_rows(_staged_rows(_render_diag_conn),'cross50')]
        _render_types={}
        _unsupported=[]
        if len(_cross50)>=45:
            _q45=_cross50[44]
            _src45=dict(_q45.get('_source_content') or {})
            _mark45=dict(_src45.get('marking') or {})
            print('SCOREMAX_CROSS50_Q45_SOURCE_DIAG '+json.dumps({
              'position':45,
              'membership_id':_q45.get('membership_id'),
              'question_id':_q45.get('ph_question_id'),
              'projected_qtype':_q45.get('qtype'),
              'question_family_type':_src45.get('question_family_type'),
              'exam_question_type':_src45.get('exam_question_type'),
              'pedagogical_type':_src45.get('pedagogical_type'),
              'stem':_src45.get('stem'),
              'options':_src45.get('options'),
              'statements':_src45.get('statements'),
              'marking_key_type':_mark45.get('key_type'),
              'marking_key':_mark45.get('key'),
              'accepted_answers':_mark45.get('accepted_answers'),
            },sort_keys=True,separators=(',',':')),flush=True)
        with app.test_request_context('/student/content-review/staged?batch=cross50'):
            for _q in _cross50:
                _ctx,_ok,_html=_staged_canonical_surface_probe(_q)
                _qt=str(_ctx.get('qtype') or '')
                _render_types[_qt]=_render_types.get(_qt,0)+1
                if not _ok:
                    _unsupported.append({'membership_id':_q.get('membership_id'),'question_id':_q.get('ph_question_id'),'qtype':_qt})
        print('SCOREMAX_CROSS50_CANONICAL_RENDER_DIAG '+json.dumps({
          'total':len(_cross50),'interactive':len(_cross50)-len(_unsupported),
          'unsupported_count':len(_unsupported),'qtypes':_render_types,'unsupported':_unsupported[:20],
          'same_component_as_live':True,'approval_fail_closed':True,
        },sort_keys=True,separators=(',',':')),flush=True)
    finally:
        _render_diag_conn.close()
    app._ux_content_reviewer_installed=True
