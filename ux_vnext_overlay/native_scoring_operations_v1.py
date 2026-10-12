"""Bounded operations for the EXISTING PH/ScoreMax marking contract.

No network, model, database, independent grading entrypoint or topic/ID dispatch.
The written-response engine remains responsible for points and final results.
"""
from __future__ import annotations
import ast
import copy
from fractions import Fraction
import hashlib
import json
import re

VERSION = 'PH-NATIVE-OPERATIONS-1'
EXTENDED_VERSION = 'PH-NATIVE-OPERATIONS-2'
RUNTIME_VERSION = 'SM-RUBRIC-NATIVE-1'


def stable_hash(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True, separators=(',', ':'),
                                    ensure_ascii=False, allow_nan=False).encode()).hexdigest()


def _text(value):
    if not isinstance(value, str) or len(value) > 10000:
        raise ValueError('TEXT_LIMIT')
    return ' '.join(value.strip().rstrip('.;').split())


def _fraction(value):
    if isinstance(value, bool) or not re.fullmatch(r'[+-]?(?:\d+(?:\.\d*)?|\.\d+)(?:[eE][+-]?\d{1,3})?', str(value)):
        raise ValueError('FINITE_DECIMAL_REQUIRED')
    if len(str(value)) > 80:
        raise ValueError('NUMBER_LIMIT')
    out = Fraction(str(value))
    if out.numerator.bit_length() > 512 or out.denominator.bit_length() > 512:
        raise ValueError('NUMBER_LIMIT')
    return out


