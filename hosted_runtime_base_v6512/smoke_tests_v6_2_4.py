"""ScoreMax V6.2.4 curriculum-isolation and accessibility regression suite."""
from __future__ import annotations
import os,sys,tempfile
from pathlib import Path
ROOT=Path(__file__).resolve().parent
sys.path.insert(0,str(ROOT))
from smoke_tests_v5_5 import install_framework_stubs

def main():
    flask,request=install_framework_stubs(); temp=Path(tempfile.mkdtemp(prefix="scoremax_v624_"))
    os.environ["SCOREMAX_DB"]=str(temp/"scoremax.db"); os.environ["SCOREMAX_ENV"]="local"
    import app
    checks=[]
    def ok(name,condition=True):
        if not condition: raise AssertionError(name)
        checks.append(name); print("PASS:",name)
    app.init(); c=app.db()
    fsc=c.execute("""INSERT INTO users(system_user_id,role,full_name,email,username,password_hash,account_status,session_version,academic_level)
      VALUES('STU-V624-FSC','student','FSc Student','fsc624@test','fsc624','x','active',0,'FSc Part 1')""").lastrowid
    unknown=c.execute("""INSERT INTO users(system_user_id,role,full_name,email,username,password_hash,account_status,session_version,academic_level,subjects)
      VALUES('STU-V624-X','student','Unknown Programme','x624@test','x624','x','active',0,'Pilot Programme X','Economics')""").lastrowid
    matric=c.execute("""INSERT INTO users(system_user_id,role,full_name,email,username,password_hash,account_status,session_version,academic_level)
      VALUES('STU-V624-M','student','Matric Student','m624@test','m624','x','active',0,'Matric / Class 9–10')""").lastrowid
    c.commit()
    fsc_ch=app._curriculum_chapters(c,fsc)
    ok('matching programme still receives its own live chapters',bool(fsc_ch) and all(s in {'Biology','Chemistry','Physics'} for s,_ in fsc_ch))
    ok('unknown programme receives no cross-programme chapters',app._curriculum_chapters(c,unknown)==[])
    ok('missing programme inventory remains unknown rather than false zero coverage',app._estimate_starting_coverage(c,unknown) is None)
    ok('unknown explicit target receives no fallback bank',app._curriculum_chapters(c,fsc,'Unknown Assessment')==[])
    unknown_map=app._subject_map(c,unknown)
    ok('declared subject remains visible without borrowing inventory',len(unknown_map)==1 and unknown_map[0]['subject']=='Economics' and unknown_map[0]['availability']=='COMING_SOON')
    ok('unknown programme cannot inherit FSc subjects',not ({'Biology','Chemistry','Physics'} & {x['subject'] for x in unknown_map}))
    matric_map=app._subject_map(c,matric)
    ok('Matric catalogue can explain subjects without marking FSc bank live',all(x['available_questions']==0 and not x['chapters'] for x in matric_map))
    c.close()
    source=(ROOT/'app.py').read_text()
    ok('stale four-level mastery ordering fragment is removed',"{'Foundation':1,'Exam Ready':2,'Distinction':3,'Elite':4}" not in source)
    base=(ROOT/'templates/base.html').read_text(); css=(ROOT/'static/styles.css').read_text()
    ok('shell includes a keyboard skip link and focusable main landmark','class="skip-link"' in base and 'id="mainContent" tabindex="-1"' in base)
    ok('tabs receive ARIA ownership relationships','aria-controls' in base and "setAttribute('aria-labelledby'" in base and "setAttribute('role','tabpanel'" in base)
    ok('tabs support arrow Home and End keys',all(key in base for key in ["e.key==='ArrowRight'","e.key==='ArrowLeft'","e.key==='Home'","e.key==='End'"]))
    ok('mobile menu supports Escape and keyboard focus containment',"e.key==='Escape'" in base and 'focusable=[' in base and 'mobileMenuOpener' in base)
    ok('visible focus and reduced-motion styles exist',':focus-visible' in css and 'prefers-reduced-motion' in css)
    ok('release health marker is 6.2.4',app.healthz()[0]['version']in {'6.2.4','6.2.5','6.2.6','6.2.7','6.2.7.1','6.2.7.2','6.2.8','6.2.8.1'})
    print(f"\nV6.2.4 CURRICULUM/ACCESSIBILITY CHECKS PASSED: {len(checks)}")
if __name__=='__main__': main()
