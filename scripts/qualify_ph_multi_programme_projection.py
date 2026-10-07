#!/usr/bin/env python3
from __future__ import annotations

import ast
import hashlib
import importlib.util
import json
import re
import sqlite3
import sys
from pathlib import Path

POLICY="SCOREMAX-PH-MULTI-PROGRAMME-PROJECTION-QUAL-20261007-1"
ROOT=Path(sys.argv[1] if len(sys.argv)>1 else "scoremax_runtime_v669b").resolve()


def emit(event,**kw):
    print("SCOREMAX_PH_MULTI_PROGRAMME "+json.dumps({"event":event,"policy":POLICY,**kw},sort_keys=True),flush=True)


class Contracts:
    @staticmethod
    def canonical_programme(value):
        value=str(value or "").strip()
        groups={
          "FSc Part 1":("FSc Part 1","FSC_PART_I","FSC_PART_1","HSSC_PART_I"),
          "FSc Part 2":("FSc Part 2","FSC_PART_II","FSC_PART_2","HSSC_PART_II"),
          "MDCAT":("MDCAT",),
          "ECAT":("ECAT",),
        }
        key=value.casefold()
        for name,aliases in groups.items():
            if key in {x.casefold() for x in aliases}:return name
        return value

    @classmethod
    def programme_aliases(cls,value):
        name=cls.canonical_programme(value)
        return {
          "FSc Part 1":["FSc Part 1","FSC_PART_I","FSC_PART_1","HSSC_PART_I"],
          "FSc Part 2":["FSc Part 2","FSC_PART_II","FSC_PART_2","HSSC_PART_II"],
          "MDCAT":["MDCAT"],
          "ECAT":["ECAT"],
        }.get(name,[name] if name else [])

    class QuestionContractError(ValueError):
        pass


class Integration:
    @staticmethod
    def canonical_json(value):
        return json.dumps(value,sort_keys=True,separators=(",",":"),ensure_ascii=False,default=str)


def extract_functions(path:Path,names:list[str]):
    text=path.read_text(encoding="utf-8")
    tree=ast.parse(text)
    lines=text.splitlines()
    out=[]
    found=set()
    for node in tree.body:
        if isinstance(node,ast.FunctionDef) and node.name in names:
            out.append("\n".join(lines[node.lineno-1:node.end_lineno]))
            found.add(node.name)
    missing=set(names)-found
    if missing: raise RuntimeError("MISSING_GENERATED_FUNCTIONS "+",".join(sorted(missing)))
    return "\n\n".join(out)


