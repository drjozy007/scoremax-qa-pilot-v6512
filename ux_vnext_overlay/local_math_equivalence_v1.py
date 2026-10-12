"""Bounded local algebra for ScoreMax's source-backed evidence marker.

The whole expression is parsed; learner text is never executed. Structural
evidence follows the existing ScoreMax evidence engine's commutative shape
semantics, so equal final values do not by themselves prove a required method.
"""
from __future__ import annotations

import ast
from dataclasses import dataclass
import re

import sympy as sp

VERSION = 'SM-LOCAL-MATH-EQUIVALENCE-2'
_REAL = set('abcdxyuvpqkrtmn')
_NAMES = {s: sp.Symbol(s, real=True) if s in _REAL else sp.Symbol(s)
          for s in 'abcdxyuvpqkrtmnzw'}
_NAMES.update({s + str(n): sp.Symbol(s + str(n)) for s in 'zw' for n in (1, 2, 3)})
_NAMES.update(i=sp.I, I=sp.I, pi=sp.pi, omega=(-1 + sp.I*sp.sqrt(3))/2)
_FUNCTIONS = {'sqrt', 'bar', 'conj', 'Re', 'Im', 'abs', 'sin', 'cos', 'cis'}
_WORDS = sorted(set(_NAMES) | _FUNCTIONS, key=len, reverse=True)
_TOKEN = re.compile(r'(?:\d+(?:\.\d*)?|\.\d+)|[A-Za-z][A-Za-z0-9_]*|\*\*|[+*/%(),-]')
_SUP = str.maketrans('⁰¹²³⁴⁵⁶⁷⁸⁹', '0123456789')
_SUB = str.maketrans('₀₁₂₃₄₅₆₇₈₉', '0123456789')
_FRACTIONS = {'½':'(1/2)', '⅓':'(1/3)', '⅔':'(2/3)', '¼':'(1/4)',
              '¾':'(3/4)', '⅛':'(1/8)', '⅜':'(3/8)', '⅝':'(5/8)', '⅞':'(7/8)'}


def _normalise(value):
    if not isinstance(value, str) or not 0 < len(value) <= 500:
        raise ValueError('EXPRESSION_LIMIT')
    text = value.strip().replace('−','-').replace('–','-').replace('×','*').replace('·','*').replace('÷','/')
    for char, fraction in _FRACTIONS.items():
        text = re.sub(r'(\d+)\s*'+re.escape(char),lambda m:'('+m[1]+'+'+fraction+')',text)
        text = text.replace(char, fraction)
    text = text.translate(_SUB)
    text = re.sub(r'([a-z](?:[123])?)\u0304', r'bar(\1)', text)
    text = re.sub(r'\b([zw])_([123])\b', r'\1\2', text)
    text = text.replace('π','pi').replace('ω','omega').replace('√','sqrt')
    text = re.sub(r'([⁰¹²³⁴⁵⁶⁷⁸⁹]+)', lambda m: '**' + m[1].translate(_SUP), text).replace('^','**')
    text = re.sub(r'sqrt\s*(\d+(?:\.\d+)?)', r'sqrt(\1)', text)
    # Paired modulus bars have mathematical meaning; unmatched bars are invalid.
    while '|' in text:
        match = re.search(r'\|([^|]+)\|', text)
        if not match:
            raise ValueError('UNPAIRED_MODULUS')
        text = text[:match.start()] + 'abs(' + match[1] + ')' + text[match.end():]
    tokens = []; pos = 0
    for match in _TOKEN.finditer(text):
        if text[pos:match.start()].strip():
            raise ValueError('EXPRESSION_GRAMMAR')
        token = match[0]; pos = match.end()
        if token[0].isalpha() and token not in _NAMES and token not in _FUNCTIONS:
            # Conventional adjacent one-letter symbols (ab, ib, zi) only.
            if len(token) <= 8 and all(ch in _NAMES and len(ch) == 1 for ch in token):
                tokens.extend(list(token)); continue
            # A named constant/function after a one-letter symbol: ipi, isqrt.
            split = next(((token[:len(token)-len(w)],w) for w in _WORDS
                          if token.endswith(w) and token != w and
                          token[:len(token)-len(w)] in _NAMES), None)
            if split:
                tokens.extend(split); continue
            raise ValueError('UNKNOWN_MATHEMATICAL_NAME')
        tokens.append(token)
    if text[pos:].strip() or not tokens or len(tokens) > 150:
        raise ValueError('EXPRESSION_GRAMMAR')
    out = []
    for token in tokens:
        if out:
            prev = out[-1]
            if (prev[0].isdigit() or prev.startswith('.')) and (token[0].isdigit() or token.startswith('.')):
                raise ValueError('ADJACENT_NUMBERS_AMBIGUOUS')
            end = prev == ')' or prev in _NAMES or prev[0].isdigit() or prev.startswith('.')
            start = token == '(' or token in _NAMES or token in _FUNCTIONS or token[0].isdigit() or token.startswith('.')
            if end and start:
                out.append('*')
        out.append(token)
    return ''.join(out)


