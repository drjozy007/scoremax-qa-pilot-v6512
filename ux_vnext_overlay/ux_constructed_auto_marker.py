from __future__ import annotations

import json
import re
from written_response_engine import mark_written_response

_MARKER='SCOREMAX_CONSTRUCTED_AUTO_MARKER_V1'


def _norm(value):
    return re.sub(r'\\s+',' ',str(value or '').strip()).casefold()


def _accepted_from_cfg(answer_cfg, fallback=''):
    vals=[]
    for value in (answer_cfg or {}).get('accepted_answers') or []:
        token=str(value or '').strip()
        if token and token not in vals:
            vals.append(token)
    fb=str(fallback or '').strip()
    if fb and fb not in vals:
        vals.insert(0,fb)
    return vals


def _looks_symbolic(value):
    text=str(value or '').strip()
    if not text:
        return False
    letters=re.findall(r'[A-Za-z]+',text)
    digits=len(re.findall(r'\\d',text))
    math=len(re.findall(r'[=+*/^<>⟨⟩²³₀-₉-]',text))
    # Compact numeric/list/formula responses should not go through prose similarity.
    if digits and len(letters)<=4:
        return True
    if math>=2 and len(letters)<=8:
        return True
    if re.fullmatch(r'[\\s\\d,.;:+\\-*/^()]+',text):
        return True
    return False


def compile_contract(answer_cfg, fallback_answer='', marks=1.0, stem='', command_word=''):
    accepted=_accepted_from_cfg(answer_cfg,fallback_answer)
    if not accepted:
        return None
    maximum=float(marks or 1.0)
    symbolic=all(_looks_symbolic(x) for x in accepted)
    mode='EXACT' if symbolic else 'SEMANTIC'
    command=str(command_word or '').strip().lower()
    if not command:
        first=(str(stem or '').strip().split() or [''])[0].strip('?:,.').lower()
        if first in {'explain','describe','state','identify','calculate','determine','compare','justify','evaluate','predict','define'}:
            command=first
    return {
      'version':'SM-CONSTRUCTED-AUTO-1',
      'mode':mode,
      'accepted_answers':accepted,
      'maximum_marks':maximum,
      'command_verb':command,
    }


def is_markable(answer_cfg, fallback_answer='', marks=1.0, stem='', command_word=''):
    return compile_contract(answer_cfg,fallback_answer,marks,stem,command_word) is not None


def mark(contract, response):
    if not contract:
        return {'markable':False,'marks_awarded':0.0,'maximum_marks':0.0,'is_correct':False,
                'confidence':0.0,'status':'NO_MARKING_CONTRACT','feedback':[]}
    answer=str(response or '').strip()
    maximum=float(contract.get('maximum_marks') or 1.0)
    if not answer:
        return {'markable':True,'marks_awarded':0.0,'maximum_marks':maximum,'is_correct':False,
                'confidence':1.0,'status':'RESPONSE_INCOMPLETE','feedback':['No response was submitted.']}
    accepted=list(contract.get('accepted_answers') or [])
    if contract.get('mode')=='EXACT':
        ok=_norm(answer) in {_norm(x) for x in accepted}
        return {'markable':True,'marks_awarded':maximum if ok else 0.0,'maximum_marks':maximum,
                'is_correct':ok,'confidence':1.0,'status':'MARK_CONFIRMED',
                'feedback':[] if ok else ['Check the required value, expression or ordered result.']}

    model=accepted[0]
    question={
      'maximum_marks':maximum,
      'command_verb':contract.get('command_verb') or '',
      'required_mark_points':[{
        'id':'P1','description':model,'marks':maximum,
        'required_terms':[],
        'acceptable_paraphrases':accepted[1:],
        'accepted_phrases':accepted,
        'causal_link_required':str(contract.get('command_verb') or '').lower() in {'explain','analyse','justify','predict'},
        'improvement_instruction':'Include the essential scientific idea expressed in the approved answer.'
      }],
      'contradictions':[],
      'misconceptions':[],
    }
    result=mark_written_response(question,answer,{
      'confirmed_confidence':0.72,
      'grader_a_version':'local-rubric-a-1',
      'grader_b_version':'local-rubric-b-1',
      'reconciliation_policy_version':'local-conservative-1',
    })
    awarded=float(result.get('proposed_mark') or 0)
    return {
      'markable':True,'marks_awarded':awarded,'maximum_marks':maximum,
      'is_correct':awarded>=maximum-1e-9,
      'confidence':float(result.get('confidence') or 0),
      'status':str(result.get('status') or ''),
      'feedback':list(result.get('feedback') or []),
      'result':result,
    }


def fixture_qualification():
    exact=compile_contract({'accepted_answers':['-314']},'-314',1,'Calculate the value.','calculate')
    if not mark(exact,'-314')['is_correct'] or mark(exact,'314')['is_correct']:
        raise RuntimeError('CONSTRUCTED_EXACT_FIXTURE_FAIL')
    semantic=compile_contract(
      {'accepted_answers':['Irregular motion arises from repeated microscopic collisions.']},
      '',1,'Explain why a suspended particle shows irregular Brownian motion.','explain')
    good=mark(semantic,'The particle moves irregularly because repeated microscopic collisions strike it from different directions.')
    bad=mark(semantic,'The particle is stationary because gravity prevents molecular collisions.')
    if not good['markable'] or good['marks_awarded']<=bad['marks_awarded']:
        raise RuntimeError('CONSTRUCTED_SEMANTIC_FIXTURE_FAIL')
    return {'exact':True,'semantic':True,'fail_closed':compile_contract({},'',1,'','') is None}
