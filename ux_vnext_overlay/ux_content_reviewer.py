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
    if not uid or session.get('role')!='student':
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


def _reviewer_nav_patch() -> str:
    return r'''<style id="ux-content-reviewer-nav-style">.ux-review-nav{background:#fff7e6!important;color:#6f4a00!important;border-radius:9px!important;font-weight:900!important}.ux-reviewer-badge{display:inline-flex;align-items:center;gap:5px;padding:4px 7px;border-radius:999px;background:#fff7e6;color:#6f4a00;font-size:.62rem;font-weight:900}</style><script id="ux-content-reviewer-nav">(function(){function add(){const nav=document.querySelector('.site-header .desktop-nav');const account=nav&&nav.querySelector('.student-account-menu');if(nav&&account&&!nav.querySelector('.ux-review-nav')){const a=document.createElement('a');a.className='ux-review-nav'+(location.pathname.startsWith('/student/content-review')?' active':'');a.href='/student/content-review';a.textContent='Review';nav.insertBefore(a,account);}const menu=document.querySelector('.student-account-dropdown');if(menu&&!menu.querySelector('.ux-review-menu')){const a=document.createElement('a');a.className='ux-review-menu';a.href='/student/content-review';a.textContent='Review Questions';menu.insertBefore(a,menu.firstElementChild?.nextSibling||null);}}function later(){setTimeout(add,30);setTimeout(add,180);}if(document.readyState==='loading')document.addEventListener('DOMContentLoaded',later);else later();})();</script>'''


def install_content_reviewer(app) -> None:
    if getattr(app,'_ux_content_reviewer_installed',False): return
    _ensure_reviewer_schema_and_account()

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
            rows=conn.execute(f"SELECT q.* FROM questions q WHERE {where} ORDER BY q.id DESC LIMIT 120",params).fetchall()
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
            label,severity=FLAG_REASONS[reason]
            code='CRF-'+datetime.now().strftime('%Y%m%d%H%M%S')+'-'+secrets.token_hex(2).upper()
            context={
              'source':'SCOREMAX_CONTENT_REVIEWER','reason_code':reason,'reason_label':label,'question_db_id':question_id,
              'question_id':q.get('question_id'),'subject':q.get('subject'),'chapter':q.get('chapter'),'question_version':q.get('question_version'),
              'ph_question_id':q.get('ph_question_id'),'ph_question_version_id':q.get('ph_question_version_id'),
              'ph_release_id':q.get('ph_release_id'),'ph_release_version':q.get('ph_release_version'),
              'ph_question_checksum_sha256':q.get('ph_question_checksum_sha256'),'requested_action':'ACADEMIC_REVIEW',
              'withdrawal_authority':'POWER_HOUSE','reviewer_can_withdraw':False,
            }
            description=(f'{label}. '+notes).strip()
            conn.execute("""INSERT INTO pilot_feedback(feedback_code,reporter_user_id,category,severity,description,question_id,routing_target,status,context_json,page_path)
              VALUES(?,?,?,?,?,?,'Power House','OPEN',?,?)""",
              (code,session['user_id'],'ACADEMIC_CONTENT',severity,description,question_id,json.dumps(context,sort_keys=True),f'/student/content-review/question/{question_id}'))
            conn.commit()
        finally: conn.close()
        flash(f'Flag {code} recorded and routed to Power House for academic review. The reviewer cannot withdraw the question.','success')
        return redirect(url_for('ux_content_review_question',question_id=question_id,view='reviewer'))

    @app.after_request
    def _ux_content_reviewer_nav(response):
        if not response.is_sequence or 'text/html' not in (response.content_type or '').lower(): return response
        if not _is_reviewer(): return response
        html=response.get_data(as_text=True)
        if 'ux-content-reviewer-nav-style' not in html:
            patch=_reviewer_nav_patch(); html=html.replace('</body>',patch+'</body>',1) if '</body>' in html else html+patch
            response.set_data(html); response.content_length=len(response.get_data())
        return response

    app._ux_content_reviewer_installed=True
