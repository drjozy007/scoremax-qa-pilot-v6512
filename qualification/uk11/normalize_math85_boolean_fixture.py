"""Correct only the UK Maths 85-case Boolean test fixture."""
from pathlib import Path
p=Path("qualification/uk11/math85_native_characterization.py")
s=p.read_text()
a="'correct_option_ids':['No','FALSE']"
b="'correct_option_ids':['No']"
assert s.count(a)==1,"BOOLEAN_FIXTURE_KEY_ANCHOR_DRIFT"
s=s.replace(a,b)
anchor="    if response is None:return '','RAW_INPUT'\n    return str(response),'RAW_INPUT'"
replacement="""    if response is None:return '','RAW_INPUT'
    if q=='Q016' and isinstance(response,str):
        norm=response.strip().casefold()
        if norm in ('false','no'):return 'No','BOOLEAN_UI_ALIAS_PROVISIONAL'
        if norm in ('true','yes'):return 'Yes','BOOLEAN_UI_ALIAS_PROVISIONAL'
    return str(response),'RAW_INPUT'"""
assert s.count(anchor)==1,"BOOLEAN_RESPONSE_ADAPTER_ANCHOR_DRIFT"
p.write_text(s.replace(anchor,replacement))
print("UK11_MATH85_BOOLEAN_FIXTURE_CORRECTED single_key=true display_aliases_provisional=true")
