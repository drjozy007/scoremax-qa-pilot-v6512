from __future__ import annotations

import csv
import io
import os
import shutil
import sqlite3
from pathlib import Path

from flask import Response, flash, redirect, render_template, request, session, url_for

ALLOWED_STATUSES=("NEW","CONTACTED","CONVERTED")

TEMPLATE=r'''{% extends 'base.html' %}{% block title %}Interest & Demand · Admin{% endblock %}{% block content %}
<section class="page-shell ux-interest-admin">
  <section class="card page-intro"><p class="eyebrow">ADMIN · INTEREST & DEMAND</p><h1>Interest & Demand</h1><p class="muted">One operational view of registrations of interest across ScoreMax programmes, events and community opportunities. This is demand evidence, not enrolment or payment.</p></section>

  <section class="grid4 ux-interest-metrics">
    <div class="metric"><span>Total interest</span><strong>{{metrics.total}}</strong></div>
    <div class="metric"><span>New</span><strong>{{metrics.new_count}}</strong></div>
    <div class="metric"><span>Contacted</span><strong>{{metrics.contacted_count}}</strong></div>
    <div class="metric"><span>Converted</span><strong>{{metrics.converted_count}}</strong></div>
  </section>

  <section class="card"><div class="split"><div><p class="eyebrow">DEMAND SIGNAL</p><h2>Interest by programme</h2></div><a class="btn alt small" href="{{url_for('admin_interest_export',programme=filters.programme,role=filters.role,city=filters.city,status=filters.status,q=filters.q)}}">Export filtered CSV</a></div>
    <div class="table-wrap"><table><tr><th>Programme / opportunity</th><th>Total</th><th>New</th><th>Contacted</th><th>Converted</th></tr>{% for row in demand %}<tr><td><strong>{{row.programme}}</strong></td><td>{{row.total}}</td><td>{{row.new_count}}</td><td>{{row.contacted_count}}</td><td>{{row.converted_count}}</td></tr>{% else %}<tr><td colspan="5">No interest registrations yet.</td></tr>{% endfor %}</table></div>
  </section>

  <section class="card"><p class="eyebrow">FILTER</p><form method="get" action="{{url_for('admin_interests')}}" class="form-grid ux-interest-filter">
    <label>Programme<select name="programme"><option value="">All</option>{% for x in programmes %}<option value="{{x}}" {{'selected' if filters.programme==x else ''}}>{{x}}</option>{% endfor %}</select></label>
    <label>Role<select name="role"><option value="">All</option>{% for x in roles %}<option value="{{x}}" {{'selected' if filters.role==x else ''}}>{{x}}</option>{% endfor %}</select></label>
    <label>City<select name="city"><option value="">All</option>{% for x in cities %}<option value="{{x}}" {{'selected' if filters.city==x else ''}}>{{x}}</option>{% endfor %}</select></label>
    <label>Status<select name="status"><option value="">All</option>{% for x in allowed_statuses %}<option value="{{x}}" {{'selected' if filters.status==x else ''}}>{{x|title}}</option>{% endfor %}</select></label>
    <label class="full">Search<input name="q" value="{{filters.q}}" placeholder="Name, email, mobile or school"></label>
    <div class="full actions"><button class="btn">Apply filters</button><a class="btn alt" href="{{url_for('admin_interests')}}">Clear</a></div>
  </form></section>

  <section class="card"><div class="split"><div><p class="eyebrow">REGISTRATIONS</p><h2>Latest interest records</h2></div><span class="pill">Showing up to 500 records</span></div>
    <div class="table-wrap"><table class="ux-interest-table"><tr><th>Date</th><th>Interest</th><th>Person</th><th>Location / school</th><th>Contact</th><th>Status</th><th>Action</th></tr>
      {% for r in rows %}<tr>
        <td>{{r.created_at}}</td><td><strong>{{r.programme}}</strong><br><small>{{r.role}}</small></td>
        <td><strong>{{r.full_name}}</strong>{% if r.note %}<details><summary>Note</summary><small>{{r.note}}</small></details>{% endif %}</td>
        <td>{{r.city or '—'}}{% if r.school %}<br><small>{{r.school}}</small>{% endif %}</td>
        <td>{% if r.email %}{{r.email}}{% endif %}{% if r.mobile %}<br>{{r.mobile}}{% endif %}{% if not r.email and not r.mobile %}—{% endif %}</td>
        <td><span class="status-pill {{'good' if r.status=='CONVERTED' else ('mid' if r.status=='CONTACTED' else '')}}">{{r.status|title}}</span>{% if r.admin_note %}<br><small>{{r.admin_note}}</small>{% endif %}</td>
        <td><form method="post" action="{{url_for('admin_interest_status',interest_id=r.id)}}" class="mini-admin-form"><input type="hidden" name="_csrf_token" value="{{csrf_token()}}"><input type="hidden" name="return_to" value="{{request.full_path}}"><select name="status">{% for x in allowed_statuses %}<option value="{{x}}" {{'selected' if r.status==x else ''}}>{{x|title}}</option>{% endfor %}</select><input name="admin_note" value="{{r.admin_note or ''}}" placeholder="Optional note" maxlength="500"><button class="btn small alt">Save</button></form></td>
      </tr>{% else %}<tr><td colspan="7">No matching interest registrations.</td></tr>{% endfor %}
    </table></div>
  </section>
</section>
<style id="ux-interest-admin-style">
.ux-interest-admin{max-width:1220px}.ux-interest-metrics .metric{display:flex;flex-direction:column;gap:7px;min-height:92px}.ux-interest-metrics .metric span{color:#62736f;font-size:.78rem}.ux-interest-metrics .metric strong{font-size:1.75rem;color:#173f3d}.ux-interest-filter{align-items:end}.ux-interest-table td{vertical-align:top}.ux-interest-table .mini-admin-form{min-width:180px}.ux-interest-table .mini-admin-form input,.ux-interest-table .mini-admin-form select{width:100%;margin-bottom:6px}
</style>
{% endblock %}'''


