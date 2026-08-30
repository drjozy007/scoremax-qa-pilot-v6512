"""Timed V6.4 Emergency Direct Intake scale gate: real 3,000-row XLSX -> preview -> Draft import -> governed release."""
from __future__ import annotations
import io, os, tempfile, time
from pathlib import Path
from openpyxl import Workbook
from smoke_tests_v5_5 import install_framework_stubs
_, request=install_framework_stubs()
ROOT=Path(__file__).resolve().parent; TMP=Path(tempfile.mkdtemp(prefix='scoremax_v640_scale3000_'))
os.environ['SCOREMAX_DB']=str(TMP/'scoremax.db'); os.environ['SCOREMAX_BACKUP_DIR']=str(TMP/'backups'); os.environ['SCOREMAX_CONTENT_INTAKE_DIR']=str(TMP/'intake')
import app
app.init(); c=app.db(); admin=c.execute("SELECT id FROM users WHERE role='admin' ORDER BY id LIMIT 1").fetchone()['id']; c.close(); app.session.clear(); app.session.update({'user_id':admin,'role':'admin'})

wb=Workbook(); intro=wb.active; intro.title='Instructions'; intro.append(['Reference only']);
ws=wb.create_sheet('Questions')
ws.append(['Question ID','Family ID','Programme','Subject','Chapter','Type','Question / Task','A','B','C','D','Key Answer','Explanation / Marking Rubric','Mastery','Difficulty','Rights Status','ScoreMax Ready','Status','Reviewer 2 Required','Assessment Purpose'])
for i in range(3000):
    ws.append([f'SCALE-Q-{i+1:04d}',f'SCALE-F-{i+1:04d}','FSc Part 1','Chemistry','Chapter 1','MCQ',f'Scale question {i+1}?','A','B','C','D','A','Scale governed explanation','Foundation','Moderate','ScoreMax Original','Yes','Approved','No','practice|test|mastery'])
buf=io.BytesIO(); wb.save(buf); payload=buf.getvalue(); wb.close()
class Upload:
    def __init__(self): self.filename='scoremax_scale_3000.xlsx'
    def read(self): return payload

def tick(label,fn):
    t=time.perf_counter(); result=fn(); dt=time.perf_counter()-t; print(f'{label}: {dt:.3f}s'); return result,dt
request.method='POST'; request.files={'file':Upload()}; request.args={'mode':'emergency'}; request.form={'intake_mode':'EMERGENCY_DIRECT','source_system':'EMERGENCY_APPROVED_WORKBOOK','source_prompt_pack_id':'SCALE-3000','source_prompt_pack_version':'1'}
_,preview_s=tick('preview+validate+persist',app.admin_import)
c=app.db(); batch=c.execute("SELECT * FROM content_import_batches WHERE source_prompt_pack_id='SCALE-3000' ORDER BY id DESC LIMIT 1").fetchone(); assert batch and batch['row_count']==3000 and batch['error_count']==0, dict(batch) if batch else None; c.close()
request.form={'batch_id':str(batch['id'])}; _,import_s=tick('atomic Draft/inactive import',app.admin_import_confirm)
c=app.db(); imported=c.execute('SELECT COUNT(*) n FROM questions WHERE source_import_batch_id=?',(batch['id'],)).fetchone()['n']; live_before=c.execute(f"SELECT COUNT(*) n FROM questions q WHERE q.source_import_batch_id=? AND {app.live_question_clause('q')}",(batch['id'],)).fetchone()['n']; c.close(); assert imported==3000 and live_before==0
request.form={'attestation':'I CONFIRM THIS IS A FROZEN ACADEMICALLY APPROVED RELEASE','release_note':'3,000-row scale qualification'}; _,release_s=tick('eligible governed release',lambda:app.admin_import_release_eligible(batch['id']))
c=app.db(); live_after=c.execute(f"SELECT COUNT(*) n FROM questions q WHERE q.source_import_batch_id=? AND {app.live_question_clause('q')}",(batch['id'],)).fetchone()['n']; b=c.execute('SELECT released_count,release_status FROM content_import_batches WHERE id=?',(batch['id'],)).fetchone(); integrity=c.execute('PRAGMA integrity_check').fetchone()[0]; c.close()
assert live_after==3000 and b['released_count']==3000 and b['release_status']=='RELEASED_ELIGIBLE' and integrity=='ok'
print(f'PASS: 3,000-row XLSX end-to-end: preview={preview_s:.3f}s import={import_s:.3f}s release={release_s:.3f}s live={live_after} integrity={integrity}')
