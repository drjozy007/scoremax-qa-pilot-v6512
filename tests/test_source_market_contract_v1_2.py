import json
from pathlib import Path
from jsonschema import Draft202012Validator

ROOT=Path(__file__).resolve().parents[1]
SCHEMA_11=ROOT/"hosted_runtime_base_v6512/integration_contracts/v1_1_0/PH_SM_APPROVED_CONTENT_V1.schema.json"
SCHEMA_12=ROOT/"hosted_runtime_base_v6512/integration_contracts/v1_2_0/PH_SM_APPROVED_CONTENT_V1.schema.json"

def _architecture(schema):
    return schema["$defs"]["question"]["properties"]["architecture"]

def test_source_market_schema_relaxes_only_cross_market_lineage():
    s11=json.loads(SCHEMA_11.read_text())
    s12=json.loads(SCHEMA_12.read_text())
    a11=_architecture(s11); a12=_architecture(s12)
    assert s12["properties"]["schema_version"]["const"]=="1.2.0"
    assert a11["properties"]["claim_family_id"]["type"]=="string"
    assert a12["properties"]["claim_family_id"]["type"]==["string","null"]
    assert a12["properties"]["reasoning_seed_id"]["type"]==["string","null"]
    assert a12["properties"]["transfer_level"]["type"]==["string","null"]
    assert a12["properties"]["knowledge_node_ids"]["minItems"]==0
    for field in ("evidence_role","independent_mastery_eligible","independent_mastery_weight","mastery_level","mastery_ceiling","cognitive_demand"):
        assert field in a12["required"]

def test_scoremax_accepts_1_2_without_dropping_old_versions():
    source=(ROOT/"hosted_runtime_base_v6512/scoremax_integration_v1.py").read_text()
    assert "SOURCE_MARKET_SCHEMA_VERSION='1.2.0'" in source
    assert "{'1.0.0','1.1.0',SOURCE_MARKET_SCHEMA_VERSION}" in source
    assert "v1_2_0" in source