def _polynomial_equation(text, symbols, allowed_denominators=()):
    """Exact rational equation signature; extends retained polynomial AST semantics.

    No eval/sympify, sampling, functions, cancellation of unknown domain factors,
    or treating different true identities as evidence of the requested relation.
    """
    text = _text(text).replace('−', '-').replace('×', '*').replace('·', '*').replace('÷', '/').replace('^', '**')
    if len(text) > 500 or text.count('=') != 1 or not 1 <= len(symbols) <= 8:
        raise ValueError('EQUATION_GRAMMAR')
    if any(not re.fullmatch('[A-Za-z]', s) for s in symbols) or len(set(symbols)) != len(symbols):
        raise ValueError('SYMBOLS_INVALID')
    zero = (0,) * len(symbols)
    one = {zero: Fraction(1)}
    budget = [0]
    denominators = set()

    def clean(p):
        p = {k:v for k,v in p.items() if v}
        if len(p) > 128 or any(sum(k) > 8 or v.numerator.bit_length() > 512 or v.denominator.bit_length() > 512 for k,v in p.items()):
            raise ValueError('EXPRESSION_COMPLEXITY')
        return p

    def add(a, b, sign=1):
        p = dict(a)
        for k,v in b.items(): p[k] = p.get(k, Fraction(0)) + sign*v
        return clean(p)

    def mul(a, b):
        budget[0] += len(a)*len(b)
        if budget[0] > 3000: raise ValueError('EXPRESSION_BUDGET')
        p = {}
        for k,v in a.items():
            for l,w in b.items():
                m = tuple(x+y for x,y in zip(k,l)); p[m] = p.get(m,Fraction(0)) + v*w
        return clean(p)

    def parse(value):
        # Implicit products only between declared single-letter symbols or brackets.
        if re.search(r'[^A-Za-z0-9+*/().\s-]', value): raise ValueError('EXPRESSION_GRAMMAR')
        tokens = re.findall(r'\d+(?:\.\d*)?|\.\d+|\*\*|[A-Za-z]|[+*/()-]', value)
        if len(tokens) > 100: raise ValueError('EXPRESSION_LIMIT')
        if ''.join(tokens) != re.sub(r'\s+', '', value): raise ValueError('EXPRESSION_GRAMMAR')
        out = []
        for token in tokens:
            if out:
                prev = out[-1]
                if (prev[-1:].isdigit() or prev==')' or prev in symbols) and (token=='(' or token in symbols): out.append('*')
                elif (prev==')' or prev in symbols) and token[0].isdigit(): out.append('*')
            out.append(token)
        value = ''.join(out)
        tree = ast.parse(value, mode='eval')
        if sum(1 for _ in ast.walk(tree)) > 140: raise ValueError('EXPRESSION_LIMIT')

        def walk(n, depth=0):
            if depth > 18: raise ValueError('EXPRESSION_DEPTH')
            if isinstance(n, ast.Constant) and type(n.value) in (int,float):
                return clean({zero:_fraction(ast.get_source_segment(value,n))}), one
            if isinstance(n, ast.Name) and n.id in symbols:
                return {tuple(int(i==symbols.index(n.id)) for i in range(len(symbols))):Fraction(1)}, one
            if isinstance(n, ast.UnaryOp) and isinstance(n.op,(ast.USub,ast.UAdd)):
                a,b=walk(n.operand,depth+1)
                return ({k:-v for k,v in a.items()} if isinstance(n.op,ast.USub) else a),b
            if isinstance(n,ast.BinOp):
                a,b=walk(n.left,depth+1)
                if isinstance(n.op,ast.Pow):
                    if not isinstance(n.right,ast.Constant) or type(n.right.value) is not int or not 0 <= n.right.value <= 4:
                        raise ValueError('POWER_LIMIT')
                    if not a and n.right.value==0: raise ValueError('UNDEFINED_POWER')
                    an,bn=one,one
                    for _ in range(n.right.value): an,bn=mul(an,a),mul(bn,b)
                    return an,bn
                c,d=walk(n.right,depth+1)
                if isinstance(n.op,ast.Add): return add(mul(a,d),mul(c,b)),mul(b,d)
                if isinstance(n.op,ast.Sub): return add(mul(a,d),mul(c,b),-1),mul(b,d)
                if isinstance(n.op,ast.Mult): return mul(a,c),mul(b,d)
                if isinstance(n.op,ast.Div):
                    if len(c)!=1: raise ValueError('UNAPPROVED_DENOMINATOR_DOMAIN')
                    mono=next(iter(c))
                    for i,e in enumerate(mono):
                        if e:
                            if symbols[i] not in allowed_denominators: raise ValueError('UNAPPROVED_DENOMINATOR_DOMAIN')
                            denominators.add(symbols[i])
                    return mul(a,d),mul(b,c)
            raise ValueError('EXPRESSION_SYNTAX_UNSUPPORTED')
        return walk(tree.body)
    a,b=parse(text.split('=')[0]);c,d=parse(text.split('=')[1])
    p=add(mul(a,d),mul(c,b),-1)
    if not p: raise ValueError('IDENTITY_IS_NOT_REQUESTED_RELATION')
    scale=p[sorted(p)[0]]
    return tuple((k,str(p[k]/scale)) for k in sorted(p)), sorted(denominators)