def _db_path() -> Path:
    return Path(os.environ.get("SCOREMAX_DB","/tmp/scoremax-ux-vnext/state/scoremax.db"))


def _connect() -> sqlite3.Connection:
    path=_db_path(); path.parent.mkdir(parents=True,exist_ok=True)
    conn=sqlite3.connect(path); conn.row_factory=sqlite3.Row
    conn.execute("PRAGMA foreign_keys=ON"); conn.execute("PRAGMA busy_timeout=5000")
    return conn


def ensure_interest_schema() -> None:
    conn=_connect()
    try:
        conn.execute('''CREATE TABLE IF NOT EXISTS ux_interest_registrations(
          id INTEGER PRIMARY KEY,
          programme TEXT NOT NULL,
          full_name TEXT NOT NULL,
          email TEXT,
          mobile TEXT,
          role TEXT NOT NULL,
          school TEXT,
          city TEXT,
          note TEXT,
          status TEXT NOT NULL DEFAULT 'NEW',
          admin_note TEXT,
          status_updated_at TEXT,
          status_updated_by INTEGER,
          created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )''')
        cols={str(r['name']) for r in conn.execute('PRAGMA table_info(ux_interest_registrations)').fetchall()}
        additions={
            'status':"TEXT NOT NULL DEFAULT 'NEW'",
            'admin_note':'TEXT',
            'status_updated_at':'TEXT',
            'status_updated_by':'INTEGER',
        }
        for name,definition in additions.items():
            if name not in cols:
                conn.execute(f'ALTER TABLE ux_interest_registrations ADD COLUMN {name} {definition}')
        conn.execute("UPDATE ux_interest_registrations SET status='NEW' WHERE status IS NULL OR trim(status)='' OR upper(status) NOT IN ('NEW','CONTACTED','CONVERTED')")
        conn.execute('CREATE INDEX IF NOT EXISTS idx_ux_interest_programme ON ux_interest_registrations(programme)')
        conn.execute('CREATE INDEX IF NOT EXISTS idx_ux_interest_email ON ux_interest_registrations(lower(email))')
        conn.execute('CREATE INDEX IF NOT EXISTS idx_ux_interest_status ON ux_interest_registrations(status)')
        conn.execute('CREATE INDEX IF NOT EXISTS idx_ux_interest_role ON ux_interest_registrations(role)')
        conn.execute('CREATE INDEX IF NOT EXISTS idx_ux_interest_city ON ux_interest_registrations(city)')
        conn.execute('CREATE INDEX IF NOT EXISTS idx_ux_interest_created ON ux_interest_registrations(created_at)')
        conn.commit()
    finally:
        conn.close()