def _shape(op, *args):
    # Reused semantics of ScoreMax's existing structural evidence engine.
    if op in {'+', '*'}:
        flat = []
        for item in args:
            flat.extend(item[1:] if item[0] == op else [item])
        return (op, *sorted(flat, key=repr))
    return (op, *args)


@dataclass(frozen=True)
class ParsedExpression:
    value: object
    shape: tuple
    denominators: tuple


def parsed_expression(value):
    normal = _normalise(value)
    tree = ast.parse(normal, mode='eval')
    if sum(1 for _ in ast.walk(tree)) > 180:
        raise ValueError('EXPRESSION_NODE_LIMIT')
    denominators = []; operations = [0]

    def visit(node, depth=0):
        operations[0] += 1
        if operations[0] > 100 or depth > 18:
            raise ValueError('EXPRESSION_COMPLEXITY')
        if isinstance(node, ast.Constant) and type(node.value) in (int, float):
            literal = ast.get_source_segment(normal, node)
            if len(literal) > 32:
                raise ValueError('NUMBER_LIMIT')
            val = sp.Rational(literal)
            if abs(val) > 10**9:
                raise ValueError('NUMBER_LIMIT')
            return val, ('number', str(val)), 1, 0
        if isinstance(node, ast.Name) and node.id in _NAMES:
            return _NAMES[node.id], ('name', node.id), 1, int(bool(_NAMES[node.id].free_symbols))
        if isinstance(node, ast.UnaryOp) and isinstance(node.op, (ast.UAdd, ast.USub)):
            val, shape, terms, degree = visit(node.operand, depth+1)
            return (val, shape, terms, degree) if isinstance(node.op, ast.UAdd) else (-val, _shape('negate',shape),terms,degree)
        if isinstance(node, ast.BinOp):
            a, sa, ta, da = visit(node.left, depth+1)
            b, sb, tb, db = visit(node.right, depth+1)
            if isinstance(node.op, (ast.Add, ast.Sub)):
                terms, degree = ta+tb, max(da,db)
                val = a+b if isinstance(node.op,ast.Add) else a-b
                shape = _shape('+' if isinstance(node.op,ast.Add) else '-',sa,sb)
            elif isinstance(node.op, ast.Mult):
                terms, degree = ta*tb, da+db
                if terms > 256 or degree > 12:
                    raise ValueError('EXPRESSION_EXPANSION_LIMIT')
                val, shape = a*b, _shape('*',sa,sb)
            elif isinstance(node.op, ast.Div):
                if b == 0:
                    raise ValueError('ZERO_DENOMINATOR')
                terms, degree = ta*tb, max(da,db)
                denominators.append(b)
                val, shape = a/b, _shape('/',sa,sb)
            elif isinstance(node.op, ast.Mod):
                if a.is_Integer is not True or b.is_Integer is not True or b<=0:
                    raise ValueError('INTEGER_MODULUS_REQUIRED')
                val,shape,terms,degree=a%b,_shape('mod',sa,sb),1,0
            elif isinstance(node.op, ast.Pow):
                if b.is_Integer is not True or b.free_symbols or abs(b) > 10**9:
                    raise ValueError('POWER_LIMIT')
                exponent = int(b)
                if abs(exponent) > 8 and a not in (sp.I, -sp.I, sp.Integer(1), sp.Integer(-1), _NAMES['omega']):
                    raise ValueError('POWER_LIMIT')
                if a == 0 and exponent <= 0:
                    raise ValueError('UNDEFINED_POWER')
                root_of_unity = a in (sp.I,-sp.I,sp.Integer(1),sp.Integer(-1),_NAMES['omega'])
                terms, degree = (1,0) if root_of_unity else (ta**abs(exponent),da*abs(exponent))
                if terms > 256 or degree > 12:
                    raise ValueError('EXPRESSION_EXPANSION_LIMIT')
                if exponent < 0:
                    denominators.append(a)
                val = a**(exponent%3) if a==_NAMES['omega'] else a**exponent
                shape = _shape('power',sa,sb)
            else:
                raise ValueError('EXPRESSION_OPERATOR')
            if terms > 256 or degree > 12:
                raise ValueError('EXPRESSION_EXPANSION_LIMIT')
            if val.is_Rational and (int(val.p).bit_length() > 1024 or int(val.q).bit_length() > 1024):
                raise ValueError('NUMBER_COMPLEXITY')
            return val, shape, terms, degree
        if isinstance(node, ast.Call) and isinstance(node.func, ast.Name) and node.func.id in _FUNCTIONS and len(node.args)==1 and not node.keywords:
            arg, shape, terms, degree = visit(node.args[0], depth+1)
            fn = node.func.id
            if fn in {'sqrt','sin','cos','cis'} and arg.free_symbols:
                raise ValueError('FUNCTION_DOMAIN_UNSUPPORTED')
            if fn in {'sin','cos','cis'} and not (arg/sp.pi).is_Rational:
                raise ValueError('EXACT_ANGLE_REQUIRED')
            if fn in {'sin','cos','cis'} and (abs(arg/sp.pi)>4096 or (arg/sp.pi).q>24):
                raise ValueError('ANGLE_COMPLEXITY')
            if fn=='sqrt' and sum(isinstance(n,ast.Call) and isinstance(n.func,ast.Name) and n.func.id=='sqrt' for n in ast.walk(node))>3:
                raise ValueError('RADICAL_COMPLEXITY')
            funcs = {'sqrt':sp.sqrt,'bar':sp.conjugate,'conj':sp.conjugate,
                     'Re':sp.re,'Im':sp.im,'abs':sp.Abs,'sin':sp.sin,'cos':sp.cos,
                     'cis':lambda x:sp.cos(x)+sp.I*sp.sin(x)}
            return funcs[fn](arg), (fn,shape), terms, degree
        raise ValueError('EXPRESSION_GRAMMAR')

    result, shape, _, _ = visit(tree.body)
    if result.has(sp.zoo,sp.nan,sp.oo,-sp.oo):
        raise ValueError('UNDEFINED_EXPRESSION')
    return ParsedExpression(result,shape,tuple(denominators))


