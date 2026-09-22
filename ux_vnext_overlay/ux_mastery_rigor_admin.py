from __future__ import annotations

import json
from flask import flash, redirect, render_template, request, session, url_for

DEFAULT_BREADTH={
    'Foundation':0.50,
    'Exam Ready':0.70,
    'Advanced':0.80,
    'Distinction':0.90,
    'Expert':0.95,
    'Elite':1.00,
}


def _ensure_col(conn, table, name, definition):
    cols={r[1] for r in conn.execute(f"PRAGMA table_info({table})").fetchall()}
    if name not in cols:
        conn.execute(f"ALTER TABLE {table} ADD COLUMN {name} {definition}")


def _coverage_tokens(scoremax, row):
    keys=set(row.keys()) if hasattr(row,'keys') else set()
    if 'ph_knowledge_node_ids_json' in keys:
        try:
            vals=json.loads(row['ph_knowledge_node_ids_json'] or '[]')
        except Exception:
            vals=[]
        out={f"KN::{str(x).strip()}" for x in vals if str(x).strip()}
        if out:
            return out
    for field,prefix in (
        ('learning_outcome','LO'),('subtopic','SUBTOPIC'),('topic','TOPIC'),
        ('family_id','FAMILY'),('question_id','QUESTION')
    ):
        if field in keys and str(row[field] or '').strip():
            return {f"{prefix}::{str(row[field]).strip()}"}
    return set()


def ensure_mastery_rigor_schema(scoremax):
    conn=scoremax.db()
    try:
        _ensure_col(conn,'mastery_policies','min_breadth_pct',"REAL NOT NULL DEFAULT 0")
        for level,value in DEFAULT_BREADTH.items():
            conn.execute("""UPDATE mastery_policies SET min_breadth_pct=?
              WHERE mastery_level=? AND (min_breadth_pct IS NULL OR min_breadth_pct=0)""",(value,level))
        conn.execute("""CREATE TABLE IF NOT EXISTS mastery_policy_change_audit_v1(
          id INTEGER PRIMARY KEY AUTOINCREMENT,
          mastery_level TEXT NOT NULL,
          actor_user_id INTEGER,
          previous_json TEXT NOT NULL DEFAULT '{}',
          new_json TEXT NOT NULL DEFAULT '{}',
          reason TEXT NOT NULL DEFAULT '',
          created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )""")
        conn.commit()
    finally:
        conn.close()