def _admin_only():
    if not session.get('user_id') or session.get('role')!='admin':
        return redirect(url_for('login'))
    return None


def _filters() -> dict[str,str]:
    return {k:(request.args.get(k) or '').strip()[:180] for k in ('programme','role','city','status','q')}


def _where(filters: dict[str,str]) -> tuple[str,list[str]]:
    clauses=[]; params=[]
    for key,column in (('programme','programme'),('role','role'),('city','city'),('status','status')):
        value=filters.get(key,'')
        if value:
            clauses.append(f'lower(COALESCE({column},\'\'))=lower(?)'); params.append(value)
    q=filters.get('q','')
    if q:
        like=f'%{q.lower()}%'
        clauses.append("(lower(COALESCE(full_name,'')) LIKE ? OR lower(COALESCE(email,'')) LIKE ? OR lower(COALESCE(mobile,'')) LIKE ? OR lower(COALESCE(school,'')) LIKE ?)")
        params.extend([like,like,like,like])
    return (' WHERE '+' AND '.join(clauses) if clauses else ''),params


def _csv_response(rows) -> Response:
    out=io.StringIO(newline='')
    writer=csv.writer(out)
    writer.writerow(['id','created_at','programme','role','full_name','email','mobile','school','city','note','status','admin_note','status_updated_at','status_updated_by'])
    for r in rows:
        writer.writerow([r['id'],r['created_at'],r['programme'],r['role'],r['full_name'],r['email'],r['mobile'],r['school'],r['city'],r['note'],r['status'],r['admin_note'],r['status_updated_at'],r['status_updated_by']])
    return Response(out.getvalue(),mimetype='text/csv',headers={'Content-Disposition':'attachment; filename=scoremax_interest_demand.csv'})


