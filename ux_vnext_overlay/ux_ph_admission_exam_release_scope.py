from __future__ import annotations

import ast
from pathlib import Path

MARKER="SCOREMAX_PH_ADMISSION_EXAM_RELEASE_SCOPE_V1"


def _replace_function(text: str, name: str, source: str) -> str:
    tree=ast.parse(text); lines=text.splitlines()
    node=next((n for n in tree.body if isinstance(n,ast.FunctionDef) and n.name==name),None)
    if not node:
        raise RuntimeError("MISSING_FUNCTION:"+name)
    lines[node.lineno-1:node.end_lineno]=source.splitlines()
    return "\n".join(lines)+"\n"


def apply_ph_admission_exam_release_scope(root: Path) -> None:
    root=Path(root)
    p=root/"scoremax_integration_v1.py"
    text=p.read_text(encoding="utf-8")
    if MARKER in text:
        print(MARKER+" already_applied=true",flush=True);return

    helper=r'''
def _ph_release_scope_compatible(curr,rel):
    """Narrow compatibility for one canonical FSc question allocated by PH to an admission exam.

    Canonical curriculum remains immutable. Release membership may supply MDCAT/ECAT
    programme + unit context only when market and subject still match and the source
    curriculum is FSc. All other scope differences remain fail-closed.
    """
    def norm(v):
        return ''.join(ch for ch in str(v or '').strip().upper() if ch.isalnum())
    display=(curr.get('display') or {}) if isinstance(curr,dict) else {}
    source_tokens=[curr.get('programme_id'),display.get('programme'),curr.get('qualification_id'),display.get('qualification')]
    source_fsc=any(('FSC' in norm(x) or 'HSSC' in norm(x) or 'INTERMEDIATE' in norm(x)) for x in source_tokens if x)
    dest=norm(rel.get('programme_id'))
    admission=dest in {'MDCAT','ECAT'}
    same_market=norm(curr.get('market_id'))==norm(rel.get('market_id')) and bool(norm(rel.get('market_id')))
    same_subject=norm(curr.get('subject_id') or display.get('subject'))==norm(rel.get('subject_id')) and bool(norm(rel.get('subject_id')))
    return bool(source_fsc and admission and same_market and same_subject)


def _ph_release_scope_mismatch(curr,rel):
    cross=_ph_release_scope_compatible(curr,rel)
    errors=[]
    for rk in ('market_id','programme_id','subject_id','chapter_id'):
        if str(curr.get(rk) or '')==str(rel.get(rk) or ''):
            continue
        if cross and rk in {'programme_id','chapter_id'}:
            continue
        errors.append(rk)
    return errors
'''
    anchor="def admit_content_envelope(c,envelope,content_sha_header=''):\n"
    if anchor not in text:
        raise RuntimeError("ADMIT_CONTENT_ANCHOR_MISSING")
    text=text.replace(anchor,helper+"\n\n"+anchor,1)

    old="""        curr=q.get('curriculum') or {}
        for rk in ('market_id','programme_id','subject_id','chapter_id'):
            if str(curr.get(rk) or '')!=str(rel.get(rk) or ''):
                errors.append({'code':'SCOPE_MISMATCH','path':f'payload.questions[{i}].curriculum.{rk}','message':'Question scope differs from release scope','retryable':False})
"""
    new="""        curr=q.get('curriculum') or {}
        for rk in _ph_release_scope_mismatch(curr,rel):
            errors.append({'code':'SCOPE_MISMATCH','path':f'payload.questions[{i}].curriculum.{rk}','message':'Question scope differs from release scope','retryable':False})
"""
    if old not in text:
        raise RuntimeError("SCOPE_VALIDATION_BLOCK_MISSING")
    text=text.replace(old,new,1)
    text+="\n# "+MARKER+"\n"
    compile(text,str(p),'exec')
    p.write_text(text,encoding="utf-8")
    print(MARKER+" fsc_to_admission_exam_only=true market_same=true subject_same=true canonical_curriculum_immutable=true fail_closed=true",flush=True)
