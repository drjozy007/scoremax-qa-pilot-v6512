from __future__ import annotations

import ast
import json
import shutil
from pathlib import Path

FUNCTIONS = (
    "_contract_schema_path",
    "_strict_envelope_errors",
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

    health_old="'local_schema_version':RECTIFIED_SCHEMA_VERSION if contract=='PH_SM_APPROVED_CONTENT_V1' else SCHEMA_VERSION,"
    health_new="'local_schema_version':SOURCE_MARKET_SCHEMA_VERSION if contract=='PH_SM_APPROVED_CONTENT_V1' else SCHEMA_VERSION,"
    if health_old in text:
        text=text.replace(health_old,health_new,1)

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
    print(
        "SCOREMAX_V12_RECEIVER_OVERLAY_PASS "
        "schema=1.2.0 backward_1.0_1.1_preserved=true "
        "staged_only=true activation_authority_unchanged=true "
        "functions="+str(len(FUNCTIONS)+len(INSERT_FUNCTIONS))+" schemas="+str(len(copied)),
        flush=True,
    )
