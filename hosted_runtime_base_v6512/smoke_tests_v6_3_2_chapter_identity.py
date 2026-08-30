from release_compatibility import is_compatible_descendant
"""ScoreMax V6.3.2 governed chapter identity checks."""
import os, tempfile
from pathlib import Path
from smoke_tests_v5_5 import install_framework_stubs
install_framework_stubs()
ROOT=Path(__file__).resolve().parent
os.environ['SCOREMAX_DB']=str(Path(tempfile.mkdtemp(prefix='scoremax_v632_chapters_'))/'scoremax.db')
import app

n=0
def ok(name, condition):
    global n
    if not condition: raise AssertionError(name)
    n+=1; print('PASS:',name)

# Parsing is deterministic and never guesses missing academic metadata.
a=app.parse_chapter_identity('Chapter 3 — Chemical Bonding')
ok('explicit chapter number and name parse from the source label',a['chapter_number']=='3' and a['chapter_name']=='Chemical Bonding' and a['display_label']=='Chapter 3 — Chemical Bonding')
a=app.parse_chapter_identity('Cell Biology')
ok('title-only source remains a chapter name without inventing a number',a['chapter_number']=='' and a['chapter_name']=='Cell Biology' and a['display_label']=='Cell Biology')
a=app.parse_chapter_identity('Chapter 7')
ok('number-only source remains unresolved rather than inventing a name',a['chapter_number']=='7' and a['chapter_name']=='' and a['display_label']=='Chapter 7')

app.init(); c=app.db()
ok('chapter catalogue exists on a fresh V6.3.2 database','chapter_catalogue' in {r['name'] for r in c.execute("SELECT name FROM sqlite_master WHERE type='table'")})
cell=app.chapter_identity(c,'FSc Part 1','Biology','Cell Biology')
ok('fresh seed chapter is backfilled into the chapter catalogue',cell['chapter_name']=='Cell Biology' and cell['display_label']=='Cell Biology')

app.upsert_chapter_catalogue(c,'FSc Part 1','Chemistry','Chapter 3','3','Chemical Bonding',metadata_source='GOVERNED_IMPORT',review_status='Approved')
gov=app.chapter_identity(c,'FSc Part 1','Chemistry','Chapter 3')
ok('governed metadata produces Chapter number plus chapter name',gov['chapter']=='Chapter 3' and gov['chapter_number']=='3' and gov['chapter_name']=='Chemical Bonding' and gov['display_label']=='Chapter 3 — Chemical Bonding')
app.upsert_chapter_catalogue(c,'FSc Part 1','Chemistry','Chapter 3')
gov2=app.chapter_identity(c,'FSc Part 1','Chemistry','Chapter 3')
ok('derived backfill cannot overwrite governed chapter metadata',gov2['display_label']=='Chapter 3 — Chemical Bonding' and gov2['metadata_source']=='GOVERNED_IMPORT')

c.execute("""INSERT INTO users(system_user_id,role,full_name,academic_level,subjects,profile_completed)
  VALUES('STU-CHID-1','student','Chapter Identity Student','FSc Part 1','Biology',1)""")
sid=c.execute("SELECT id FROM users WHERE system_user_id='STU-CHID-1'").fetchone()['id']
subjects=app._subject_map(c,sid)
bio=next(x for x in subjects if x['subject']=='Biology')
ok('student subject map carries canonical chapter display metadata',bio['chapters'] and bio['chapters'][0]['display_label']=='Cell Biology' and bio['chapters'][0]['chapter']=='Cell Biology')

subject=(ROOT/'templates/subject_detail.html').read_text(); chapter=(ROOT/'templates/chapter_page.html').read_text()
ok('chapter cards render number and name while URLs keep raw source chapter identity','ch.chapter_number' in subject and 'ch.chapter_name or ch.display_label' in subject and "chapter=ch.chapter" in subject)
ok('chapter page renders canonical display identity while practice filters keep raw identity','chapter.chapter_name or chapter.display_label' in chapter and "chapter=chapter.chapter" in chapter)
practice=(ROOT/'templates/test_setup.html').read_text()
ok('Practice shows display labels but submits the raw chapter key','x.display_label||x.chapter' in practice and 'value="${esc(x.chapter)}"' in practice)
ok('Practice chapter renderer escapes imported display metadata before innerHTML use','function esc(x)' in practice and '${esc(x.display_label||x.chapter)}' in practice)
plan=(ROOT/'templates/study_plan.html').read_text(); mastery=(ROOT/'templates/mastery.html').read_text()
ok('Study Plan and mastery selector use canonical chapter display labels','chapter_display or x.chapter' in plan and 'c.display_label or c.chapter' in mastery)
ok('release marker identifies the governed chapter identity descendant',is_compatible_descendant(app.healthz()[0]['release_version'],'6.3.2'))

c.close()
print(f'\nV6.3.2 CHAPTER IDENTITY CHECKS PASSED: {n}')