def _units(text):
    """Representation normalisation, not inferred unit conversions."""
    supers = str.maketrans('⁰¹²³⁴⁵⁶⁷⁸⁹⁻⁺','0123456789-+')
    text=re.sub(r'[⁰¹²³⁴⁵⁶⁷⁸⁹⁻⁺]+',lambda m:'^'+m[0].translate(supers),text)
    text=re.sub(r'([A-Za-z]+)([+-]?\d+)',r'\1^\2',text)
    text=text.replace('·','*').replace('×','*').replace('−','-')
    tokens=re.findall(r'[A-Za-z]+|\^|[+-]?\d+|[*/()]',text)
    if ''.join(tokens)!=re.sub(r'\s+','',text) or len(tokens)>60: raise ValueError('UNIT_GRAMMAR')
    pos=[0]
    def group(depth=0):
        if depth>5: raise ValueError('UNIT_DEPTH')
        result={};sign=1;need=True
        while pos[0]<len(tokens):
            t=tokens[pos[0]]
            if t==')': break
            if t in ('*','/'):
                if need: raise ValueError('UNIT_GRAMMAR')
                sign=1 if t=='*' else -1;pos[0]+=1;need=True;continue
            if t=='(':
                pos[0]+=1;part=group(depth+1)
                if pos[0]>=len(tokens) or tokens[pos[0]]!=')': raise ValueError('UNIT_GRAMMAR')
                pos[0]+=1
            elif re.fullmatch('[A-Za-z]+',t): part={t:1};pos[0]+=1
            else: raise ValueError('UNIT_GRAMMAR')
            exponent=1
            if pos[0]<len(tokens) and tokens[pos[0]]=='^':
                pos[0]+=1
                if pos[0]>=len(tokens) or not re.fullmatch(r'[+-]?\d+',tokens[pos[0]]): raise ValueError('UNIT_EXPONENT')
                exponent=int(tokens[pos[0]]);pos[0]+=1
                if not -12<=exponent<=12: raise ValueError('UNIT_EXPONENT')
            for unit,e in part.items(): result[unit]=result.get(unit,0)+sign*exponent*e
            sign=1;need=False
        if need: raise ValueError('UNIT_GRAMMAR')
        return {k:v for k,v in result.items() if v}
    result=group()
    if pos[0]!=len(tokens): raise ValueError('UNIT_GRAMMAR')
    return [[k,v] for k,v in sorted(result.items())]


def _quantity(text, label=''):
    text=_text(text)
    if '=' in text:
        if not label or text.count('=')!=1 or text.split('=')[0].strip()!=label: raise ValueError('QUANTITY_LABEL')
        text=text.split('=')[1].strip()
    m=re.fullmatch(r'([+-]?(?:\d+(?:\.\d*)?|\.\d+)(?:[eE][+-]?\d{1,3})?)\s+(.+)',text)
    if not m: raise ValueError('QUANTITY_GRAMMAR')
    return _fraction(m[1]),_units(m[2]),m[1]


def derive_operations(source):
    """Recognise explicit governed constructs, never prose similarity or IDs.

    Unsupported policy/representation/mark-allocation shapes return no operations.
    Source fields remain academic authority. This function confers none.
    """
    try:
        if not isinstance(source,dict): return None
        if source.get('Required_Produced_Representation')!='NONE': return None
        if source.get('Scoring_Mode')!='DETERMINISTIC_NORMALIZED': return None
        if source.get('Auto_Marking_Eligibility') not in {'ELIGIBLE_DETERMINISTIC_NORMALIZED','ELIGIBLE_DETERMINISTIC_NORMALIZED_WITH_EQUIVALENT_TERMS'}: return None
        if int(source.get('Mark_Point_Count',0))!=1 or _fraction(source['Marks'])!=_fraction(source['Mark_Point_Values']): return None
        answer=_text(source['Canonical_Accepted_Evidence'])
        if answer!=_text(source['Model_Answer']): return None
        kind=None;op={}
        if source.get('SAQ_Demand_Archetype')=='ARCH-STATE-RELATION' and answer.count('=')==1:
            if source.get('Equation_Equivalence_Rule')!='Algebraically equivalent rearrangements are accepted when they preserve the same relationship.': return None
            symbols=sorted(set(re.findall('[A-Za-z]',answer)))
            original,_=_polynomial_equation(answer,symbols,())
            # Only explicit, algebraically verified source rearrangements authorise
            # denominator domains; do not assume every symbol is nonzero.
            allowed=set();forms=[answer]
            for candidate in str(source.get('Unacceptable_Near_Misses','')).split(';')[1:]:
                candidate=_text(candidate)
                try:
                    signature,used=_polynomial_equation(candidate,symbols,symbols)
                    if signature==original: allowed.update(used);forms.append(candidate)
                except (ValueError,SyntaxError): pass
            kind='RATIONAL_EQUATION';op={'symbols':symbols,'allowed_denominators':sorted(allowed),'accepted_source_forms':forms}
        else:
            m=re.fullmatch(r'([A-Za-z])\s*=\s*(.+)',answer)
            if m:
                try: value,units,literal=_quantity(answer,m[1])
                except ValueError: return None
                if source.get('Numerical_Tolerance_Rule')!='NOT_APPLICABLE' or source.get('Significant_Figures_Rule')!='NOT_APPLICABLE': return None
                kind='QUANTITY';op={'label':m[1],'value':str(value),'units':units,'absolute_tolerance':'0','significant_figures':None}
            else:
                stem=str(source.get('Learner_Question','')).casefold()
                exclusion=str(source.get('Unacceptable_Near_Misses',''))
                m=re.fullmatch(r'Do not call .+? ([A-Za-z]+); .+? is ([A-Za-z]+)\.',exclusion)
                if 'what process ' not in stem or not m: return None
                negative,positive=m[1],m[2]
                if not answer.casefold().startswith(positive.casefold()+' ') or positive.casefold()==negative.casefold(): return None
                kind='CONTROLLED_TERM';op={'term':positive,'excluded_term':negative,'canonical':answer,
                    'excluded_canonical':negative+answer[len(positive):], 'case_sensitive':False}
        return [{'point_id':'p1','kind':kind,**op}]
    except (KeyError,ValueError,TypeError,OverflowError,SyntaxError): return None


