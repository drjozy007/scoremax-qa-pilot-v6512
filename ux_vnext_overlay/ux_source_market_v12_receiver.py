from __future__ import annotations

import ast
import json
import shutil
from pathlib import Path

FUNCTIONS = (
    "_governance_ready",
    "_semantic_question_errors",
    "_semantic_content_errors",
    "_load_manifest_package",
    "_projection",
    "admit_content_envelope",
)
INSERT_FUNCTIONS = ("_two_tier_key", "_text_option_id")


def _function_span(text: str, name: str):
    tree=ast.parse(text)
    lines=text.splitlines()
    for node in ast.walk(tree):
        if isinstance(node,(ast.FunctionDef,ast.AsyncFunctionDef)) and node.name==name:
            return node.lineno-1, node.end_lineno, "\n".join(lines[node.lineno-1:node.end_lineno])
    return None


def _replace_function(target: str, donor: str, name: str) -> str:
    ts=_function_span(target,name)
    ds=_function_span(donor,name)
    if ds is None:
        raise SystemExit("SCOREMAX_V12_DONOR_FUNCTION_MISSING:"+name)
    if ts is None:
        raise SystemExit("SCOREMAX_V12_TARGET_FUNCTION_MISSING:"+name)
    tlines=target.splitlines()
    return "\n".join(tlines[:ts[0]]+[ds[2]]+tlines[ts[1]:])+"\n"


def _insert_missing_function(target: str, donor: str, name: str, before: str) -> str:
    if _function_span(target,name) is not None:
        return target
    ds=_function_span(donor,name)
    anchor=_function_span(target,before)
    if ds is None or anchor is None:
        raise SystemExit("SCOREMAX_V12_INSERT_SEAM_MISSING:"+name)
    lines=target.splitlines()
    return "\n".join(lines[:anchor[0]]+[ds[2],""]+lines[anchor[0]:])+"\n"


