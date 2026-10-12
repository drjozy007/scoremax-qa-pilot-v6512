"""Restricted, local mathematical equivalence for ScoreMax constructed work.

No eval/sympify/parse_expr, network, model or learner answer execution. This
checks mathematical statements; it does not infer a proof or a rubric award.
"""
from __future__ import annotations

import ast
import re

import sympy as sp

VERSION='SM-LOCAL-MATH-EQUIVALENCE-1'
_NAMES={name:sp.Symbol(name,real=name in {'a','b','c','d','x','y','u','v','p','q','k'})
        for name in ('a','b','c','d','x','y','u','v','p','q','k','z','w')}
_NAMES.update(i=sp.I,I=sp.I,pi=sp.pi,omega=(-1+sp.I*sp.sqrt(3))/2)
_SUP=str.maketrans('⁰¹²³⁴⁵⁶⁷⁸⁹','0123456789')
_ALLOWED=re.compile(r'[A-Za-z0-9_+*/().,\s-]+\Z')


def _normalise(value):
    if not isinstance(value,str) or len(value)>240:
        raise ValueError('EXPRESSION_LIMIT')
    text=value.strip().replace('−','-').replace('–','-').replace('×','*').replace('÷','/')
    text=text.replace('i√','i*√').replace('ω√','ω*√')
    text=text.replace('π','pi').replace('ω','omega').replace('√','sqrt')
    text=re.sub(r'([⁰¹²³⁴⁵⁶⁷⁸⁹]+)',lambda m:'**'+m.group(1).translate(_SUP),text)
    text=text.replace('^','**')
    text=re.sub(r'(?<![A-Za-z_])sqrt\s*(\d+(?:\.\d+)?)',r'sqrt(\1)',text)
    text=re.sub(r'(?<=\))\s+(?=[A-Za-z0-9(])','*',text)
    text=re.sub(r'(?<=\d)(?=(?:[A-Za-z]|\())|(?<=\))(?=(?:[A-Za-z]|\d|\())', '*',text)
    # 2sqrt(3) and 3i are multiplication; no function call other than sqrt.
    if not text or not _ALLOWED.fullmatch(text):
        raise ValueError('EXPRESSION_GRAMMAR')
    return text


def parse_expression(value):
    tree=ast.parse(_normalise(value),mode='eval')
    nodes=0
    def visit(node,depth=0):
        nonlocal nodes
        nodes+=1
        if nodes>60 or depth>15:raise ValueError('EXPRESSION_COMPLEXITY')
        if isinstance(node,ast.Constant) and type(node.value) in (int,float):
            if abs(node.value)>10**7:raise ValueError('NUMBER_LIMIT')
            return sp.Rational(str(node.value))
        if isinstance(node,ast.Name) and node.id in _NAMES:
            return _NAMES[node.id]
        if isinstance(node,ast.UnaryOp) and type(node.op) in (ast.UAdd,ast.USub):
            item=visit(node.operand,depth+1)
            return item if isinstance(node.op,ast.UAdd) else -item
        if isinstance(node,ast.BinOp):
            a=visit(node.left,depth+1)
            if isinstance(node.op,ast.Pow):
                if not isinstance(node.right,ast.Constant) or type(node.right.value) is not int or not -8<=node.right.value<=8:
                    raise ValueError('POWER_LIMIT')
                return a**node.right.value
            b=visit(node.right,depth+1)
            if isinstance(node.op,ast.Add):return a+b
            if isinstance(node.op,ast.Sub):return a-b
            if isinstance(node.op,ast.Mult):return a*b
            if isinstance(node.op,ast.Div):return a/b
        if isinstance(node,ast.Call) and isinstance(node.func,ast.Name) and node.func.id=='sqrt' and len(node.args)==1 and not node.keywords:
            arg=visit(node.args[0],depth+1)
            if arg.is_number is not True or arg.is_nonnegative is not True:
                raise ValueError('RADICAL_DOMAIN')
            return sp.sqrt(arg)
        raise ValueError('EXPRESSION_GRAMMAR')
    result=visit(tree.body)
    if result.has(sp.zoo,sp.nan,sp.oo,-sp.oo):raise ValueError('UNDEFINED_EXPRESSION')
    return result


def equivalent(left,right):
    """Return True, False or None (unsupported/undecidable); never guess."""
    try:
        a=parse_expression(left);b=parse_expression(right)
        delta=sp.cancel(sp.expand(a-b))
        if delta==0:return True
        if delta.is_number and delta.equals(0) is False:return False
        return None
    except (ValueError,SyntaxError,TypeError,OverflowError,RecursionError,ZeroDivisionError):
        return None


def statement_equivalent(source,learner):
    """Compare both sides of explicit equations with the same named left side."""
    try:
        sl,sr=[x.strip() for x in source.split('=')]
        ll,lr=[x.strip() for x in learner.split('=')]
        if sl!=ll or not sl or not sr or not lr:return None
        if parse_expression(sr).free_symbols or parse_expression(lr).free_symbols:
            return None
        return equivalent(sr,lr)
    except ValueError:
        return None