def parse_expression(value):
    return parsed_expression(value).value


def equivalent(left,right):
    """Exact equality, proven inequality of constants, or unsupported (None)."""
    try:
        a=parsed_expression(left); b=parsed_expression(right)
        # Do not cancel away a learner's undeclared singularity.
        ad={sp.srepr(x) for x in a.denominators if x.free_symbols}
        bd={sp.srepr(x) for x in b.denominators if x.free_symbols}
        if ad != bd:
            return None
        delta=sp.cancel(sp.expand(a.value-b.value))
        if delta == 0:
            return True
        if delta.is_number and delta.equals(0) is False:
            return False
        return None
    except (ValueError,SyntaxError,TypeError,OverflowError,RecursionError,ZeroDivisionError):
        return None


def same_displayed_form(left,right):
    try:
        return parsed_expression(left).shape == parsed_expression(right).shape
    except (ValueError,SyntaxError,TypeError,OverflowError,RecursionError):
        return None


def statement_equivalent(source,learner):
    try:
        sl,sr=[x.strip() for x in source.split('=')]
        ll,lr=[x.strip() for x in learner.split('=')]
        if _normalise(sl) != _normalise(ll):
            return None
        source_rhs, learner_rhs = parse_expression(sr), parse_expression(lr)
        if source_rhs.free_symbols or learner_rhs.free_symbols:
            return None
        if sl.startswith(('Re(', 'Im(')) and learner_rhs.is_real is not True:
            return None
        return equivalent(sr,lr)
    except (ValueError,SyntaxError,TypeError,OverflowError,RecursionError):
        return None