def install_mastery_rigor_admin(app):
    if getattr(app,'_ux_mastery_rigor_admin_installed',False):
        return
    import app as scoremax
    ensure_mastery_rigor_schema(scoremax)

    original_effective=scoremax.effective_mastery_requirements
    def effective_mastery_requirements_v2(base_policy,assembly_policy=None):
        out=dict(original_effective(base_policy,assembly_policy) or {})
        if not base_policy:
            return out
        base=dict(base_policy)
        standard=int(assembly_policy['mastery_standard_score'] or 50) if assembly_policy else 50
        delta=(max(0,min(100,standard))-50)/50.0
        base_breadth=float(base.get('min_breadth_pct') or 0)
        if base_breadth>0:
            out['min_breadth_pct']=round(max(0.25,min(1.0,base_breadth+0.10*delta)),3)
        else:
            out['min_breadth_pct']=0.0
        return out
    scoremax.effective_mastery_requirements=effective_mastery_requirements_v2

    original_build=scoremax.build_mastery_form
    def build_mastery_form_v2(c,student_id,scope_type,target_level,programme='',subject='',chapter=''):
        best=None
        best_ratio=-1.0
        last_error=None
        for _ in range(6):
            try:
                chosen,meta=original_build(c,student_id,scope_type,target_level,programme,subject,chapter)
            except Exception as exc:
                last_error=exc
                break
            effective=dict(meta.get('mastery_effective_policy') or {})
            required=float(effective.get('min_breadth_pct') or 0)
            if meta.get('mastery_demo_only') or required<=0:
                meta['mastery_breadth_ratio']=1.0 if chosen else 0.0
                meta['mastery_breadth_required_pct']=required
                return chosen,meta

            clauses=[scoremax.live_question_clause('q'),"COALESCE(q.is_demo,0)=0",
                     "COALESCE(q.calibration_status,'PROVISIONAL') NOT IN ('BLOCKED','REVIEW_NEGATIVE')"]
            params=[]
            if programme:
                clauses.append("(lower(COALESCE(q.programme,''))=lower(?) OR lower(COALESCE(q.qualification,''))=lower(?))")
                params.extend([programme,programme])
            if subject:
                clauses.append("q.subject=?"); params.append(subject)
            if str(scope_type or '').lower()=='chapter' and chapter:
                clauses.append("q.chapter=?"); params.append(chapter)
            pool=c.execute(f"SELECT q.* FROM questions q WHERE {' AND '.join(clauses)}",params).fetchall()
            pool=[r for r in pool if scoremax.canonical_question_type(r) in scoremax.LIVE_MARKABLE_TYPES
                  and scoremax.mastery_rank(r['level'] or 'Foundation')<=scoremax.mastery_rank(target_level)]
            available=set()
            for row in pool:
                available.update(_coverage_tokens(scoremax,row))
            covered=set()
            for row in chosen:
                covered.update(_coverage_tokens(scoremax,row))
            ratio=round(len(covered)/len(available),3) if available else 1.0
            if ratio>best_ratio:
                best=(chosen,dict(meta)); best_ratio=ratio
            if ratio+1e-9>=required:
                meta=dict(meta)
                meta['mastery_breadth_ok']=True
                meta['mastery_breadth_ratio']=ratio
                meta['mastery_breadth_required_pct']=required
                meta['mastery_breadth_covered']=len(covered)
                meta['mastery_breadth_required']=max(1,int(round(len(available)*required))) if available else 1
                meta['mastery_breadth_unit']='knowledge-node/learning-outcome coverage'
                return chosen,meta
        if last_error is not None:
            raise last_error
        if best is not None:
            chosen,meta=best
            required=float((meta.get('mastery_effective_policy') or {}).get('min_breadth_pct') or 0)
            meta['mastery_breadth_ok']=False
            meta['mastery_breadth_ratio']=best_ratio
            raise ValueError(
              f'This mastery form cannot yet meet the configured breadth standard '
              f'({round(best_ratio*100)}% available coverage represented; {round(required*100)}% required). '
              'Add broader approved Power House question coverage or adjust the governed mastery rule.'
            )
        raise ValueError('A mastery form could not be assembled.')
    scoremax.build_mastery_form=build_mastery_form_v2

    @app.route('/admin/mastery-rigor',methods=['GET'],endpoint='admin_mastery_rigor')
    def admin_mastery_rigor():
        if not scoremax.require('admin'):
            return redirect(url_for('login'))
        c=scoremax.db()
        try:
            level_rows=[dict(r) for r in c.execute(
              "SELECT * FROM mastery_policies WHERE active=1 ORDER BY level_rank").fetchall()]
            policy_rows=c.execute("""SELECT ap.*,ab.powerhouse_blueprint_id,
              af.name framework_name,afv.version_name framework_version_name
              FROM assessment_assembly_policies ap
              LEFT JOIN assessment_blueprints ab ON ab.id=ap.blueprint_id
              LEFT JOIN assessment_framework_versions afv ON afv.id=ap.framework_version_id
              LEFT JOIN assessment_frameworks af ON af.id=afv.framework_id
              ORDER BY CASE ap.status WHEN 'ACTIVE' THEN 0 WHEN 'DRAFT' THEN 1 ELSE 2 END,
                       ap.created_at DESC LIMIT 50""").fetchall()
            policies=[]
            for row in policy_rows:
                item=dict(row); item['preview']=scoremax.safe_json(row['preview_json'],{}); policies.append(item)
            blueprints=c.execute("""SELECT ab.id,ab.powerhouse_blueprint_id,ab.blueprint_version,
              af.name framework_name,afv.version_name framework_version_name,ab.local_status
              FROM assessment_blueprints ab
              JOIN assessment_frameworks af ON af.id=ab.framework_id
              JOIN assessment_framework_versions afv ON afv.id=ab.framework_version_id
              ORDER BY ab.imported_at DESC,ab.id DESC""").fetchall()
            active_global=next((p for p in policies if p['status']=='ACTIVE' and p['scope_type']=='global'),None)
            audit=c.execute("""SELECT * FROM mastery_policy_change_audit_v1
              ORDER BY id DESC LIMIT 20""").fetchall()
        finally:
            c.close()
        return render_template('admin_mastery_rigor.html',
          levels=level_rows,policies=policies,blueprints=blueprints,
          active_global=active_global,audit=audit)

    @app.route('/admin/mastery-rigor/level',methods=['POST'],endpoint='admin_mastery_rigor_level')
    def admin_mastery_rigor_level():
        if not scoremax.require('admin'):
            return redirect(url_for('login'))
        level=(request.form.get('mastery_level') or '').strip()
        if level not in scoremax.MASTER_LEVELS:
            flash('Choose a valid mastery level.','error')
            return redirect(url_for('admin_mastery_rigor'))
        reason=(request.form.get('reason') or '').strip()
        if not reason:
            flash('A reason is required for mastery-policy changes.','error')
            return redirect(url_for('admin_mastery_rigor'))
        try:
            values={
              'min_forms':max(1,int(request.form.get('min_forms') or 1)),
              'min_questions':max(5,int(request.form.get('min_questions') or 10)),
              'min_accuracy':max(0,min(100,float(request.form.get('min_accuracy') or 70))),
              'verification_days':max(1,int(request.form.get('verification_days') or 90)),
              'external_percentile_target':float(request.form.get('external_percentile_target')) if (request.form.get('external_percentile_target') or '').strip() else None,
              'target_band_pct':max(0,min(1,float(request.form.get('target_band_pct') or .25))),
              'unseen_family_pct':max(0,min(1,float(request.form.get('unseen_family_pct') or .60))),
              'min_breadth_pct':max(0,min(1,float(request.form.get('min_breadth_pct') or 0))),
            }
        except ValueError:
            flash('Check the mastery-rule numbers and try again.','error')
            return redirect(url_for('admin_mastery_rigor'))
        c=scoremax.db()
        try:
            row=c.execute("SELECT * FROM mastery_policies WHERE mastery_level=?",(level,)).fetchone()
            if not row:
                flash('Mastery policy not found.','error')
                return redirect(url_for('admin_mastery_rigor'))
            before=dict(row)
            c.execute("""UPDATE mastery_policies SET min_forms=?,min_questions=?,min_accuracy=?,
              verification_days=?,external_percentile_target=?,target_band_pct=?,
              unseen_family_pct=?,min_breadth_pct=?,updated_at=CURRENT_TIMESTAMP
              WHERE mastery_level=?""",
              (values['min_forms'],values['min_questions'],values['min_accuracy'],values['verification_days'],
               values['external_percentile_target'],values['target_band_pct'],values['unseen_family_pct'],
               values['min_breadth_pct'],level))
            c.execute("""INSERT INTO mastery_policy_change_audit_v1(
              mastery_level,actor_user_id,previous_json,new_json,reason)
              VALUES(?,?,?,?,?)""",(level,session.get('user_id'),
              json.dumps(before,sort_keys=True,default=str),json.dumps(values,sort_keys=True),reason))
            c.commit()
        finally:
            c.close()
        flash(f'{level} mastery rule updated. Future forms use the new rule; historical attempts are unchanged.','success')
        return redirect(url_for('admin_mastery_rigor'))

    app._ux_mastery_rigor_admin_installed=True