def attach_native_operations(rubric, source):
    operations=derive_operations(source)
    version=VERSION
    if not operations:
        operations=derive_controlled_operations(source)
        version=EXTENDED_VERSION
    if not operations: return None
    body=copy.deepcopy(rubric)
    if body.get('version')!='PH-SAQ-SCORING-CONTRACT-1': return None
    if not _original_points_match(body,source,operations): return None
    if 'native_scoring' in body: return body if compile_native_rubric(body,source['Marks'],source['Learner_Question'],source['Model_Answer']) else None
    original=body.pop('contract_sha256',None)
    if original!=stable_hash(body): return None
    body['native_scoring']={'version':version,'original_contract_sha256':original,
        'source_row_sha256':stable_hash(source),'source_row':copy.deepcopy(source),'operations':operations}
    # A capability binding does not erase the source's eligibility/policy declaration.
    body['contract_sha256']=stable_hash(body)
    return body


def compile_native_rubric(rubric, maximum, stem, answer):
    try:
        binding=rubric['native_scoring'];source=binding['source_row']
        if binding['version'] not in (VERSION,EXTENDED_VERSION) or binding['source_row_sha256']!=stable_hash(source): return None
        unsigned=copy.deepcopy(rubric);supplied=unsigned.pop('contract_sha256')
        if supplied!=stable_hash(unsigned): return None
        original=copy.deepcopy(unsigned);original.pop('native_scoring')
        if stable_hash(original)!=binding['original_contract_sha256']: return None
        if _text(stem)!=_text(source['Learner_Question']) or _text(answer)!=_text(source['Model_Answer']): return None
        if _fraction(maximum)!=_fraction(source['Marks']) or _fraction(maximum)!=_fraction(rubric['maximum_marks']): return None
        expected=derive_operations(source) if binding['version']==VERSION else derive_controlled_operations(source)
        if not expected or binding['operations']!=expected: return None
        points=rubric['required_mark_points']
        if not _original_points_match(rubric,source,expected): return None
        return {'version':RUNTIME_VERSION,'maximum_marks':float(maximum),'required_mark_points':copy.deepcopy(points),
                'native_contract':copy.deepcopy(rubric),'question_text':stem,'model_answer':answer}
    except (KeyError,ValueError,TypeError,OverflowError): return None


def validate_native_rubric(rubric, maximum):
    try:
        compiled=compile_native_rubric(rubric['native_contract'],maximum,rubric['question_text'],rubric['model_answer'])
        valid = compiled is not None and all(rubric.get(k)==v for k,v in compiled.items())
        return {'valid':valid,'errors':[] if valid else ['NATIVE_SOURCE_BINDING_INVALID']}
    except (KeyError,ValueError,TypeError): return {'valid':False,'errors':['NATIVE_SOURCE_BINDING_INVALID']}