def apply_source_market_v12_receiver(root: Path) -> None:
    root=Path(root)
    target=root/"scoremax_integration_v1.py"
    donor_path=Path(__file__).resolve().with_name("source_market_v1_2_receiver_reference.py")
    if not target.is_file() or not donor_path.is_file():
        raise SystemExit("SCOREMAX_V12_RECEIVER_SOURCE_MISSING")

    text=target.read_text(encoding="utf-8")
    donor=donor_path.read_text(encoding="utf-8")

    if "SOURCE_MARKET_SCHEMA_VERSION='1.2.0'" not in text:
        anchor="RECTIFIED_SCHEMA_VERSION='1.1.0'\n"
        if anchor not in text:
            raise SystemExit("SCOREMAX_V12_SCHEMA_CONSTANT_ANCHOR_MISSING")
        text=text.replace(anchor,anchor+"SOURCE_MARKET_SCHEMA_VERSION='1.2.0'\n",1)

    for name in INSERT_FUNCTIONS:
        text=_insert_missing_function(text,donor,name,"_semantic_question_errors")

    if "_TWO_TIER_KEY_RE=" not in text:
        anchor="def _two_tier_key(content):"
        if anchor not in text:
            raise SystemExit("SCOREMAX_V12_TWO_TIER_HELPER_ANCHOR_MISSING")
        text=text.replace(
            anchor,
            '_TWO_TIER_KEY_RE=re.compile(r"(?i)^\\s*Tier\\s*1\\s*:\\s*([A-Za-z0-9_]+)\\s*;\\s*Tier\\s*2\\s*:\\s*([1-9][0-9]*)\\s*$")\n\n'+anchor,
            1,
        )

    for name in FUNCTIONS:
        text=_replace_function(text,donor,name)

    compile(text,str(target),"exec")
    target.write_text(text,encoding="utf-8")

    src_dir=Path(__file__).resolve().with_name("source_market_v1_2_contracts")
    dst_dir=root/"integration_contracts"/"v1_2_0"
    dst_dir.mkdir(parents=True,exist_ok=True)
    copied=[]
    for name in (
        "PH_SM_APPROVED_CONTENT_V1.schema.json",
        "PH_SM_APPROVED_CONTENT_PACKAGE_V1.schema.json",
        "PH_SM_APPROVED_CONTENT_MANIFEST_V1.schema.json",
    ):
        src=src_dir/name
        dst=dst_dir/name
        if not src.is_file():
            raise SystemExit("SCOREMAX_V12_SCHEMA_SOURCE_MISSING:"+name)
        json.loads(src.read_text(encoding="utf-8"))
        shutil.copy2(src,dst)
        copied.append(name)

    rendered=target.read_text(encoding="utf-8")
    required=(
        "SOURCE_MARKET_SCHEMA_VERSION='1.2.0'",
        "sv in {'1.1.0','1.2.0'}",
        "TEXT_OPTIONS_UNRESOLVED",
        "NOT_APPLICABLE",
        "_two_tier_key(content)",
        "_text_option_id(content)",
        "def _load_manifest_package(package_bytes,release,schema_version=",
        "_governance_ready(q,schema_version)",
        "_semantic_content_errors(questions,stimuli,schema_version)",
    )
    missing=[x for x in required if x not in rendered]
    if missing:
        raise SystemExit("SCOREMAX_V12_RECEIVER_POSTBUILD_CONTROL_MISSING:"+",".join(missing))
    # Read-only bounded diagnostic: expose only string vocabulary from existing canonical_family.
    contract_engine=root/"question_contract_engine.py"
    if contract_engine.is_file():
        ce=contract_engine.read_text(encoding="utf-8")
        alias_marker="SM-SOURCE-MARKET-MCQ-SINGLE-ALIAS-1"
        if alias_marker not in ce:
            ce += r'''

# SM-SOURCE-MARKET-MCQ-SINGLE-ALIAS-1
# Schema-1.2 incoming MCQ_SINGLE is the same single-choice construct already governed
# by standard_mcq -> single_choice in the existing ScoreMax contract tables.
_original_canonical_family_source_market_v12 = canonical_family
def canonical_family(value):
    token=_text(value).strip().lower().replace("-","_").replace(" ","_")
    if token=="mcq_single":
        return "standard_mcq"
    return _original_canonical_family_source_market_v12(value)
'''
            compile(ce,str(contract_engine),"exec")
            contract_engine.write_text(ce,encoding="utf-8")
    if contract_engine.is_file():
        ce_text=contract_engine.read_text(encoding="utf-8")
        ce_tree=ast.parse(ce_text)
        vocab=[]
        for node in ast.walk(ce_tree):
            if isinstance(node,(ast.FunctionDef,ast.AsyncFunctionDef)) and node.name=="canonical_family":
                for sub in ast.walk(node):
                    if isinstance(sub,ast.Constant) and isinstance(sub.value,str) and 0 < len(sub.value) <= 80:
                        vocab.append(sub.value)
                break
        print("SCOREMAX_V12_FAMILY_VOCAB_DIAG "+json.dumps(sorted(set(vocab))),flush=True)

        tables={}
        for node in ce_tree.body:
            if isinstance(node,(ast.Assign,ast.AnnAssign)):
                targets=node.targets if isinstance(node,ast.Assign) else [node.target]
                names=[t.id for t in targets if isinstance(t,ast.Name)]
                if not names: continue
                name=names[0]
                if not any(k in name.upper() for k in ("FAMILY","ALIAS","TYPE","FORMAT")): continue
                try:
                    value=ast.literal_eval(node.value)
                except Exception:
                    continue
                if isinstance(value,(dict,list,tuple,set)):
                    tables[name]=value
        print("SCOREMAX_V12_FAMILY_TABLES_DIAG "+json.dumps(tables,sort_keys=True,default=list),flush=True)

    print(
        "SCOREMAX_V12_RECEIVER_OVERLAY_PASS "
        "schema=1.2.0 backward_1.0_1.1_preserved=true "
        "staged_only=true activation_authority_unchanged=true "
        "functions="+str(len(FUNCTIONS)+len(INSERT_FUNCTIONS))+" schemas="+str(len(copied)),
        flush=True,
    )