def install_interest_admin(app) -> None:
    ensure_interest_schema()
    if 'admin_interests' in app.view_functions:
        return

    @app.route('/admin/interests',methods=['GET'],endpoint='admin_interests')
    def admin_interests():
        guard=_admin_only()
        if guard: return guard
        filters=_filters(); where,params=_where(filters)
        conn=_connect()
        try:
            metrics=conn.execute("""SELECT COUNT(*) total,
              SUM(CASE WHEN status='NEW' THEN 1 ELSE 0 END) new_count,
              SUM(CASE WHEN status='CONTACTED' THEN 1 ELSE 0 END) contacted_count,
              SUM(CASE WHEN status='CONVERTED' THEN 1 ELSE 0 END) converted_count
              FROM ux_interest_registrations""").fetchone()
            demand=conn.execute("""SELECT programme,COUNT(*) total,
              SUM(CASE WHEN status='NEW' THEN 1 ELSE 0 END) new_count,
              SUM(CASE WHEN status='CONTACTED' THEN 1 ELSE 0 END) contacted_count,
              SUM(CASE WHEN status='CONVERTED' THEN 1 ELSE 0 END) converted_count
              FROM ux_interest_registrations GROUP BY programme ORDER BY total DESC,programme LIMIT 100""").fetchall()
            rows=conn.execute('SELECT * FROM ux_interest_registrations'+where+' ORDER BY id DESC LIMIT 500',params).fetchall()
            programmes=[r[0] for r in conn.execute("SELECT DISTINCT programme FROM ux_interest_registrations WHERE trim(COALESCE(programme,''))<>'' ORDER BY programme").fetchall()]
            roles=[r[0] for r in conn.execute("SELECT DISTINCT role FROM ux_interest_registrations WHERE trim(COALESCE(role,''))<>'' ORDER BY role").fetchall()]
            cities=[r[0] for r in conn.execute("SELECT DISTINCT city FROM ux_interest_registrations WHERE trim(COALESCE(city,''))<>'' ORDER BY city LIMIT 250").fetchall()]
        finally:
            conn.close()
        metric_payload={'total':int(metrics['total'] or 0),'new_count':int(metrics['new_count'] or 0),'contacted_count':int(metrics['contacted_count'] or 0),'converted_count':int(metrics['converted_count'] or 0)}
        return render_template('admin_interest_demand.html',metrics=metric_payload,demand=demand,rows=rows,programmes=programmes,roles=roles,cities=cities,filters=filters,allowed_statuses=ALLOWED_STATUSES)

    @app.route('/admin/interests/<int:interest_id>/status',methods=['POST'],endpoint='admin_interest_status')
    def admin_interest_status(interest_id: int):
        guard=_admin_only()
        if guard: return guard
        status=(request.form.get('status') or '').strip().upper()
        note=(request.form.get('admin_note') or '').strip()[:500]
        if status not in ALLOWED_STATUSES:
            flash('Invalid interest status.','error')
            return redirect(url_for('admin_interests'))
        conn=_connect()
        try:
            row=conn.execute('SELECT id FROM ux_interest_registrations WHERE id=?',(interest_id,)).fetchone()
            if row:
                conn.execute("UPDATE ux_interest_registrations SET status=?,admin_note=?,status_updated_at=CURRENT_TIMESTAMP,status_updated_by=? WHERE id=?",(status,note,session.get('user_id'),interest_id))
                conn.commit()
        finally:
            conn.close()
        return_to=(request.form.get('return_to') or '').strip()
        if not return_to.startswith('/admin/interests'):
            return_to=url_for('admin_interests')
        return redirect(return_to)

    @app.route('/admin/interests/export.csv',methods=['GET'],endpoint='admin_interest_export')
    def admin_interest_export():
        guard=_admin_only()
        if guard: return guard
        filters=_filters(); where,params=_where(filters)
        conn=_connect()
        try:
            rows=conn.execute('SELECT * FROM ux_interest_registrations'+where+' ORDER BY id DESC',params).fetchall()
        finally:
            conn.close()
        return _csv_response(rows)


def apply_interest_admin(root: Path) -> None:
    runtime_module=root/'ux_interest_admin.py'
    shutil.copy2(Path(__file__),runtime_module)
    template=root/'templates'/'admin_interest_demand.html'
    template.write_text(TEMPLATE,encoding='utf-8')
    app_path=root/'app.py'
    text=app_path.read_text(encoding='utf-8')
    marker='from ux_interest_admin import install_interest_admin\ninstall_interest_admin(app)'
    if marker not in text:
        anchor="\nif __name__=='__main__':\n"
        if anchor not in text:
            raise SystemExit('UX_INTEREST_ADMIN_APP_INSTALL_ANCHOR_MISSING')
        text=text.replace(anchor,'\n'+marker+'\n'+anchor,1)
        app_path.write_text(text,encoding='utf-8')
    if marker not in app_path.read_text(encoding='utf-8'):
        raise SystemExit('UX_INTEREST_ADMIN_INSTALL_CONTROL_MISSING')
    print('SCOREMAX_UX_INTEREST_ADMIN_PASS same_scoremax_db=true status_workflow=true csv_export=true filters=true',flush=True)