def native_observations(rubric, answer):
    """Return point evidence to the existing aggregation path; never award marks here."""
    binding=rubric['native_contract']['native_scoring']
    if binding['version']==EXTENDED_VERSION: return _controlled_observations(binding,answer)
    op=binding['operations'][0]
    pid=op['point_id'];awarded=set();denied=set();unknown=[]
    # Decimal-aware splitting; the canonical full quantity is tried atomically.
    chunks=[x.strip() for x in re.split(r';|\n|(?<!\d)\.(?=\s|$)|\.(?=\s+[A-Za-z])',answer) if x.strip()]
    if len(chunks)>50: return set(),set(),['RESPONSE_LIMIT']
    for text in chunks:
        try:
            if op['kind']=='RATIONAL_EQUATION':
                actual,_=_polynomial_equation(text,op['symbols'],op['allowed_denominators'])
                expected,_=_polynomial_equation(op['accepted_source_forms'][0],op['symbols'],op['allowed_denominators'])
                # A non-equivalent relation might be unrelated/valid working. Never
                # manufacture zero marks or select a correct equation from it.
                if actual==expected: awarded.add(pid)
                else: unknown.append(text)
            elif op['kind']=='QUANTITY':
                value,units,literal=_quantity(text,op['label'])
                if units!=op['units']: unknown.append(text)
                elif value==Fraction(op['value']): awarded.add(pid)
                else: denied.add(pid)
            elif op['kind']=='CONTROLLED_TERM':
                norm=_text(text).casefold()
                for prefix in ('the process is ','it is '):
                    if norm.startswith(prefix): norm=norm[len(prefix):];break
                if norm in (op['term'].casefold(),op['canonical'].casefold()): awarded.add(pid)
                elif norm in (op['excluded_term'].casefold(),op['excluded_canonical'].casefold(),'not '+op['term'].casefold()): denied.add(pid)
                else: unknown.append(text)
            else: unknown.append(text)
        except (ValueError,TypeError,SyntaxError,OverflowError,RecursionError): unknown.append(text)
    return awarded,denied,unknown


def _original_points_match(rubric,source,operations):
    """No new points, weights, criteria or cross-question authority."""
    try:
        points=rubric['required_mark_points'];values=source['Mark_Point_Values'].split(';')
        evidence=source['Canonical_Accepted_Evidence'].split(' | ')
        if not len(points)==len(values)==len(evidence)==len(operations)==int(source['Mark_Point_Count']): return False
        if sum(_fraction(v) for v in values)!=_fraction(source['Marks']):return False
        return all(p['id']==op['point_id']==f'p{i}' and _fraction(p['marks'])==_fraction(v)
                   and p['accepted_expressions']==[e] for i,(p,op,v,e) in enumerate(zip(points,operations,values,evidence),1))
    except (KeyError,ValueError,TypeError):return False


