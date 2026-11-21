"""Build exactly the accepted SQLite ScoreMax with read-only performance patches.

PRODUCTION BUILD CANDIDATE ONLY. Invoked explicitly during isolated CI;
not wired to Render, auto-deploy, DB schema migration or learner activation.
All academic and PH admission/marking paths remain on the accepted runtime.
"""
from __future__ import annotations
import hashlib,json,subprocess,sys
from pathlib import Path

REPO=Path(__file__).resolve().parents[1]
ROOT=REPO/"scoremax_runtime_v669b"
ACCEPTED_SHA="ce3989897be46c2c01f2d7d726168843165f2d18111b02b48f1c18a3dec5d2e6"
ALLOWED_CHANGED={"app.py","ux_student_batch.py","ux_catalogue_browser.py"}
STEPS=(
 "scoremax_navigation_perf_delta_20261114.py",
 "scoremax_navigation_grouped_scope_delta_20261114.py",
 "scoremax_navigation_batch_student_evidence_20261114.py",
 "scoremax_mastery_card_projection_20261114.py",
 "scoremax_request_evidence_reuse_20261114.py",
 "scoremax_catalogue_subject_pushdown_20261114.py",
 "scoremax_evidence_scalar_copy_20261115.py",
 "scoremax_fused_subject_inventory_20261114.py",
 "scoremax_hidden_template_work_guard_20261115.py",
 "scoremax_chapter_mastery_local_bundle_20261115.py",
 "scoremax_learn_subject_evidence_grouping_20261116.py",
)
def checksums():
    return {p.relative_to(ROOT).as_posix():hashlib.sha256(p.read_bytes()).hexdigest()
            for p in ROOT.rglob("*") if p.is_file()}
def digest(values):
    return hashlib.sha256(json.dumps(values,sort_keys=True,separators=(",",":")).encode()).hexdigest()
def execute(file,*args):
    response=subprocess.run([sys.executable,"-B",str(file),*map(str,args)],
       cwd=REPO,capture_output=True,text=True,timeout=180)
    if response.returncode:
        raise RuntimeError("SQLITE_NAV_BUILD_STEP_FAILED:"+str(file)+
                           ": "+(response.stdout+response.stderr)[-3000:])
    return response.stdout.strip()[-1000:]

def main():
    execute(REPO/"scripts/materialize_scoremax_biology_receiver_20261027.py")
    baseline=checksums()
    if len(baseline)!=263 or digest(baseline)!=ACCEPTED_SHA:
        raise RuntimeError("ACCEPTED_SCOREMAX_RUNTIME_DIGEST_DRIFT:"+digest(baseline))
    for name in STEPS:execute(REPO/"scripts"/name,ROOT)
    changed=checksums()
    changed_files=sorted(k for k in (baseline.keys()|changed.keys())
                         if baseline.get(k)!=changed.get(k))
    if not changed_files or set(changed_files)-ALLOWED_CHANGED or baseline.keys()!=changed.keys():
        raise RuntimeError("SQLITE_NAV_UNAUTHORISED_RUNTIME_FILES:"+repr(changed_files))
    for file in changed_files:
        compile((ROOT/file).read_text(encoding="utf8"),str(ROOT/file),"exec")
    # Reproducibility is checked on a fresh builder by CI.
    result={"status":"SQLITE_NAV_CANDIDATE_BUILT","source_sha256":digest(baseline),
      "candidate_sha256":digest(changed),"changed_runtime_files":changed_files,
      "patches":list(STEPS),"ddl_applied":False,
      "postgres":False,"persistent_shadow":False,
      "marked_questions_or_mastery_awarded":False,"deployment_performed":False}
    print("SCOREMAX_SQLITE_ONLY_CANDIDATE="+json.dumps(result,sort_keys=True),flush=True)
if __name__=="__main__":main()
