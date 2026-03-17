"""Importable standard library modules for Pebble.

Provide ``import "math"`` and ``import "io"`` as built-in modules whose
functions are implemented in the host language (Python) rather than in
``.pbl`` files.  The resolver detects stdlib names before looking for
files on disk.
"""

import math
from collections.abc import Callable
from dataclasses import dataclass

from pebble.builtins import Value
from pebble.errors import PebbleRuntimeError

type StdlibHandler = Callable[[list[Value]], Value] | None
"""Handler for a stdlib function.

``None`` means the function needs VM access (e.g. ``input()``) and is
dispatched by the VM itself.
"""


@dataclass(frozen=True)
class StdlibModule:
    """A built-in standard library module.

    Attributes:
        functions: Map of function name to ``(arity, handler)`` pairs.
        constants: Map of constant name to its value.

    """

    functions: dict[str, tuple[int | tuple[int, ...], StdlibHandler]]
    constants: dict[str, Value]


# -- Numeric helpers ----------------------------------------------------------


def _require_numeric(value: Value, fn_name: str) -> int | float:
    """Validate that *value* is a plain int or float, raising on bad types."""
    if isinstance(value, bool):
        msg = f"{fn_name}() requires a number, got bool"
        raise PebbleRuntimeError(msg, line=0, column=0)
    if isinstance(value, int | float):
        return value
    type_name = type(value).__name__
    msg = f"{fn_name}() requires a number, got {type_name}"
    raise PebbleRuntimeError(msg, line=0, column=0)


def _require_two_numeric(a: Value, b: Value, fn_name: str) -> tuple[int | float, int | float]:
    """Validate that both *a* and *b* are plain int or float."""
    if isinstance(a, bool) or isinstance(b, bool):
        msg = f"{fn_name}() requires numbers, got bool"
        raise PebbleRuntimeError(msg, line=0, column=0)
    if isinstance(a, int | float) and isinstance(b, int | float):
        return a, b
    msg = f"{fn_name}() requires numbers"
    raise PebbleRuntimeError(msg, line=0, column=0)


# -- Math handlers ------------------------------------------------------------


def _math_abs(args: list[Value]) -> Value:
    """Return the absolute value of a number."""
    x = _require_numeric(args[0], "abs")
    return abs(x)


def _math_min(args: list[Value]) -> Value:
    """Return the minimum of two numbers."""
    a, b = _require_two_numeric(args[0], args[1], "min")
    return min(a, b)


def _math_max(args: list[Value]) -> Value:
    """Return the maximum of two numbers."""
    a, b = _require_two_numeric(args[0], args[1], "max")
    return max(a, b)


def _math_floor(args: list[Value]) -> Value:
    """Round down to the nearest integer."""
    x = _require_numeric(args[0], "floor")
    return math.floor(x)


def _math_ceil(args: list[Value]) -> Value:
    """Round up to the nearest integer."""
    x = _require_numeric(args[0], "ceil")
    return math.ceil(x)


def _math_round(args: list[Value]) -> Value:
    """Round to the nearest integer."""
    x = _require_numeric(args[0], "round")
    return round(x)


def _math_sqrt(args: list[Value]) -> Value:
    """Return the square root of a number."""
    x = _require_numeric(args[0], "sqrt")
    if x < 0:
        msg = "sqrt() argument must not be negative"
        raise PebbleRuntimeError(msg, line=0, column=0)
    return math.sqrt(x)


def _math_pow(args: list[Value]) -> Value:
    """Return x raised to the power y."""
    x, y = _require_two_numeric(args[0], args[1], "pow")
    result = x**y
    if isinstance(result, complex):
        msg = "pow() produced a complex result (negative base with fractional exponent)"
        raise PebbleRuntimeError(msg, line=0, column=0)
    return result


def _math_sin(args: list[Value]) -> Value:
    """Return the sine of x (radians)."""
    x = _require_numeric(args[0], "sin")
    return math.sin(x)


def _math_cos(args: list[Value]) -> Value:
    """Return the cosine of x (radians)."""
    x = _require_numeric(args[0], "cos")
    return math.cos(x)


def _math_log(args: list[Value]) -> Value:
    """Return the natural logarithm of x."""
    x = _require_numeric(args[0], "log")
    if x <= 0:
        msg = "log() argument must be positive"
        raise PebbleRuntimeError(msg, line=0, column=0)
    return math.log(x)


# -- Module definitions -------------------------------------------------------


MATH_MODULE = StdlibModule(
    functions={
        "abs": (1, _math_abs),
        "min": (2, _math_min),
        "max": (2, _math_max),
        "floor": (1, _math_floor),
        "ceil": (1, _math_ceil),
        "round": (1, _math_round),
        "sqrt": (1, _math_sqrt),
        "pow": (2, _math_pow),
        "sin": (1, _math_sin),
        "cos": (1, _math_cos),
        "log": (1, _math_log),
    },
    constants={
        "pi": math.pi,
        "e": math.e,
    },
)
"""The ``math`` standard library module."""

IO_MODULE = StdlibModule(
    functions={
        "input": ((0, 1), None),
    },
    constants={},
)
"""The ``io`` standard library module."""

STDLIB_MODULES: dict[str, StdlibModule] = {
    "math": MATH_MODULE,
    "io": IO_MODULE,
}
"""Registry of all importable standard library modules."""
