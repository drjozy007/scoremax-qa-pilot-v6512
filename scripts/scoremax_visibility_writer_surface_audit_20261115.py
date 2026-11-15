"""Read-only audit of source mutations affecting ScoreMax governed visibility.

Inspect every generated Python file in the accepted runtime. Report which
functions contain SQL mutations to the seven canonical authority tables, and
flag indirect/dynamic writes for manual review. This is an inventory,
NOT proof that all writers are already covered by triggers.
"""
import ast, json, re, sys
from pathlib import Path
WATCHED=("questions","question_families","integration_ph_question_version_store",
         "integration_ph_release_question_membership","integration_ph_content_releases",
         "integration_ph_product_activation_authorizations",
         "ph_bridge_staged_withdrawal_exclusions_v6611e")
RE_STR=r"(?:INSERT\s+(?:OR\s+\w+\s+)?INTO|REPLACE\s+INTO|UPDATE|DELETE\s+FROM)"
SQL_RE=re.compile(r"\b"+RE_STR+r"\s+([A-Za-z_][A-Za-z0-9_]*)",re.I)
DEF_RE=re.compile(r"\b(?:def|async def)\s+(\w+)\s*\(")
def main(root):
    out={}
    hazards=[]
    for file in sorted(root.rglob("*.py")):
        if any(part in {"tests","__pycache__"} for part in file.parts):continue
        source=file.read_text(encoding="utf8")
        try:tree=ast.parse(source)
        except SyntaxError:continue
        chunks=[(node.name,ast.get_source_segment(source,node) or "")
                for node in ast.walk(tree)
                if isinstance(node,(ast.FunctionDef,ast.AsyncFunctionDef))]
        chunks.append(("<module>",source))
        for name,body in chunks:
            for match in SQL_RE.finditer(body):
                table=match.group(1).lower()
                if table not in WATCHED:continue
                key=f"{file.relative_to(root)}::{name}"
                out.setdefault(table,set()).add(key)
            if name!="<module>" and any(word in body for word in ("executescript","cursor.executemany","executemany(")):
                for table in WATCHED:
                    if table in body and not any(m.group(1).lower()==table for m in SQL_RE.finditer(body)):
                        hazards.append((str(file.relative_to(root)),name,table,"DYNAMIC_OR_INDIRECT_WRITE"))
    rows={table:sorted(out.get(table,set())) for table in WATCHED}
    for table in WATCHED:
        if not rows[table]:
            raise RuntimeError("AUTHORITY_TABLE_WITHOUT_DETECTED_WRITER:"+table)
    print("SCOREMAX_VISIBILITY_WRITER_AUDIT="+json.dumps({
       "source":"generated_existing_runtime","tables":rows,
       "indirect_ambiguity":sorted(set(hazards))[:150],
       "all_writers_certified":False,"production_db_access":False,
       "recommended_action":"manual_review_dynamic_writers_and_atomic_invalidation_before_live_migration"
    },sort_keys=True),flush=True)
if __name__=="__main__":
    if len(sys.argv)!=2:raise SystemExit("Specify generated runtime root")
    main(Path(sys.argv[1]).resolve())