def derive_controlled_operations(source):
    """Project closed, explicitly authored evidence; retain original eligibility.

    This compiler recognises source evidence shapes, never IDs or keyword overlap.
    Narrative explanations, conditional methods and contextual term assignments
    are excluded. No source status or policy is rewritten.
    """
    try:
        if source['Required_Produced_Representation']!='NONE':return None
        if source['Numerical_Tolerance_Rule']!='NOT_APPLICABLE' or source['Significant_Figures_Rule']!='NOT_APPLICABLE':return None
        clauses=source['Canonical_Accepted_Evidence'].split(' | ')
        if len(clauses)!=int(source['Mark_Point_Count']):return None
        if len(clauses)==1:
            text=_text(clauses[0]);m=re.fullmatch(r'([A-Za-z])\s*=\s*(.+)',text)
            if not m or _text(source['Model_Answer'])!=text:return None
            label=m[1];forms=[text]
            alias=re.fullmatch(r'(.+?)\s+\(equivalently (.+)\)',text)
            if alias: forms=[alias[1],label+' = '+alias[2]]
            accepted=[]
            for form in forms:
                value,units,_=_quantity(form,label);accepted.append({'value':str(value),'units':units})
            return [{'point_id':'p1','kind':'SOURCE_QUANTITY','label':label,'canonical':text,'accepted':accepted}]
        if source['SAQ_Demand_Archetype']!='ARCH-NAME':return None
        if source['Partial_Credit_Rule']!='Award 1 mark for each independently satisfied mark point.':return None
        if any(_fraction(v)!=1 for v in source['Mark_Point_Values'].split(';')):return None
        if not source['Contradiction_Rule'].startswith('A direct contradiction of a credited proposition removes credit for that proposition;'):return None
        if source['Order_Sensitivity'] not in {
            'NO unless the response itself states a directional relationship; equivalent sentence order is accepted.',
            'YES only where a ranking/order is explicitly demanded; otherwise equivalent sentence order is accepted.'}:return None
        if re.search(r'\b(rank|order|sequence|ascending|descending)\b',source['Learner_Question'],re.I):return None
        operations=[];all_terms=set()
        for i,clause in enumerate(clauses,1):
            text=_text(clause)
            # Only unlabelled category names, not explanation or assignment prose.
            if not re.fullmatch(r'[A-Za-z -]+(?:\([A-Za-z -]+\))?(?: forces)?',text):return None
            if not text.lower().endswith(('forces','bonding')):return None
            if any(x in text.lower().split() for x in ['not','no','and','or','because','is','are']):return None
            forms=[text];parenthesis=re.fullmatch(r'(.+?) \((.+)\)(.*)',text)
            if parenthesis:forms.extend([parenthesis[1]+parenthesis[3],parenthesis[2]+parenthesis[3]])
            # An explicit 'Accept X for Y' declaration only changes this row's
            # authored term, preserving any authored suffix.
            for alternative in str(source['Acceptable_Alternatives']).strip('.').split(';'):
                am=re.fullmatch(r'\s*[Aa]ccept ([A-Za-z -]+) for ([A-Za-z -]+)\s*',alternative)
                if am:
                    for form in list(forms):
                        if form.casefold().startswith(am[2].casefold()):
                            forms.extend([am[1]+form[len(am[2]):],am[1],am[2]])
            terms=sorted({_text(s).casefold() for s in forms})
            if all_terms.intersection(terms):return None
            all_terms.update(terms)
            operations.append({'point_id':f'p{i}','kind':'SOURCE_TERM_SET','accepted':terms,'canonical':text})
        return operations
    except (KeyError,ValueError,TypeError,OverflowError):return None


def _controlled_observations(binding,answer):
    operations=binding['operations'];awarded=set();denied=set();unknown=[]
    if all(op['kind']=='SOURCE_TERM_SET' for op in operations):
        answer=re.sub(r',|\band\b',';',answer,flags=re.I)
    chunks=[s.strip() for s in re.split(r';|\n|(?<!\d)\.(?=\s|$)|\.(?=\s+[A-Za-z])',answer) if s.strip()]
    if len(chunks)>50:return set(),set(),['RESPONSE_LIMIT']
    for text in chunks:
        norm=_text(text);matched=False
        for op in operations:
            pid=op['point_id']
            if op['kind']=='SOURCE_QUANTITY':
                if norm==op['canonical']:awarded.add(pid);matched=True;continue
                try:value,units,_=_quantity(norm,op['label'])
                except ValueError:continue
                same_units=[x for x in op['accepted'] if x['units']==units]
                if same_units:
                    (awarded if any(value==Fraction(x['value']) for x in same_units) else denied).add(pid);matched=True
            elif op['kind']=='SOURCE_TERM_SET':
                if norm.casefold() in op['accepted']:awarded.add(pid);matched=True
                elif norm.casefold().startswith('not ') and norm[4:].casefold() in op['accepted']:denied.add(pid);matched=True
        if not matched:unknown.append(text)
    return awarded,denied,unknown