def distributed_terms(value, *, require_expanded=False):
    """Retain the individual terms of a distributive expansion before collecting.

    This is structural method evidence, not equivalence of final answers.
    Numerical arithmetic within an individual term may be simplified.
    """
    normal=_normalise(value)
    parsed_expression(value)  # Shared bounds and grammar, before expansion.
    tree=ast.parse(normal,mode='eval')
    def walk(node):
        if isinstance(node,ast.BinOp) and isinstance(node.op,(ast.Add,ast.Sub)):
            left=walk(node.left);right=walk(node.right)
            return left + ([f'-({x})' for x in right] if isinstance(node.op,ast.Sub) else right)
        if isinstance(node,ast.UnaryOp) and isinstance(node.op,ast.USub):
            return [f'-({x})' for x in walk(node.operand)]
        if isinstance(node,ast.BinOp) and isinstance(node.op,ast.Mult):
            a=walk(node.left);b=walk(node.right)
            if require_expanded and (len(a)>1 or len(b)>1):
                raise ValueError('UNDISTRIBUTED_PRODUCT')
            if len(a)*len(b)>16:
                raise ValueError('DISTRIBUTION_LIMIT')
            return [f'({x})*({y})' for x in a for y in b]
        return [ast.get_source_segment(normal,node)]
    terms=walk(tree.body)
    if len(terms)>16:
        raise ValueError('DISTRIBUTION_LIMIT')
    return tuple(sorted(sp.srepr(parse_expression(t).expand()) for t in terms))


def demonstrates_expansion(source,learner):
    try:
        target=distributed_terms(source)
        observed=distributed_terms(learner,require_expanded=True)
        return len(target)>1 and target==observed
    except (ValueError,SyntaxError,TypeError,OverflowError,RecursionError):
        return None


def rectangular_form(value):
    """A displayed sum of real terms and real multiples of a single i."""
    try:
        normal=_normalise(value);parsed_expression(value)
        tree=ast.parse(normal,mode='eval')
        def real(node):
            return parse_expression(ast.get_source_segment(normal,node)).is_real is True
        def imaginary_term(node):
            if isinstance(node,ast.Name):return node.id in {'i','I'}
            if isinstance(node,ast.UnaryOp) and isinstance(node.op,(ast.UAdd,ast.USub)):
                return imaginary_term(node.operand)
            if isinstance(node,ast.BinOp) and isinstance(node.op,ast.Mult):
                return (real(node.left) and imaginary_term(node.right)) or (real(node.right) and imaginary_term(node.left))
            if isinstance(node,ast.BinOp) and isinstance(node.op,ast.Div):
                return imaginary_term(node.left) and real(node.right)
            return False
        def rectangular(node):
            if isinstance(node,ast.BinOp) and isinstance(node.op,(ast.Add,ast.Sub)):
                return rectangular(node.left) and rectangular(node.right)
            return real(node) or imaginary_term(node)
        return rectangular(tree.body)
    except (ValueError,SyntaxError,TypeError,OverflowError,RecursionError):
        return None
