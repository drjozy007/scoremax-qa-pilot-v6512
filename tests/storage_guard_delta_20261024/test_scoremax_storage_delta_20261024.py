"""New isolated storage delta cases only; no service or historical suite imports."""
from contextlib import closing, redirect_stdout
from copy import deepcopy
import hashlib
import importlib.util
import io
import json
import os
from pathlib import Path
import shutil
import sqlite3
import subprocess
import sys
import tempfile
import threading
import time
from types import SimpleNamespace
import unittest
from unittest.mock import patch

HERE=Path(__file__).resolve().parent
sys.path.insert(0,str(HERE))
import scoremax_persistent_storage_guard as guard
import backup_capacity_v1 as capacity
spec=importlib.util.spec_from_file_location("scoremax_storage_baseline",HERE/"scoremax_persistent_storage_guard.baseline.py")
baseline=importlib.util.module_from_spec(spec); spec.loader.exec_module(baseline)
REAL_CONNECT=sqlite3.connect
EVENTS=[]


class StorageDelta(unittest.TestCase):
    def setUp(self):
        self.folder=tempfile.TemporaryDirectory(prefix="synthetic-",dir=HERE)
        self.root=Path(self.folder.name)
        self.child_env=dict(os.environ,RENDER='false',PYTHONDONTWRITEBYTECODE='1')
        self.environment=patch.dict(os.environ,{"RENDER":"false"},clear=True); self.environment.start()
        self.lock_temp=patch.object(capacity.tempfile,"gettempdir",return_value=str(self.root)); self.lock_temp.start()
        for module in (guard,baseline):
            module.ROOT=self.root/"scoremax"
            module.DB=module.ROOT/"state"/"scoremax.db"
            module.BACKUP=module.ROOT/"backup"
            module.INTAKE=module.ROOT/"intake"
            module.MOUNT=self.root
            module.SENTINEL=self.root/".scoremax_persistent_storage_identity.json"
            module.PROBE_DB=module.ROOT/"state"/"probe.sqlite3"
            module.BASELINE_BACKUP=module.BACKUP/"scoremax_preimport_empty_baseline.sqlite3"
            module.OPERATIONAL_BACKUP=module.BACKUP/"scoremax_operational_latest.sqlite3"
        for path in (guard.DB.parent,guard.BACKUP,guard.INTAKE):path.mkdir(parents=True)
        with closing(REAL_CONNECT(guard.DB)) as c:
            c.executescript("""
            CREATE TABLE questions(id INTEGER PRIMARY KEY,question_id TEXT,ph_projection_owner TEXT,source_import_batch_id INTEGER,
                content_environment TEXT,scoremax_ready INTEGER,status TEXT,review_status TEXT,active INTEGER,academic_payload TEXT);
            CREATE TABLE curriculum(id INTEGER PRIMARY KEY);
            CREATE TABLE question_families(id INTEGER PRIMARY KEY);
            CREATE TABLE chapter_catalogue(id INTEGER PRIMARY KEY);
            CREATE TABLE coverage_packages(code TEXT,programme TEXT,status TEXT,price_minor INTEGER,currency TEXT,billing_period TEXT);
            CREATE TABLE plans(price_minor INTEGER);
            CREATE TABLE users(system_user_id TEXT,role TEXT,username TEXT,email TEXT,content_reviewer_enabled INTEGER);
            """)
            c.executemany("INSERT INTO coverage_packages VALUES(?,?,?,?,?,?)",
                [(key,*values) for key,values in guard.APPROVED_COVERAGE_PACKAGES.items()])
            c.commit()

    def tearDown(self):
        self.lock_temp.stop()
        self.environment.stop()
        self.folder.cleanup()

    def backup(self,target=None):
        with closing(guard._readonly_connection(guard.DB)) as c:
            c.row_factory=sqlite3.Row; c.execute("BEGIN")
            return guard._backup_and_verify(c,target or guard.OPERATIONAL_BACKUP)

    def private_directories(self):
        return list(guard.BACKUP.glob(".*.copy-*"))

    def old_backup(self):
        self.backup()
        return guard.OPERATIONAL_BACKUP.read_bytes()

    def add_synthetic_row(self):
        with closing(REAL_CONNECT(guard.DB)) as c:
            c.execute("INSERT INTO questions VALUES(1,'SYNTHETIC-1','',1,'CANDIDATE',0,'Draft','Draft',0,?)",("synthetic ignored payload "*100,))
            c.commit()

    def test_success_private_persistent_restore_and_unrelated_files(self):
        predictable=guard.OPERATIONAL_BACKUP.with_suffix(".tmp"); predictable.write_bytes(b"other operation")
        unrelated=guard.BACKUP/".another-operation"; unrelated.mkdir(); (unrelated/"keep").write_bytes(b"protected")
        restore=guard._restore_semantic_check
        observed=[]
        def check(source,*args,**kwargs):
            observed.append((source,kwargs["workspace"]))
            self.assertTrue(source.is_relative_to(guard.BACKUP))
            self.assertEqual(source.parent,kwargs["workspace"])
            self.assertNotEqual(source.parent,guard.BACKUP)
            return restore(source,*args,**kwargs)
        with patch.object(guard,"_restore_semantic_check",side_effect=check):
            digest,integrity,fk=self.backup()
        self.assertEqual(integrity,"ok"); self.assertEqual(fk,0)
        self.assertEqual(digest,hashlib.sha256(guard.OPERATIONAL_BACKUP.read_bytes()).hexdigest())
        self.assertEqual(predictable.read_bytes(),b"other operation")
        self.assertEqual((unrelated/"keep").read_bytes(),b"protected")
        self.assertEqual(len(observed),1); self.assertFalse(self.private_directories())

    def test_semantic_or_digest_failure_never_replaces_old_backup(self):
        old=self.old_backup(); self.add_synthetic_row()
        for name in ("_restore_semantic_check","_sha256_stream"):
            with self.subTest(name=name), patch.object(guard,name,side_effect=RuntimeError("SYNTHETIC_VERIFICATION_FAILURE")):
                with redirect_stdout(io.StringIO()),self.assertRaises(SystemExit) as failure:self.backup()
                self.assertEqual(failure.exception.code,78)
                self.assertEqual(guard.OPERATIONAL_BACKUP.read_bytes(),old)
                self.assertFalse(self.private_directories())

    def test_initial_capacity_exact_boundary_and_below(self):
        self.assertEqual(capacity.RESERVE_BYTES,512*1024*1024)
        size=capacity.database_bytes(guard.DB)
        admitted=size*2+capacity.RESERVE_BYTES+guard.COPY_SLACK_BYTES
        with patch.object(capacity.shutil,"disk_usage",return_value=SimpleNamespace(free=admitted-1)),patch.object(guard,"capacity_backup") as copy:
            with redirect_stdout(io.StringIO()),self.assertRaises(SystemExit):self.backup()
            copy.assert_not_called()
        self.assertFalse(guard.OPERATIONAL_BACKUP.exists())
        with patch.object(capacity.shutil,"disk_usage",return_value=SimpleNamespace(free=admitted)):
            self.backup()
        self.assertTrue(guard.OPERATIONAL_BACKUP.is_file()); self.assertFalse(self.private_directories())

    def late_space_loss(self,stage,free_after):
        old=self.old_backup(); old_identity=capacity._destination_identity(guard.OPERATIONAL_BACKUP)
        self.add_synthetic_row()
        dropped=[False]; original=getattr(guard,stage)
        def lose_space(*args,**kwargs):
            value=original(*args,**kwargs)
            dropped[0]=True
            return value
        def available(path):
            return SimpleNamespace(free=free_after if dropped[0] else 2**40)
        output=io.StringIO()
        with patch.object(guard,stage,side_effect=lose_space),patch.object(capacity.shutil,'disk_usage',side_effect=available):
            with redirect_stdout(output),self.assertRaises(SystemExit) as refusal:self.backup()
        self.assertTrue(dropped[0]);self.assertEqual(refusal.exception.code,78)
        self.assertIn('backup_publication_capacity_refused',output.getvalue())
        self.assertEqual(guard.OPERATIONAL_BACKUP.read_bytes(),old)
        self.assertEqual(capacity._destination_identity(guard.OPERATIONAL_BACKUP),old_identity)
        self.assertFalse(self.private_directories())

    def test_reserve_drop_during_restore_verification_refuses_publication(self):
        self.late_space_loss('_restore_semantic_check',capacity.RESERVE_BYTES-1)

    def test_slack_drop_during_final_digest_refuses_publication(self):
        self.late_space_loss('_sha256_stream',capacity.RESERVE_BYTES+guard.COPY_SLACK_BYTES-1)

    def test_native_semantic_mismatch_preserves_old_backup(self):
        old=self.old_backup()
        original=guard.check_sqlite
        def mismatch(path):
            if path.name=='restore.sqlite3':
                with closing(REAL_CONNECT(path)) as c:
                    c.execute("DELETE FROM coverage_packages WHERE code='fsc1_biology'");c.commit()
            return original(path)
        with patch.object(guard,'check_sqlite',side_effect=mismatch):
            with redirect_stdout(io.StringIO()),self.assertRaises(SystemExit):self.backup()
        self.assertEqual(guard.OPERATIONAL_BACKUP.read_bytes(),old);self.assertFalse(self.private_directories())

    def test_committed_wal_rows_survive_and_private_artifacts_are_delete_mode(self):
        with closing(REAL_CONNECT(guard.DB)) as writer:
            self.assertEqual(writer.execute('PRAGMA journal_mode=WAL').fetchone()[0],'wal')
            writer.execute("INSERT INTO questions VALUES(1,'SYNTHETIC-WAL','',1,'CANDIDATE',0,'Draft','Draft',0,'synthetic')")
            writer.commit()
            self.assertTrue(Path(str(guard.DB)+'-wal').is_file())
            self.backup()
            self.assertEqual(writer.execute('PRAGMA journal_mode').fetchone()[0],'wal')
            with closing(REAL_CONNECT(guard.OPERATIONAL_BACKUP)) as destination:
                self.assertEqual(destination.execute('PRAGMA journal_mode').fetchone()[0],'delete')
                self.assertEqual(destination.execute('SELECT question_id FROM questions').fetchall(),[('SYNTHETIC-WAL',)])
            for suffix in ('-wal','-shm','-journal'):
                self.assertFalse(Path(str(guard.OPERATIONAL_BACKUP)+suffix).exists())
        self.assertFalse(self.private_directories())

    def test_mid_copy_reserve_loss_preserves_old_backup(self):
        old=self.old_backup()
        calls=[0]
        def available(path):
            calls[0]+=1
            return SimpleNamespace(free=2**40 if calls[0]<=2 else capacity.RESERVE_BYTES-1)
        with patch.object(capacity.shutil,"disk_usage",side_effect=available):
            with redirect_stdout(io.StringIO()),self.assertRaises(SystemExit):self.backup()
        self.assertEqual(guard.OPERATIONAL_BACKUP.read_bytes(),old); self.assertFalse(self.private_directories())

    def test_snapshot_growth_is_not_silently_readmitted(self):
        old=self.old_backup()
        def grows(source,destination,target,*,progress_hook,pages,backup_artifact):
            self.assertTrue(backup_artifact)
            count=source.execute("PRAGMA page_count").fetchone()[0]
            progress_hook(0,0,count+1)
        with patch.object(guard,"capacity_backup",side_effect=grows):
            with redirect_stdout(io.StringIO()),self.assertRaises(SystemExit):self.backup()
        self.assertEqual(guard.OPERATIONAL_BACKUP.read_bytes(),old); self.assertFalse(self.private_directories())

    def test_other_filesystem_budget_and_protected_sidecar_are_refused(self):
        with redirect_stdout(io.StringIO()),self.assertRaises(SystemExit):self.backup(self.root/'outside.sqlite3')
        self.assertFalse((self.root/'outside.sqlite3').exists())
        old=self.old_backup()
        sidecar=Path(str(guard.OPERATIONAL_BACKUP)+'-wal');sidecar.write_bytes(b'PROTECTED-OWNER')
        with redirect_stdout(io.StringIO()),self.assertRaises(SystemExit):self.backup()
        self.assertEqual(guard.OPERATIONAL_BACKUP.read_bytes(),old)
        self.assertEqual(sidecar.read_bytes(),b'PROTECTED-OWNER');self.assertFalse(self.private_directories())

    def test_owned_handles_close_after_checker_and_restore_open_failures(self):
        tracked=[]
        class Tracked(sqlite3.Connection):
            did_close=False
            def close(self):
                self.did_close=True
                return super().close()
        def connect(*args,**kwargs):
            value=REAL_CONNECT(*args,factory=Tracked,**kwargs); tracked.append(value); return value
        with patch.object(guard.sqlite3,"connect",side_effect=connect),patch.object(guard,"_sqlite_state",side_effect=sqlite3.DatabaseError("synthetic")):
            with redirect_stdout(io.StringIO()),self.assertRaises(SystemExit):guard.check_sqlite(guard.DB)
        self.assertTrue(tracked and all(c.did_close for c in tracked))
        tracked.clear()
        private=guard._private_destination
        def refuse_restore(path):
            if path.name=="restore.sqlite3":raise sqlite3.OperationalError("synthetic destination-open failure")
            return private(path)
        with patch.object(guard.sqlite3,"connect",side_effect=connect),patch.object(guard,"_private_destination",side_effect=refuse_restore):
            with self.assertRaises(sqlite3.OperationalError):self.backup()
        self.assertTrue(tracked and all(c.did_close for c in tracked)); self.assertFalse(self.private_directories())

    def test_copy_exception_closes_and_removes_only_own_workspace(self):
        old=self.old_backup()
        def fails(source,destination,target,**kwargs):
            destination.execute("CREATE TABLE partial(id INTEGER)"); destination.commit()
            raise sqlite3.OperationalError("synthetic copy failure")
        with patch.object(guard,"capacity_backup",side_effect=fails):
            with self.assertRaises(sqlite3.OperationalError):self.backup()
        self.assertEqual(guard.OPERATIONAL_BACKUP.read_bytes(),old); self.assertFalse(self.private_directories())

    def test_destination_changed_during_verification_is_not_overwritten(self):
        self.old_backup()
        restore=guard._restore_semantic_check
        changed=[]
        def external_change(*args,**kwargs):
            restore(*args,**kwargs)
            with guard.OPERATIONAL_BACKUP.open("ab") as handle:handle.write(b"EXTERNAL-OWNER")
            changed.append(guard.OPERATIONAL_BACKUP.read_bytes())
        with patch.object(guard,"_restore_semantic_check",side_effect=external_change):
            with redirect_stdout(io.StringIO()),self.assertRaises(SystemExit):self.backup()
        self.assertEqual(guard.OPERATIONAL_BACKUP.read_bytes(),changed[0]); self.assertFalse(self.private_directories())

    def test_serialized_capacity_publication_and_cleanup(self):
        active=[0,0]; barrier=threading.Barrier(3); failures=[]
        original=guard._restore_semantic_check
        def observed(*args,**kwargs):
            active[0]+=1; active[1]=max(active[1],active[0])
            try:time.sleep(.025);return original(*args,**kwargs)
            finally:active[0]-=1
        def worker():
            try:barrier.wait();self.backup()
            except BaseException as exc:failures.append(type(exc).__name__)
        with patch.object(guard,"_restore_semantic_check",side_effect=observed):
            a=threading.Thread(target=worker);b=threading.Thread(target=worker)
            a.start();b.start();barrier.wait();a.join(5);b.join(5)
        self.assertFalse(a.is_alive() or b.is_alive());self.assertEqual(failures,[])
        self.assertEqual(active[1],1);self.assertFalse(self.private_directories())
        self.assertEqual(guard.check_sqlite(guard.OPERATIONAL_BACKUP),("ok",0))

    def test_preimport_guard_preserves_live_database_and_one_live_scan(self):
        before=guard.DB.read_bytes(); queries=[]
        original=guard._readonly_connection
        def observed(path):
            c=original(path)
            if path==guard.DB:c.set_trace_callback(queries.append)
            return c
        with patch.object(guard,"_readonly_connection",side_effect=observed):
            result=guard.qualify_database()
        self.assertEqual(result["state"],"preimport_qualified")
        self.assertEqual(before,guard.DB.read_bytes())
        self.assertEqual(sum(q.lower()=="pragma integrity_check" for q in queries),1)
        self.assertEqual(sum(q.lower()=="pragma foreign_key_check" for q in queries),1)

    def test_filesystem_lock_identity_and_competing_process(self):
        self.assertEqual(capacity.capacity_lock_path(guard.BACKUP),capacity.capacity_lock_path(guard.INTAKE))
        code="""import sys
print('BOOT',flush=True)
import tempfile
from pathlib import Path
sys.path.insert(0,sys.argv[1])
import backup_capacity_v1 as capacity
tempfile.gettempdir=lambda:sys.argv[2]
try:
    with capacity.capacity_lock(Path(sys.argv[3]),timeout_seconds=.15):print('UNEXPECTED_ACQUIRE')
except TimeoutError:print('BLOCKED')
"""
        with capacity.capacity_lock(guard.BACKUP,timeout_seconds=.5):
            child=subprocess.run([sys.executable,'-B','-c',code,str(HERE),str(self.root),str(guard.INTAKE)],capture_output=True,text=True,timeout=20,env=self.child_env)
        self.assertEqual(child.returncode,0,child.stderr)
        self.assertEqual(child.stdout.strip(),'BOOT\nBLOCKED')

    def test_main_uses_qualification_scan_result(self):
        qualification={"state":"preimport_qualified","integrity":"ok","fk":0}
        with patch.object(guard,"is_mount",return_value=True),patch.object(guard,"durability_probe",return_value=1),patch.object(guard,"qualify_database",return_value=qualification),patch.object(guard,"check_sqlite",side_effect=AssertionError("duplicate live scan")):
            output=io.StringIO()
            with redirect_stdout(output):guard.main()
        self.assertIn("db_integrity=ok db_fk=0",output.getvalue())

    def emergency_fixture(self):
        source=guard.INTAKE/"synthetic.json"; source.write_bytes(b"synthetic source evidence only")
        backup=guard.BACKUP/"preimport.sqlite3"
        with closing(REAL_CONNECT(backup)) as c:c.execute("CREATE TABLE synthetic(id INTEGER)");c.commit()
        self.add_synthetic_row()
        with closing(REAL_CONNECT(guard.DB)) as c:
            c.executescript("""
            CREATE TABLE content_import_batches(id INTEGER,batch_code TEXT,intake_mode TEXT,source_system TEXT,status TEXT,
              source_prompt_pack_id TEXT,source_prompt_pack_version TEXT,payload_checksum TEXT,row_count INTEGER,valid_count INTEGER,
              error_count INTEGER,warning_count INTEGER,source_file_path TEXT,backup_record_id INTEGER,release_status TEXT,
              released_count INTEGER,release_attested_at TEXT,release_attested_by TEXT,released_at TEXT);
            CREATE TABLE content_import_batch_rows(id INTEGER,batch_id INTEGER,import_status TEXT,question_db_id INTEGER,
              errors_json TEXT,warnings_json TEXT,question_id TEXT,row_json TEXT);
            CREATE TABLE pilot_backups(id INTEGER,integrity_status TEXT,file_path TEXT,file_sha256 TEXT,file_size_bytes INTEGER,reason TEXT);
            """)
            c.execute("INSERT INTO pilot_backups VALUES(1,'OK',?,?,?,'synthetic')",(str(backup),hashlib.sha256(backup.read_bytes()).hexdigest(),backup.stat().st_size))
            c.execute("INSERT INTO content_import_batches VALUES(1,'SYNTHETIC','EMERGENCY_DIRECT','POWER_HOUSE_GOVERNED','IMPORTED','SYNTHETIC',?,?,1,1,0,0,?,1,'NOT_RELEASED',0,NULL,NULL,NULL)",
                ("a"*64,hashlib.sha256(source.read_bytes()).hexdigest(),str(source)))
            payload=json.dumps({"ScoreMax Ready":True,"Rights Status":"approved","Status":"Approved"})
            c.execute("INSERT INTO content_import_batch_rows VALUES(1,1,'IMPORTED',1,'[]','[]','SYNTHETIC-1',?)",(payload,));c.commit()

    def test_tiny_postimport_guard_preserves_source_and_candidate_state(self):
        self.emergency_fixture()
        with closing(REAL_CONNECT(guard.DB)) as c:
            for name in ('ph_question_id','ph_question_version_id','ph_question_checksum_sha256','ph_release_id','ph_release_version','ph_release_checksum_sha256'):
                c.execute('ALTER TABLE questions ADD COLUMN '+name+' TEXT')
            c.commit()
        original=guard.DB.read_bytes()
        value=guard.qualify_database()
        self.assertEqual(guard.DB.read_bytes(),original)
        self.assertEqual(value['state'],'postimport_qualified')
        self.assertEqual(value['native_power_house_questions'],0)
        self.assertEqual(value['governed_emergency']['candidate'],1)
        self.assertEqual(value['governed_emergency']['released'],0)

    def test_released_row_and_backup_receipt_validation_parity(self):
        self.emergency_fixture()
        with closing(REAL_CONNECT(guard.DB)) as c:
            c.execute("UPDATE content_import_batches SET release_status='RELEASED_ELIGIBLE',released_count=1,release_attested_at='synthetic',release_attested_by='synthetic',released_at='synthetic'")
            c.execute("UPDATE questions SET active=1,status='Approved',review_status='Approved',content_environment='PRODUCTION',scoremax_ready=1")
            c.execute("INSERT INTO pilot_backups SELECT 2,integrity_status,file_path,file_sha256,file_size_bytes,'Automatic backup before emergency release SYNTHETIC' FROM pilot_backups WHERE id=1")
            c.commit()
        mutations=[None,"UPDATE content_import_batches SET release_attested_at=''",
            "UPDATE content_import_batches SET released_count=0","UPDATE questions SET scoremax_ready=0",
            "UPDATE questions SET status='Draft'","UPDATE questions SET review_status='Draft'",
            "UPDATE questions SET content_environment='CANDIDATE'","UPDATE pilot_backups SET file_sha256='bad' WHERE id=2",
            "UPDATE pilot_backups SET file_size_bytes=1 WHERE id=2"]
        for mutation in mutations:
            outcomes=[]
            for module in (baseline,guard):
                with closing(REAL_CONNECT(guard.DB)) as c:
                    c.row_factory=sqlite3.Row;c.execute('BEGIN')
                    if mutation:c.execute(mutation)
                    output=io.StringIO()
                    try:
                        with redirect_stdout(output):value=module._qualify_emergency_batches(c)
                        outcomes.append(('PASS',value))
                    except SystemExit as exc:outcomes.append(('FAIL',exc.code,output.getvalue()))
                    finally:c.rollback()
            self.assertEqual(outcomes[0],outcomes[1],mutation)
            if mutation:self.assertEqual(outcomes[0][0],'FAIL')

    def test_emergency_row_validation_parity(self):
        self.emergency_fixture()
        cases=[
            ("none",None),
            ("mode","UPDATE content_import_batches SET intake_mode='OTHER'"),
            ("prompt","UPDATE content_import_batches SET source_prompt_pack_id=''"),
            ("version","UPDATE content_import_batches SET source_prompt_pack_version='bad'"),
            ("counts","UPDATE content_import_batches SET row_count=2"),
            ("status","UPDATE content_import_batch_rows SET import_status='FAILED'"),
            ("errors","UPDATE content_import_batch_rows SET errors_json='[1]'"),
            ("warnings","UPDATE content_import_batch_rows SET warnings_json='[1]'"),
            ("binding","UPDATE content_import_batch_rows SET question_id='OTHER'"),
            ("rights","UPDATE content_import_batch_rows SET row_json='{\"ScoreMax Ready\":true,\"Rights Status\":\"unknown\"}'"),
            ("hold","UPDATE content_import_batch_rows SET row_json='{\"ScoreMax Ready\":true,\"Rights Status\":\"approved\",\"Status\":\"HOLD\"}'"),
            ("candidate","UPDATE questions SET status='Approved'"),
            ("active","UPDATE questions SET active=1"),
            ("release","UPDATE content_import_batches SET release_status='OTHER'"),
        ]
        for name,mutation in cases:
            outcomes=[]
            for module in (baseline,guard):
                with closing(REAL_CONNECT(guard.DB)) as c:
                    c.row_factory=sqlite3.Row;c.execute("BEGIN")
                    if mutation:c.execute(mutation)
                    output=io.StringIO()
                    try:
                        with redirect_stdout(output):value=module._qualify_emergency_batches(c)
                        outcomes.append(("PASS",value))
                    except SystemExit as exc:outcomes.append(("FAIL",exc.code,output.getvalue()))
                    finally:c.rollback()
            self.assertEqual(outcomes[0],outcomes[1],name)
            if mutation:self.assertEqual(outcomes[0][0],"FAIL",name)


if __name__=="__main__":
    runner=unittest.TextTestRunner(verbosity=2)
    result=runner.run(unittest.defaultTestLoader.loadTestsFromTestCase(StorageDelta))
    evidence={"passed":result.wasSuccessful(),"tests_run":result.testsRun,"failures":len(result.failures),"errors":len(result.errors),
       "scope":"new tiny synthetic delta only","platform":sys.platform,"python_version":sys.version.split()[0],"services_started":0,"production_access":False,"historical_suites_replayed":0,
       "reserve_bytes":capacity.RESERVE_BYTES,"capacity_helper_sha256":hashlib.sha256((HERE/"backup_capacity_v1.py").read_bytes()).hexdigest(),
       "candidate_sha256":hashlib.sha256((HERE/"scoremax_persistent_storage_guard.py").read_bytes()).hexdigest(),
       "baseline_sha256":hashlib.sha256((HERE/"scoremax_persistent_storage_guard.baseline.py").read_bytes()).hexdigest()}
    (HERE/"DELTA_TEST_RESULT_20261024.json").write_text(json.dumps(evidence,indent=2)+"\n",encoding="utf-8")
    print(json.dumps(evidence,sort_keys=True))
    raise SystemExit(not result.wasSuccessful())
