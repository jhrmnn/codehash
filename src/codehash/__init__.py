# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at http://mozilla.org/MPL/2.0/.
from __future__ import annotations

import ast
import hashlib
import inspect
import os
import sys
from itertools import chain, dropwhile
from pathlib import Path
from textwrap import dedent
from types import CodeType, ModuleType
import typing
from typing import Any, Callable, Dict, NewType, Optional, Type, TypeVar, Union, cast

__version__ = '0.1.0'
__all__ = ['hash_function', 'CodehashError']

_T = TypeVar('_T')
Hash = NewType('Hash', str)
HashHook = Callable[[object], Optional[Hash]]

STDLIB_PATHS = [str(Path(m.__file__).parent) for m in [os, ast]]

_cache: Dict[Callable[..., Any], Hash] = {}


class CodehashError(Exception):
    pass


def hash_function(func: Callable[..., Any], hook: HashHook = None) -> Hash:
    try:
        return _cache[func]
    except KeyError:
        pass
    ast_code = ast_code_of(func)
    hashed_globals = hashed_globals_of(func, hook)
    spec = repr_hashable({'ast_code': ast_code, 'globals': hashed_globals})
    return _cache.setdefault(func, hash_text(spec))


def hash_text(text: str) -> Hash:
    return Hash(hashlib.sha1(text.encode()).hexdigest())


def ast_code_of(func: Callable[..., Any]) -> str:
    lines = dedent(inspect.getsource(func)).split('\n')
    lines = list(dropwhile(lambda l: l[0] == '@', lines))
    code = '\n'.join(lines)
    module: Any = ast.parse(code)
    assert len(module.body) == 1
    assert isinstance(module.body[0], (ast.AsyncFunctionDef, ast.FunctionDef))
    for node in ast.walk(module):
        remove_docstring(node)
    func_node = module.body[0]
    func_node.name = ''  # clear function's name
    return ast.dump(func_node, annotate_fields=False)


def remove_docstring(node: ast.AST) -> None:
    classes = ast.AsyncFunctionDef, ast.FunctionDef, ast.ClassDef, ast.Module
    if not isinstance(node, classes):
        return
    if not (node.body and isinstance(node.body[0], ast.Expr)):
        return
    docstr = node.body[0].value
    if isinstance(docstr, ast.Str):
        node.body.pop(0)


def hashed_globals_of(
    func: Callable[..., Any], hook: HashHook = None
) -> Dict[str, str]:
    closure_vars = getclosurevars(func)
    assert not closure_vars.unbound
    items = chain(closure_vars.nonlocals.items(), closure_vars.globals.items())
    hashed_globals: Dict[str, str] = {}
    for name, obj in items:
        try:
            if inspect.isclass(obj) or inspect.isfunction(obj) or inspect.ismodule(obj):
                if inspect.ismodule(obj):
                    mod = obj
                    fullname = obj.__name__
                else:
                    mod = sys.modules[obj.__module__]
                    fullname = fullname_of(obj)
                if is_stdlib(mod):
                    hashed_globals[name] = f'{fullname}(stdlib)'
                else:
                    version = version_of(mod)
                    if version:
                        hashed_globals[name] = f'{fullname}({version})'
                    elif inspect.isfunction(obj):
                        hashid = hash_function(obj) if obj is not func else 'self'
                        hashed_globals[name] = f'function:{hashid}'
                    else:
                        raise CodehashError()
            else:
                hashid = hash_text(repr_hashable(obj, hook))
                hashed_globals[name] = f'composite:{hashid}'
        except CodehashError:
            raise CodehashError(f'In {func} cannot hash global {name} = {obj!r}')
    return hashed_globals


def fullname_of(obj: Union[Callable[..., object], Type[object]]) -> str:
    return f'{obj.__module__}:{obj.__qualname__}'


def is_stdlib(mod: ModuleType) -> bool:
    return any(mod.__file__.startswith(p) for p in STDLIB_PATHS)


def version_of(mod: ModuleType) -> Optional[str]:
    parts = mod.__name__.split('.')
    for n in range(len(parts), 0, -1):
        mod = sys.modules['.'.join(parts[:n])]
        version = cast(Optional[str], getattr(mod, '__version__', None))
        if version:
            return version
    return None


def deep_transform(obj: object, transform: Callable[[object], object]) -> object:
    if obj is None or isinstance(obj, (str, bytes, int, float, bool)):
        return obj
    if isinstance(obj, list):
        return [deep_transform(x, transform) for x in obj]
    if isinstance(obj, tuple):
        return tuple(deep_transform(x, transform) for x in obj)
    if isinstance(obj, dict):
        return {k: deep_transform(obj[k], transform) for k in sorted(obj)}
    return transform(obj)


class Hashed:
    def __init__(self, hashid: Hash):
        self._hash = hashid

    def __repr__(self) -> str:
        return f'Hashed({self._hash!r})'


def repr_hashable(obj: object, hook: HashHook = None) -> str:
    if not hook:
        hook = lambda o: None

    def transform(o: object) -> Hashed:
        if hasattr(o, '__codehash__'):
            hashid: Optional[Hash] = cast(Hash, o.__codehash__())  # type: ignore
        else:
            hashid = hook(o)  # type: ignore
        if hashid is None:
            raise CodehashError(f'Unknown object: {o!r}')
        return Hashed(hashid)

    return repr(deep_transform(obj, transform))


# adapted function from stdlib which parses closures in code consts as well
# see https://bugs.python.org/issue34947
def getclosurevars(func: Callable[..., Any]) -> inspect.ClosureVars:
    code = func.__code__
    nonlocal_vars = {
        name: cell.cell_contents
        for name, cell in zip(code.co_freevars, func.__closure__ or ())  # type: ignore
    }
    global_ns = func.__globals__  # type: ignore
    builtin_ns = global_ns['__builtins__']
    if inspect.ismodule(builtin_ns):
        builtin_ns = builtin_ns.__dict__  # pragma: no cover
    global_vars = {}
    builtin_vars = {}
    unbound_names = set()
    codes = [code]
    while codes:
        code = codes.pop()
        for const in code.co_consts:
            if isinstance(const, CodeType):
                codes.append(const)
        for name in code.co_names:
            try:
                global_vars[name] = global_ns[name]
            except KeyError:
                try:
                    builtin_vars[name] = builtin_ns[name]
                except KeyError:
                    unbound_names.add(name)
    return inspect.ClosureVars(nonlocal_vars, global_vars, builtin_vars, unbound_names)
