"""Seed real native Power House *synthetic fixture* release records for PG fidelity.

Reuses the accepted Biology receiver's approved-content example and its
existing test envelope construction. Direct local contract admission (NOT
HTTP signature verification, real PH releases or academic approval). Executes
only against /tmp/ disposable ScoreMax and refuses external network access.
"""
from __future__ import annotations

import copy
from datetime import datetime,timezone
import json
import os
from pathlib import Path
import sys

def main(dbpath,runtime):
    dbpath=Path(dbpath).resolve()
    runtime=Path(runtime).resolve()
    if not dbpath.is_file() or not dbpath.is_relative_to(Path("/tmp")):
        raise RuntimeError("NON_DISPOSABLE_SQLITE_REFUSED")
    if runtime.name!="scoremax_runtime_v669b":
        raise RuntimeError("GENERATED_SCOREMAX_RUNTIME_REQUIRED")
    home=dbpath.parent.parent
    os.environ.update({
        "SCOREMAX_ENV":"production",
        "SCOREMAX_SECRET":"synthetic-migration-immutable-session-secret",
        "SCOREMAX_STAGING_SESSION_SECRET":"synthetic-migration-staging-secret",
        "SCOREMAX_BOOTSTRAP_ADMIN_PASSWORD":"Synthetic-Only-No-Live-Account",
        "SCOREMAX_BOOTSTRAP_ADMIN_EMAIL":"synthetic-admin@scoremax.invalid",
        "SCOREMAX_DB":str(dbpath),
        "SCOREMAX_PERSISTENT_ROOT":str(home),
        "SCOREMAX_BACKUP_DIR":str(home/"backup"),
        "SCOREMAX_CONTENT_INTAKE_DIR":str(home/"intake"),
        "SCOREMAX_SMTP_HOST":"smtp.invalid",
        "SCOREMAX_SMTP_FROM":"test@scoremax.invalid",
        "SCOREMAX_SEND_EMAIL_VERIFICATION":"0",
        "SCOREMAX_REQUIRE_EMAIL_VERIFICATION":"0",
        "SCOREMAX_PUBLIC_STUDENT_OPENING":"0",
        "SCOREMAX_ENFORCE_PAYWALL":"0",
        "SCOREMAX_INSTANCE_COUNT":"1",
        "WEB_CONCURRENCY":"1",
        "SCOREMAX_PUBLIC_BASE_URL":"https://localhost",
    })
    sys.path.insert(0,str(runtime))
    import scoremax_production
    from ux_catalogue_data import subject_items
    sm=scoremax_production.scoremax
    integration=sm.integration_v1
    example_path=runtime/"integration_examples"/"PH_SM_APPROVED_CONTENT_V1.example.json"
    if not example_path.is_file():
        raise RuntimeError("ACCEPTED_PH_EXAMPLE_MISSING")
    original=json.loads(example_path.read_text(encoding="utf8"))
    item=subject_items("year11","Biology")[0]
    now=datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00","Z")
    def envelope(label,question=None,programme="FSC_PART_I"):
        env=copy.deepcopy(original)
        release=env["payload"]["release"]
        q=copy.deepcopy(question if question is not None else env["payload"]["questions"][0])
        release.update(
            release_id="SYN-PG-PH-RELEASE-"+label,
            release_version="1",programme_id=programme,subject_id="BIOLOGY",
            chapter_id="MDCAT::BIOLOGY::UNIT::01" if programme=="MDCAT" else "SYN-PG-PH-OPAQUE-CHAPTER",
            generated_at=now,effective_at=now,
        )
        if question is None:
            q.update(question_id="SYN-PG-PH-CANONICAL-Q",
                question_version_id="SYN-PG-PH-CANONICAL-V1",
                question_version_number=1,supersedes_question_version_id=None)
            q["curriculum"].update(
                programme_id="FSC_PART_I",subject_id="BIOLOGY",
                chapter_id="SYN-PG-PH-OPAQUE-CHAPTER",
                grade_year_id="YEAR_11",section_id="SYN-PG-SECTION-A")
            q["curriculum"]["display"].update(
                programme="FSc Part 1",grade_year="Year 11",subject="Biology",
                chapter_number=item["number"],chapter=item["name"],
                section="Governed synthetic section",topic="Governed synthetic topic")
            q["content"]["stem"]="[SYNTHETIC MIGRATION] Select the contract fixture answer."
            q["architecture"]["claim_family_id"]="SYN-PG-PH-FAMILY"
            q["question_checksum_sha256"]=integration._object_checksum(
                q,"question_checksum_sha256")
        env.update(
            message_id="SYN-PG-PH-MSG-"+label,
            idempotency_key="SYN-PG-PH-IDEM-"+label,
            occurred_at=now,sent_at=now)
        env["payload"]["questions"]=[q]
        env["payload_checksum_sha256"]=integration.payload_checksum(env["payload"])
        return env
    with sm.db() as c:
        first=envelope("FSC")
        reply,status=integration.admit_content_envelope(
            c,first,first["payload_checksum_sha256"])
        if status!=202:raise RuntimeError("FSC_SOURCE_FIXTURE_ADMISSION_FAILED:"+str(reply))
        fsc=first["payload"]["release"]
        approved=integration.authorize_product_activation(
            c,fsc["release_id"],fsc["release_version"],
            fsc["package_checksum_sha256"],"SYNTHETIC-OWNER",
            "Disposable PostgreSQL migration source fixture")
        if approved.get("status")!="ACTIVE":
            raise RuntimeError("FSC_FIXTURE_ACTIVATION_NOT_ACTIVE:"+str(approved))
        c.commit()
        second=envelope("MDCAT",question=first["payload"]["questions"][0],
                        programme="MDCAT")
        reply,status=integration.admit_content_envelope(
            c,second,second["payload_checksum_sha256"])
        if status!=202:raise RuntimeError("MDCAT_SOURCE_FIXTURE_ADMISSION_FAILED:"+str(reply))
        mdcat=second["payload"]["release"]
        approved=integration.authorize_product_activation(
            c,mdcat["release_id"],mdcat["release_version"],
            mdcat["package_checksum_sha256"],"SYNTHETIC-OWNER",
            "Disposable MDCAT membership migration source fixture")
        if approved.get("status")!="ACTIVE":
            raise RuntimeError("MDCAT_FIXTURE_ACTIVATION_NOT_ACTIVE:"+str(approved))
        c.commit()
        counts={table:c.execute("SELECT COUNT(*) FROM "+table).fetchone()[0]
                for table in (
                  "integration_ph_content_releases",
                  "integration_ph_release_question_membership",
                  "integration_ph_question_version_store",
                  "integration_ph_product_activation_authorizations",
                )}
        if any(value<1 for value in counts.values()):
            raise RuntimeError("SOURCE_PH_PROTECTED_TABLE_UNPOPULATED:"+str(counts))
        canonical=c.execute(
            "SELECT COUNT(*) FROM questions WHERE ph_projection_owner='POWER_HOUSE' AND ph_question_id=?",
            ("SYN-PG-PH-CANONICAL-Q",)).fetchone()[0]
        if canonical!=1:raise RuntimeError("PH_CROSS_PROGRAMME_DUPLICATED_CANONICAL_ID")
        aliases=sm._programme_aliases
        scope=sm._programme_scope_sql
        def eligible(programme):
            clause,params=scope(aliases(programme),"q")
            return c.execute("SELECT COUNT(*) FROM questions q WHERE "
                +sm.live_question_clause("q")+" AND "+clause+
                " AND q.ph_question_id=?",params+["SYN-PG-PH-CANONICAL-Q"]).fetchone()[0]
        fsc_live=eligible("FSc Part 1")
        mdcat_live=eligible("MDCAT")
        if fsc_live!=1 or mdcat_live!=1:
            raise RuntimeError("PH_SHARED_PROGRAMME_VISIBILITY_DRIFT:"+str((fsc_live,mdcat_live)))
        if c.execute("PRAGMA integrity_check").fetchone()[0]!="ok":
            raise RuntimeError("PH_SOURCE_SQLITE_INTEGRITY_FAILED")
        print("SCOREMAX_PG_MIGRATION_NATIVE_PH_MEMBERSHIP_PASS="+json.dumps({
            "synthetic_releases":2,
            "shared_canonical_questions":canonical,
            "fsc_membership_visible":fsc_live,
            "mdcat_membership_visible":mdcat_live,
            "protected_counts":counts,
            "native_admission_and_authorization_called":True,
            "real_PH_transport_or_source_data":False,
            "real_student_records":False,
            "production_touched":False,
        },sort_keys=True),flush=True)

if __name__=="__main__":
    if len(sys.argv)!=3:raise SystemExit("USAGE: synthetic_db runtime_root")
    main(sys.argv[1],sys.argv[2])
