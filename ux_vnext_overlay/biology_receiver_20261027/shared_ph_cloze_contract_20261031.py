"""Fail-closed compatibility gate for Power House multi-gap Cloze.

The established single Fill Blank contract cannot substitute for a structured,
potentially multi-gap Cloze item. Do not misrepresent it as MCQ or silently
discard independently keyed gap answers or alternatives.
"""
from __future__ import annotations

import ast
from pathlib import Path

MARKER = "SM-SHARED-PH-CLOZE-MULTIGAP-GATE-20261031-1"
TOKEN = "cloze_constructed_response"


def resolve_native_multi_gap(resolver, error_type):
    """Require a pre-existing genuine multi-gap runtime family, not a FIB alias."""
    try:
        native = resolver(TOKEN)
    except error_type as exc:
        raise error_type("NATIVE_MULTI_GAP_CLOZE_CONTRACT_NOT_AVAILABLE") from exc
    if native != TOKEN:
        raise error_type("NATIVE_MULTI_GAP_CLOZE_CONTRACT_NOT_AVAILABLE")
    return native


def apply(root: Path) -> None:
    """Never modify the accepted runtime without verified native multi-gap support."""
    path = Path(root) / "question_contract_engine.py"
    if not path.is_file():
        raise RuntimeError("ACCEPTED_SCOREMAX_CONTRACT_ENGINE_MISSING")
    source = path.read_text(encoding="utf-8")
    tree = ast.parse(source)
    names = {n.name for n in tree.body
             if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef))}
    if not {"canonical_family", "runtime_type_from_row"}.issubset(names):
        raise RuntimeError("SCOREMAX_NATIVE_CONTRACT_ENGINE_DRIFT")

    import importlib.util
    import sys
    spec = importlib.util.spec_from_file_location("_scoremax_cloze_existing", path)
    if spec is None or spec.loader is None:
        raise RuntimeError("SCOREMAX_NATIVE_ENGINE_IMPORT_UNAVAILABLE")
    mod = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = mod
    try:
        spec.loader.exec_module(mod)
        resolve_native_multi_gap(mod.canonical_family, mod.QuestionContractError)
    finally:
        sys.modules.pop(spec.name, None)

    # When genuinely native, reuse existing implementation; no injected aliases.
    print("SM_NATIVE_MULTIGAP_ALREADY_SUPPORTED source_identity_preserved=true", flush=True)
