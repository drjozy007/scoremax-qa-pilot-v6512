from __future__ import annotations

import json
import re

_LABEL_RE=re.compile(r"^\s*([A-Za-z0-9_]+)\s*[\).:\-]\s*(\S.*)$")


def parse_matching_key(value):
    if isinstance(value,dict):
        raw=value
    else:
        try:
            raw=json.loads(str(value or '').strip())
        except Exception:
            return None
    if not isinstance(raw,dict) or not raw:
        return None
    out={}
    for k,v in raw.items():
        left=str(k or '').strip(); right=str(v or '').strip()
        if not left or not right or left in out:
            return None
        out[left]=right
    return out or None


def canonical_matching_response(value):
    key=parse_matching_key(value)
    if key is None:
        return ''
    return json.dumps(key,sort_keys=True,separators=(',',':'),ensure_ascii=False)


def _prefix(token):
    m=re.match(r"^[A-Za-z_]+",str(token or ''))
    return m.group(0).upper() if m else ''


def parse_matching_surface(stimulus_text, key_value):
    key=parse_matching_key(key_value)
    if key is None:
        return {'valid':False,'error':'MATCHING_KEY_INVALID','left':[],'right':[],'key':{}}
    labels={}
    duplicate=set()
    for raw in str(stimulus_text or '').splitlines():
        m=_LABEL_RE.match(raw)
        if not m:
            continue
        label=m.group(1).strip()
        text=m.group(2).strip()
        if label in labels and labels[label]!=text:
            duplicate.add(label)
        labels[label]=text
    if duplicate:
        return {'valid':False,'error':'MATCHING_LABEL_DUPLICATE','left':[],'right':[],'key':key}
    required=set(key.keys())|set(key.values())
    missing=sorted(required-set(labels))
    if missing:
        return {'valid':False,'error':'MATCHING_VISIBLE_LABEL_MISSING:'+','.join(missing),'left':[],'right':[],'key':key}
    right_prefixes={_prefix(v) for v in key.values() if _prefix(v)}
    right_ids=[label for label in labels if label not in key and (not right_prefixes or _prefix(label) in right_prefixes)]
    if not set(key.values()).issubset(set(right_ids)):
        return {'valid':False,'error':'MATCHING_RIGHT_SET_INCOMPLETE','left':[],'right':[],'key':key}
    left=[{'id':lid,'text':labels[lid]} for lid in key.keys()]
    right=[{'id':rid,'text':labels[rid]} for rid in right_ids]
    return {'valid':True,'error':'','left':left,'right':right,'key':key}
