"""Built-in functions for the Pebble language.

Provide a registry of built-in functions that the VM dispatches to at
runtime.  Each builtin takes a list of :data:`Value` arguments and returns
a single :data:`Value`.

The :data:`BUILTINS` dict maps function names to ``(arity, handler)`` pairs.
:data:`BUILTIN_ARITIES` includes *all* builtins (runtime **and** compile-time
like ``print`` and ``range``) so the analyzer can validate calls from a
single source of truth.
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from typing import TYPE_CHECKING

from pebble.errors import PebbleRuntimeError

if TYPE_CHECKING:
    from pebble.bytecode import CodeObject

type Value = int | str | bool | list[Value] | Closure


# -- Closure types ------------------------------------------------------------


@dataclass
class Cell:
    """Mutable container for a captured variable.

    Enclosing and inner functions share the same ``Cell`` object so that
    mutations in either scope are visible to both.
    """

    value: Value


@dataclass(frozen=True)
class Closure:
    """A function bundled with its captured variable cells.

    Attributes:
        code: The compiled :class:`CodeObject` for the function body.
        cells: Captured :class:`Cell` references, one per free variable.

    """

    code: CodeObject
    cells: list[Cell]


# -- Value formatting ----------------------------------------------------------


def format_value(value: Value) -> str:
    """Format *value* for Pebble-native output."""
    match value:
        case bool():
            return "true" if value else "false"
        case int():
            return str(value)
        case str():
            return value
        case list():
            items = ", ".join(format_value(v) for v in value)
            return f"[{items}]"
        case Closure():
            return f"<fn {value.code.name}>"


# -- Builtin handlers ---------------------------------------------------------


def _builtin_str(args: list[Value]) -> Value:
    """Convert any value to its string representation."""
    return format_value(args[0])


def _builtin_int(args: list[Value]) -> Value:
    """Convert a string or integer to an integer."""
    arg = args[0]
    if isinstance(arg, int) and not isinstance(arg, bool):
        return arg
    if isinstance(arg, str):
        try:
            return int(arg)
        except ValueError:
            msg = f"Cannot convert '{arg}' to int"
            raise PebbleRuntimeError(msg, line=0, column=0) from None
    type_name = type(arg).__name__
    msg = f"Cannot convert {type_name} to int"
    raise PebbleRuntimeError(msg, line=0, column=0)


def _builtin_type(args: list[Value]) -> Value:
    """Return the type name of a value as a string."""
    arg = args[0]
    match arg:
        case bool():
            return "bool"
        case int():
            return "int"
        case str():
            return "str"
        case list():
            return "list"
        case Closure():
            return "fn"


def _builtin_len(args: list[Value]) -> Value:
    """Return the length of a list or string."""
    arg = args[0]
    if isinstance(arg, list | str):
        return len(arg)
    type_name = type(arg).__name__
    msg = f"len() not supported for {type_name}"
    raise PebbleRuntimeError(msg, line=0, column=0)


def _builtin_push(args: list[Value]) -> Value:
    """Append a value to a list, mutating it. Return the list."""
    target = args[0]
    if not isinstance(target, list):
        type_name = type(target).__name__
        msg = f"push() requires a list, got {type_name}"
        raise PebbleRuntimeError(msg, line=0, column=0)
    target.append(args[1])
    return target


def _builtin_pop(args: list[Value]) -> Value:
    """Remove and return the last element of a list."""
    target = args[0]
    if not isinstance(target, list):
        type_name = type(target).__name__
        msg = f"pop() requires a list, got {type_name}"
        raise PebbleRuntimeError(msg, line=0, column=0)
    if not target:
        msg = "Cannot pop from an empty list"
        raise PebbleRuntimeError(msg, line=0, column=0)
    return target.pop()


# -- Registry ------------------------------------------------------------------

type BuiltinHandler = Callable[[list[Value]], Value]

BUILTINS: dict[str, tuple[int, BuiltinHandler]] = {
    "str": (1, _builtin_str),
    "int": (1, _builtin_int),
    "type": (1, _builtin_type),
    "len": (1, _builtin_len),
    "push": (2, _builtin_push),
    "pop": (1, _builtin_pop),
}
"""Map of runtime builtin names to ``(arity, handler)`` pairs."""

# Compile-time builtins have no runtime handler — the compiler handles them.
_PRINT_ARITY = 1
_RANGE_ARITY = 1

BUILTIN_ARITIES: dict[str, int] = {name: arity for name, (arity, _) in BUILTINS.items()} | {
    "print": _PRINT_ARITY,
    "range": _RANGE_ARITY,
}
"""Map of ALL builtin names (runtime + compile-time) to arity."""
