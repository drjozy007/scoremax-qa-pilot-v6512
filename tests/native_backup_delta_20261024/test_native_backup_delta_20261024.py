"""Only new native-backup delta cases; no Flask import, services or old suites."""
import ast
from contextlib import closing
import hashlib
import io
import json
import os
from pathlib import Path
import platform
import shutil
import sqlite3
import sys
import tempfile
import threading
import time
import unittest
from unittest.mock import patch
from types import SimpleNamespace
from datetime import datetime
import secrets

HERE=Path(__file__).resolve().parent
sys.path.insert(0,str(HERE))
import pilot_readiness_engine as native
import backup_capacity_v1 as capacity
import apply_scoremax_native_backup_delta_20261024 as installer
REAL_CONNECT=sqlite3.connect
CAPTURE=HERE.parent/"scoremax_exact_runtime"

class NativeBackupDelta(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory(prefix="synthetic-native-",dir=HERE)
        self.root=Path(self.tmp.name);self.source=self.root/"live.sqlite3";self.backup=self.root/"backups"/"backup.sqlite3"
        self.environment=patch.dict(os.environ,{"RENDER":"false","SCOREMAX_BACKUP_DIR":str(self.backup.parent)},clear=True);self.environment.start()
        self.local_tmp=patch.object(capacity.tempfile,"gettempdir",return_value=str(self.root));self.local_tmp.start()
        with closing(REAL_CONNECT(self.source)) as c:
            c.executescript("""
            CREATE TABLE users(id INTEGER PRIMARY KEY,username TEXT,role TEXT,enabled INTEGER,note BLOB);
            CREATE TABLE questions(id INTEGER PRIMARY KEY,source_version TEXT,active INTEGER);
            CREATE TABLE answers(id INTEGER PRIMARY KEY,question_id INTEGER REFERENCES questions(id),answer TEXT);
            CREATE TABLE pilot_backups(id INTEGER PRIMARY KEY,backup_code TEXT,reason TEXT,file_path TEXT,file_sha256 TEXT,file_size_bytes INTEGER,integrity_status TEXT,created_by INTEGER);
            INSERT INTO users VALUES(1,'fake learner','student',1,X'00FF');
            INSERT INTO questions VALUES(1,'SYNTHETIC-ONLY',0);
            INSERT INTO answers VALUES(1,1,'synthetic answer');
            """);c.commit()
    def tearDown(self):
        self.local_tmp.stop();self.environment.stop();self.tmp.cleanup()
    def backup_call(self):return native.sqlite_backup(self.source,self.backup)
    def old_backup(self):
        self.assertEqual(self.backup_call(),(True,"ok"))
        return self.backup.read_bytes(),capacity._destination_identity(self.backup)
    def unchanged(self,old):
        self.assertEqual(self.backup.read_bytes(),old[0])
        self.assertEqual(capacity._destination_identity(self.backup),old[1])
        self.assertFalse(list(self.backup.parent.glob(".*.copy-*")))

    def test_success_private_self_contained_copy_and_semantics(self):
        original=self.source.read_bytes()
        self.backup.parent.mkdir()
        sentinel=self.backup.with_suffix(".tmp");sentinel.write_bytes(b"UNRELATED")
        self.assertEqual(self.backup_call(),(True,"ok"))
        self.assertEqual(self.source.read_bytes(),original)
        self.assertEqual(sentinel.read_bytes(),b"UNRELATED")
        with closing(REAL_CONNECT(self.source)) as a,closing(REAL_CONNECT(self.backup)) as b:
            self.assertEqual(native._native_backup_semantics(a),native._native_backup_semantics(b))
            self.assertEqual(b.execute("PRAGMA journal_mode").fetchone()[0],"delete")
        self.assertFalse(list(self.backup.parent.glob(".*.copy-*")))

    def test_missing_source_does_not_create_empty_database_or_backup(self):
        missing=self.root/"missing.sqlite3"
        value=native.sqlite_backup(missing,self.backup)
        self.assertFalse(value[0]);self.assertFalse(missing.exists());self.assertFalse(self.backup.exists())

    def test_same_source_destination_refused(self):
        original=self.source.read_bytes()
        self.assertFalse(native.sqlite_backup(self.source,self.source)[0])
        self.assertEqual(self.source.read_bytes(),original)

    def test_wal_committed_data_preserved_without_changing_live_mode(self):
        with closing(REAL_CONNECT(self.source)) as writer:
            self.assertEqual(writer.execute("PRAGMA journal_mode=WAL").fetchone()[0],"wal")
            writer.execute("INSERT INTO users VALUES(2,'recent fake learner','student',1,NULL)");writer.commit()
            self.assertTrue(Path(str(self.source)+"-wal").exists())
            self.assertEqual(self.backup_call(),(True,"ok"))
            self.assertEqual(writer.execute("PRAGMA journal_mode").fetchone()[0],"wal")
            with closing(REAL_CONNECT(self.backup)) as b:
                self.assertEqual(b.execute("SELECT COUNT(*) FROM users").fetchone()[0],2)
                self.assertEqual(b.execute("PRAGMA journal_mode").fetchone()[0],"delete")
            for suffix in ("-wal","-shm","-journal"):self.assertFalse(Path(str(self.backup)+suffix).exists())

    def test_semantics_are_one_source_snapshot_with_concurrent_wal_writer(self):
        original=native._native_backup_semantics
        added=[False]
        with closing(REAL_CONNECT(self.source)) as writer:
            writer.execute("PRAGMA journal_mode=WAL")
            def observe(c):
                value=original(c)
                filename=c.execute("PRAGMA database_list").fetchone()[2]
                if Path(filename)==self.source and not added[0]:
                    writer.execute("INSERT INTO users VALUES(2,'concurrent fake learner','student',1,NULL)");writer.commit();added[0]=True
                return value
            with patch.object(native,"_native_backup_semantics",side_effect=observe):
                self.assertEqual(self.backup_call(),(True,"ok"))
            self.assertEqual(writer.execute("SELECT COUNT(*) FROM users").fetchone()[0],2)
            with closing(REAL_CONNECT(self.backup)) as restored:self.assertEqual(restored.execute("SELECT COUNT(*) FROM users").fetchone()[0],1)

    def test_source_handles_closed_before_artifact_verification(self):
        handles=[]
        class Tracked(sqlite3.Connection):
            closed=False
            def close(self):self.closed=True;return super().close()
        def connect(*args,**kwargs):
            c=REAL_CONNECT(*args,factory=Tracked,**kwargs)
            name=c.execute("PRAGMA database_list").fetchone()[2]
            handles.append((c,Path(name)));return c
        original=native._native_backup_semantics
        checked=[False]
        def observe(c):
            if Path(c.execute("PRAGMA database_list").fetchone()[2])!=self.source:
                self.assertTrue(all(conn.closed for conn,path in handles if path==self.source));checked[0]=True
            return original(c)
        with patch.object(native.sqlite3,"connect",side_effect=connect),patch.object(native,"_native_backup_semantics",side_effect=observe):
            self.assertEqual(self.backup_call(),(True,"ok"))
        self.assertTrue(checked[0]);self.assertTrue(all(conn.closed for conn,path in handles))

    def test_destination_open_failure_closes_successful_source_handles(self):
        old=self.old_backup();handles=[]
        class Tracked(sqlite3.Connection):
            closed=False
            def close(self):self.closed=True;return super().close()
        def connect(*args,**kwargs):
            if not kwargs.get("uri",False):raise sqlite3.OperationalError("SYNTHETIC_DESTINATION_OPEN")
            c=REAL_CONNECT(*args,factory=Tracked,**kwargs);handles.append(c);return c
        with patch.object(native.sqlite3,"connect",side_effect=connect):
            result=self.backup_call()
        self.assertFalse(result[0]);self.assertIn("SYNTHETIC_DESTINATION_OPEN",result[1])
        self.assertTrue(handles and all(c.closed for c in handles));self.unchanged(old)

    def test_foreign_key_violation_refuses_publication(self):
        old=self.old_backup()
        with closing(REAL_CONNECT(self.source)) as c:c.execute("INSERT INTO answers VALUES(2,999,'synthetic orphan')");c.commit()
        result=self.backup_call()
        self.assertFalse(result[0]);self.assertIn("foreign key",result[1]);self.unchanged(old)

    def test_verification_error_closes_all_owned_connections(self):
        old=self.old_backup();handles=[]
        class Tracked(sqlite3.Connection):
            closed=False
            def close(self):self.closed=True;return super().close()
            def execute(self,sql,*args,**kwargs):
                if sql=="PRAGMA foreign_key_check":raise sqlite3.DatabaseError("SYNTHETIC_CHECK_ERROR")
                return super().execute(sql,*args,**kwargs)
        def connect(*args,**kwargs):
            c=REAL_CONNECT(*args,factory=Tracked,**kwargs);handles.append(c);return c
        with patch.object(native.sqlite3,"connect",side_effect=connect):value=self.backup_call()
        self.assertFalse(value[0]);self.assertIn("SYNTHETIC_CHECK_ERROR",value[1])
        self.assertTrue(all(c.closed for c in handles));self.unchanged(old)

    def test_semantic_failure_preserves_prior_backup(self):
        old=self.old_backup();original=native._native_backup_semantics
        def mismatch(c):
            value=original(c)
            if Path(c.execute("PRAGMA database_list").fetchone()[2])!=self.source:
                value["users_sha256"]="SYNTHETIC-MISMATCH"
            return value
        with patch.object(native,"_native_backup_semantics",side_effect=mismatch):result=self.backup_call()
        self.assertEqual(result,(False,"Backup semantic verification failed."));self.unchanged(old)

    def test_capacity_entry_and_late_verification_refusals(self):
        old=self.old_backup()
        with patch.object(capacity.shutil,"disk_usage",return_value=SimpleNamespace(free=capacity.RESERVE_BYTES-1)):
            result=self.backup_call()
        self.assertFalse(result[0]);self.unchanged(old)
        late=[False];original=native._native_backup_semantics
        def observe(c):
            result=original(c)
            if Path(c.execute("PRAGMA database_list").fetchone()[2])!=self.source:late[0]=True
            return result
        def free(path):return SimpleNamespace(free=capacity.RESERVE_BYTES+native._NATIVE_BACKUP_SLACK_BYTES-1 if late[0] else 2**40)
        with patch.object(native,"_native_backup_semantics",side_effect=observe),patch.object(capacity.shutil,"disk_usage",side_effect=free):
            result=self.backup_call()
        self.assertTrue(late[0]);self.assertFalse(result[0]);self.unchanged(old)

    def test_mid_copy_capacity_and_snapshot_growth_refusals(self):
        old=self.old_backup();calls=[0]
        def free(path):
            calls[0]+=1;return SimpleNamespace(free=2**40 if calls[0]<=3 else capacity.RESERVE_BYTES-1)
        with patch.object(capacity.shutil,"disk_usage",side_effect=free):
            self.assertFalse(self.backup_call()[0])
        self.unchanged(old)
        def grows(src,dst,target,*,pages,progress_hook,backup_artifact):
            self.assertTrue(backup_artifact);progress_hook(0,0,src.execute("PRAGMA page_count").fetchone()[0]+1)
        with patch.object(native,"capacity_backup",side_effect=grows):self.assertFalse(self.backup_call()[0])
        self.unchanged(old)

    def test_protected_sidecars_and_external_target_change_refused(self):
        old=self.old_backup();sidecar=Path(str(self.backup)+"-wal");sidecar.write_bytes(b"PROTECTED")
        self.assertFalse(self.backup_call()[0]);self.unchanged(old);self.assertEqual(sidecar.read_bytes(),b"PROTECTED")
        sidecar.unlink()
        original=native._native_backup_semantics;external=[]
        def changed(c):
            value=original(c)
            if Path(c.execute("PRAGMA database_list").fetchone()[2])!=self.source:
                with self.backup.open("ab") as out:out.write(b"EXTERNAL")
                external.append(self.backup.read_bytes())
            return value
        with patch.object(native,"_native_backup_semantics",side_effect=changed):result=self.backup_call()
        self.assertFalse(result[0]);self.assertIn("CHANGED_DURING_COPY",result[1]);self.assertEqual(self.backup.read_bytes(),external[0])

    def test_concurrent_native_calls_serialize_complete_publication(self):
        active=[0,0];errors=[];barrier=threading.Barrier(3);original=native._native_backup_semantics
        def observed(c):
            if Path(c.execute("PRAGMA database_list").fetchone()[2])!=self.source:
                active[0]+=1;active[1]=max(active[1],active[0])
                try:time.sleep(.025);return original(c)
                finally:active[0]-=1
            return original(c)
        def worker():
            try:
                barrier.wait()
                if self.backup_call()!=(True,"ok"):errors.append("FAILED")
            except Exception as exc:errors.append(type(exc).__name__)
        with patch.object(native,"_native_backup_semantics",side_effect=observed):
            a=threading.Thread(target=worker);b=threading.Thread(target=worker);a.start();b.start();barrier.wait();a.join(5);b.join(5)
        self.assertFalse(a.is_alive() or b.is_alive());self.assertEqual(errors,[]);self.assertEqual(active[1],1)

    def app_backup_function(self,backup=native.sqlite_backup):
        tree=ast.parse((HERE/"app.py").read_text(encoding="utf-8"))
        node=next(n for n in tree.body if isinstance(n,ast.FunctionDef) and n.name=="_pilot_backup")
        scope={"Path":Path,"os":os,"datetime":datetime,"secrets":secrets,"hashlib":hashlib,"sqlite_backup":backup,
            "DB":self.source,"BASE":self.root}
        exec(compile(ast.Module(body=[node],type_ignores=[]),"<native _pilot_backup only>","exec"),scope)
        return scope["_pilot_backup"]

    def test_app_streamed_hash_and_existing_receipt_contract(self):
        function=self.app_backup_function()
        with closing(REAL_CONNECT(self.source)) as c:
            with patch.object(Path,"read_bytes",side_effect=AssertionError("WHOLE_FILE_HASH_FORBIDDEN")):
                result=function(c,"synthetic backup",1)
            self.assertTrue(result["ok"]);self.assertEqual(result["message"],"ok")
            self.assertEqual(set(result),{"id","code","path","sha256","size","ok","message"})
            self.assertEqual(result["sha256"],hashlib.sha256(Path(result["path"]).read_bytes()).hexdigest())
            row=c.execute("SELECT file_sha256,file_size_bytes,integrity_status FROM pilot_backups WHERE id=?",(result["id"],)).fetchone()
            self.assertEqual(row,(result["sha256"],result["size"],"OK"))

    def test_app_failed_backup_still_logs_failure_and_skips_hash(self):
        function=self.app_backup_function(lambda a,b:(False,"SYNTHETIC_REFUSAL"))
        with closing(REAL_CONNECT(self.source)) as c:
            result=function(c,"synthetic failure",1)
            self.assertFalse(result["ok"]);self.assertEqual(result["message"],"SYNTHETIC_REFUSAL")
            self.assertEqual(result["sha256"],"");self.assertEqual(result["size"],0)
            self.assertEqual(c.execute("SELECT integrity_status FROM pilot_backups").fetchone()[0],"FAILED")

    def test_installer_refuses_nonexact_input_before_any_mutation(self):
        runtime=self.root/"incomplete";runtime.mkdir();path=runtime/"app.py";path.write_bytes(b"UNAPPROVED")
        with self.assertRaisesRegex(RuntimeError,"EXACT_CAPTURED630"):installer.apply(runtime,payload_root=HERE)
        self.assertEqual(path.read_bytes(),b"UNAPPROVED");self.assertEqual(list(runtime.iterdir()),[path])

    def test_source_only_installer_adds_only_reviewed_delta_and_replays(self):
        runtime=self.root/"scoremax_runtime_v669b"
        shutil.copytree(CAPTURE,runtime)
        receipt=installer.apply(runtime,payload_root=HERE)
        self.assertEqual(receipt["files"],260);self.assertFalse(receipt["replayed"])
        permitted=set(json.loads((HERE/"runtime_capture_manifest_630.json").read_text()))|set(installer.PAYLOAD_SHA)
        before=installer.source_manifest(runtime,permitted_names=permitted)
        replay=installer.apply(runtime,payload_root=HERE)
        self.assertTrue(replay["replayed"]);self.assertEqual(installer.source_manifest(runtime,permitted_names=permitted),before)
        changed={key for key in before if before.get(key)!=json.loads((HERE/"runtime_capture_manifest_630.json").read_text()).get(key)}
        self.assertEqual(changed,set(installer.PAYLOAD_SHA))

    def test_installer_unknown_files_refused_before_any_root_content_read(self):
        runtime=self.root/"code-root";runtime.mkdir()
        known=runtime/"app.py";known.write_bytes(b"KNOWN-SYNTHETIC-CODE")
        original_read=Path.read_bytes
        for name in ("unknown.py","database.db",".env","static/unknown.png","unknown.pyc","__pycache__/unknown.cpython-313.pyc"):
            unknown=runtime/name;unknown.parent.mkdir(parents=True,exist_ok=True)
            unknown.write_bytes(b"SYNTHETIC-UNKNOWN-ARTIFACT")
            reads=[]
            def refuse_root_read(path):
                if path.is_relative_to(runtime):
                    reads.append(path);raise AssertionError("root contents read before inventory refusal")
                return original_read(path)
            with patch.object(Path,"read_bytes",refuse_root_read):
                with self.assertRaisesRegex(RuntimeError,"UNKNOWN_(BUILD_FILE|BYTECODE)_REFUSED"):
                    installer.apply(runtime,payload_root=HERE)
            self.assertEqual(reads,[])
            self.assertEqual(known.read_bytes(),b"KNOWN-SYNTHETIC-CODE")
            unknown.unlink()

    def test_installer_bytecode_requires_known_source_and_is_not_opened(self):
        runtime=self.root/"code-root";runtime.mkdir();cache=runtime/"__pycache__";cache.mkdir()
        source=runtime/"app.py";source.write_bytes(b"SYNTHETIC-CODE")
        pycs=[cache/"app.cpython-313.pyc",cache/"app.cpython-313.opt-2.pyc",runtime/"app.pyc"]
        for path in pycs:path.write_bytes(b"SYNTHETIC-CACHE")
        original_read=Path.read_bytes;reads=[]
        def only_source_read(path):
            reads.append(path)
            self.assertEqual(path,source)
            return original_read(path)
        with patch.object(Path,"read_bytes",only_source_read):
            actual=installer.source_manifest(runtime,permitted_names={"app.py"})
        self.assertEqual(actual,{"app.py":hashlib.sha256(b"SYNTHETIC-CODE").hexdigest()})
        self.assertEqual(reads,[source])


if __name__=="__main__":
    result=unittest.TextTestRunner(verbosity=2).run(unittest.defaultTestLoader.loadTestsFromTestCase(NativeBackupDelta))
    receipt={"passed":result.wasSuccessful(),"tests_run":result.testsRun,"errors":len(result.errors),"failures":len(result.failures),
        "platform":sys.platform,"python_version":platform.python_version(),"scope":"new tiny native-backup synthetic and source-only installer delta",
        "production_access":False,"services_started":0,"application_imported":False,"historical_suites_replayed":0,
        "source_candidates_sha256":{name:hashlib.sha256((HERE/name).read_bytes()).hexdigest() for name in installer.PAYLOAD_SHA}}
    (HERE/"NATIVE_BACKUP_DELTA_TEST_RESULT_20261024.json").write_text(json.dumps(receipt,indent=2)+"\n",encoding="utf-8")
    print(json.dumps(receipt,sort_keys=True));raise SystemExit(not result.wasSuccessful())