def main():
    app=ROOT/"app.py"
    catalogue=ROOT/"ux_catalogue_browser.py"
    template=ROOT/"templates"/"ux_catalogue_subject.html"
    if not app.is_file() or not catalogue.is_file() or not template.is_file():
        raise RuntimeError("GENERATED_RUNTIME_MISSING")

    names=["_programme_aliases","canonical_programme","_programme_scope_sql","_programme_chapter_scope_sql",
           "_ph_programme_scope_context","evidence_context"]
    src=extract_functions(app,names)
    ns={"re":re,"question_contracts":Contracts,"integration_v1":Integration,"hashlib":hashlib}
    exec(compile(src,str(app),"exec"),ns)

    c=sqlite3.connect(":memory:")
    c.row_factory=sqlite3.Row
    c.executescript("""
      CREATE TABLE questions(
        id INTEGER PRIMARY KEY, programme TEXT, qualification TEXT, chapter TEXT, subject TEXT,
        ph_projection_owner TEXT, ph_question_id TEXT, ph_question_version_id TEXT,
        question_id TEXT, topic TEXT, subtopic TEXT, learning_outcome TEXT, level TEXT,
        difficulty TEXT, command_word TEXT, cognitive_skill TEXT, family_id TEXT, question_version INTEGER
      );
      CREATE TABLE integration_ph_question_version_store(
        question_id TEXT, question_version_id TEXT, local_question_db_id INTEGER
      );
      CREATE TABLE integration_ph_release_question_membership(
        release_id TEXT, release_version TEXT, question_id TEXT, question_version_id TEXT
      );
      CREATE TABLE integration_ph_content_releases(
        release_id TEXT, release_version TEXT, local_status TEXT,
        programme_id TEXT, subject_id TEXT, chapter_id TEXT
      );
    """)
    c.execute("""INSERT INTO questions VALUES(
      1,'FSc Part 1','FSC','Atomic Structure','Chemistry','POWER_HOUSE',
      'PH-Q-ONE','PH-QV-ONE','PHQ::ONE','Electron configuration','','LO','Exam Ready',
      'Exam Ready','Identify','Knowledge','FAM1',1)""")
    c.execute("INSERT INTO integration_ph_question_version_store VALUES('PH-Q-ONE','PH-QV-ONE',1)")
    releases=[
      ("REL-FSC","1","ACTIVE","FSC_PART_I","CHEMISTRY","CHAPTER::CHEMISTRY::11::02"),
      ("REL-MDCAT","1","ACTIVE","MDCAT","CHEMISTRY","MDCAT::CHEMISTRY::UNIT::02"),
      ("REL-ECAT","1","STAGED","ECAT","CHEMISTRY","ECAT::CHEMISTRY::UNIT::02"),
    ]
    c.executemany("INSERT INTO integration_ph_content_releases VALUES(?,?,?,?,?,?)",releases)
    c.executemany("INSERT INTO integration_ph_release_question_membership VALUES(?,?,?,?)",[
      ("REL-FSC","1","PH-Q-ONE","PH-QV-ONE"),
      ("REL-MDCAT","1","PH-Q-ONE","PH-QV-ONE"),
      ("REL-ECAT","1","PH-Q-ONE","PH-QV-ONE"),
    ])

    def ids_for(programme):
        aliases=Contracts.programme_aliases(programme)
        sql,args=ns["_programme_scope_sql"](aliases,"q")
        return [r["id"] for r in c.execute("SELECT q.id FROM questions q WHERE "+sql,args)]

    if ids_for("FSc Part 1")!=[1]: raise RuntimeError("FSC_MEMBERSHIP_NOT_VISIBLE")
    if ids_for("MDCAT")!=[1]: raise RuntimeError("MDCAT_MEMBERSHIP_NOT_VISIBLE")
    if ids_for("ECAT")!=[]: raise RuntimeError("STAGED_ECAT_LEAKED")

    sql,args=ns["_programme_chapter_scope_sql"]("MDCAT","MDCAT::CHEMISTRY::UNIT::02","q")
    if [r["id"] for r in c.execute("SELECT q.id FROM questions q WHERE "+sql,args)]!=[1]:
        raise RuntimeError("MDCAT_UNIT_SCOPE_FAIL")
    sql,args=ns["_programme_chapter_scope_sql"]("FSc Part 1","Atomic Structure","q")
    if [r["id"] for r in c.execute("SELECT q.id FROM questions q WHERE "+sql,args)]!=[1]:
        raise RuntimeError("FSC_HUMAN_CHAPTER_COMPAT_FAIL")

    q=dict(c.execute("SELECT * FROM questions WHERE id=1").fetchone())
    fsc=ns["evidence_context"](c,q,"FSc Part 1",1)
    mdcat=ns["evidence_context"](c,q,"MDCAT",1)
    if fsc["programme"]!="FSc Part 1" or fsc["chapter"]!="Atomic Structure":
        raise RuntimeError("FSC_EVIDENCE_DRIFT")
    if mdcat["programme"]!="MDCAT" or mdcat["chapter"]!="MDCAT::CHEMISTRY::UNIT::02":
        raise RuntimeError("MDCAT_EVIDENCE_SCOPE_FAIL")
    if fsc["ph_question_id"]!=mdcat["ph_question_id"]!="":
        raise RuntimeError("CANONICAL_IDENTITY_DRIFT")

    cat_text=catalogue.read_text(encoding="utf-8")
    tpl=template.read_text(encoding="utf-8")
    for token in (
      "active_ph_membership_drives_availability=true",
      "integration_ph_release_question_membership",
      "integration_ph_question_version_store",
      "local_status='ACTIVE'",
      "_catalogue_item_scope",
      "url_for('chapter_page',subject=subject,chapter=scope[0])",
    ):
        if token not in cat_text: raise RuntimeError("CATALOGUE_CONTROL_MISSING "+token)
    if "{% if ch.available and ch.url %}<a href=" not in tpl:
        raise RuntimeError("CATALOGUE_LINK_CONTROL_MISSING")

    emit("PASS",
      one_canonical_question_row=True,
      fsc_visible=True,
      mdcat_visible=True,
      staged_ecat_hidden=True,
      fsc_human_chapter_preserved=True,
      mdcat_release_unit_frozen=True,
      catalogue_membership_driven=True,
      production_mutation=False,
      learner_release=False)
    return 0


if __name__=="__main__":
    try: raise SystemExit(main())
    except Exception as exc:
        emit("FAIL",error_type=type(exc).__name__,detail=str(exc)[:2000],
             production_mutation=False,learner_release=False)
        raise
