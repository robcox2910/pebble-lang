"""Built-in functions for the Pebble language.

Provide a registry of built-in functions that the VM dispatches to at
runtime.  Each builtin takes a list of :data:`Value` arguments and returns
a single :data:`Value`.

The :data:`BUILTINS` dict maps function names to ``(arity, handler)`` pairs.
:data:`BUILTIN_ARITIES` includes *all* builtins (runtime **and** compile-time
like ``print`` and ``range``) so the analyzer can validate calls from a
single source of truth.
"""

from collections.abc import Callable
from dataclasses import dataclass

from pebble.bytecode import CodeObject
from pebble.errors import PebbleRuntimeError


@dataclass(frozen=True)
class EnumVariant:
    """Runtime representation of an enum variant like ``Color.Red``.

    Attributes:
        enum_name: The name of the enum (e.g. ``"Color"``).
        variant_name: The name of the variant (e.g. ``"Red"``).

    """

    enum_name: str
    variant_name: str


type Value = (
    int
    | float
    | str
    | bool
    | None
    | list[Value]
    | dict[str, Value]
    | Closure
    | StructInstance
    | EnumVariant
    | SequenceIterator
    | GeneratorObject
)


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


# -- Struct instances ----------------------------------------------------------


@dataclass
class StructInstance:
    """Runtime representation of a struct value.

    Attributes:
        type_name: The name of the struct type (e.g. ``"Point"``).
        fields: Ordered mapping from field name to current value.

    """

    type_name: str
    fields: dict[str, Value]


@dataclass
class SequenceIterator:
    """Iterator over a list or string, advancing one element at a time.

    Attributes:
        items: The list or string being iterated.
        index: Current position in the sequence.

    """

    items: list[Value] | str
    index: int = 0


@dataclass
class GeneratorObject:
    """Suspended generator coroutine created from a function containing ``yield``.

    Attributes:
        code: The compiled function body.
        ip: Instruction pointer for resumption.
        variables: Snapshot of local variables at the yield point.
        cells: Snapshot of closure cells at the yield point.
        exhausted: Whether the generator has returned.

    """

    code: CodeObject
    ip: int
    variables: dict[str, Value]
    cells: dict[str, Cell]
    exhausted: bool = False


# -- Value formatting ----------------------------------------------------------


def _format_scalar(value: Value) -> str | None:
    """Format scalar types (null, bool, numbers, strings).

    Return ``None`` if *value* is not a scalar.
    """
    if value is None:
        return "null"
    if isinstance(value, bool):
        return "true" if value else "false"
    if isinstance(value, int | float):
        return str(value)
    if isinstance(value, str):
        return value
    return None


def _format_collection(value: Value) -> str | None:
    """Format compound types (dict, list, enum, struct).

    Return ``None`` if *value* is not a compound type.
    """
    if isinstance(value, dict):
        pairs = ", ".join(f"{k}: {format_value(v)}" for k, v in value.items())
        return f"{{{pairs}}}"
    if isinstance(value, list):
        items = ", ".join(format_value(v) for v in value)
        return f"[{items}]"
    if isinstance(value, EnumVariant):
        return f"{value.enum_name}.{value.variant_name}"
    if isinstance(value, StructInstance):
        fields = ", ".join(f"{k}={format_value(v)}" for k, v in value.fields.items())
        return f"{value.type_name}({fields})"
    return None


def _format_internal(value: Value) -> str:
    """Format internal VM types (closures, generators, iterators)."""
    if isinstance(value, Closure):
        return f"<fn {value.code.name}>"
    if isinstance(value, GeneratorObject):
        return f"<generator {value.code.name}>"
    if isinstance(value, SequenceIterator):
        return "<iterator>"
    return str(value)  # pragma: no cover


def format_value(value: Value) -> str:
    """Format *value* for Pebble-native output."""
    scalar = _format_scalar(value)
    if scalar is not None:
        return scalar
    collection = _format_collection(value)
    if collection is not None:
        return collection
    return _format_internal(value)


# -- Builtin handlers ---------------------------------------------------------


def _builtin_int(args: list[Value]) -> Value:
    """Convert a string, float, or integer to an integer."""
    arg = args[0]
    if isinstance(arg, int) and not isinstance(arg, bool):
        return arg
    if isinstance(arg, float):
        return int(arg)
    if isinstance(arg, str):
        try:
            return int(arg)
        except ValueError:
            msg = f"Cannot convert '{arg}' to int"
            raise PebbleRuntimeError(msg, line=0, column=0) from None
    type_name = type(arg).__name__
    msg = f"Cannot convert {type_name} to int"
    raise PebbleRuntimeError(msg, line=0, column=0)


def _builtin_float(args: list[Value]) -> Value:
    """Convert a string, integer, or float to a float."""
    arg = args[0]
    if isinstance(arg, float):
        return arg
    if isinstance(arg, int) and not isinstance(arg, bool):
        return float(arg)
    if isinstance(arg, str):
        try:
            return float(arg)
        except ValueError:
            msg = f"Cannot convert '{arg}' to float"
            raise PebbleRuntimeError(msg, line=0, column=0) from None
    type_name = type(arg).__name__
    msg = f"Cannot convert {type_name} to float"
    raise PebbleRuntimeError(msg, line=0, column=0)


_TYPE_NAMES: dict[type, str] = {
    type(None): "null",
    bool: "bool",
    float: "float",
    int: "int",
    str: "str",
    dict: "dict",
    list: "list",
    Closure: "fn",
    GeneratorObject: "generator",
    SequenceIterator: "iterator",
}


def _builtin_type(args: list[Value]) -> Value:
    """Return the type name of a value as a string."""
    arg = args[0]
    type_name = _TYPE_NAMES.get(type(arg))
    if type_name is not None:
        return type_name
    if isinstance(arg, EnumVariant):
        return arg.enum_name
    if isinstance(arg, StructInstance):
        return arg.type_name
    return "unknown"  # pragma: no cover


def _builtin_len(args: list[Value]) -> Value:
    """Return the length of a list or string."""
    arg = args[0]
    if isinstance(arg, list | str | dict):
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


def _builtin_keys(args: list[Value]) -> Value:
    """Return the keys of a dictionary as a list."""
    arg = args[0]
    if not isinstance(arg, dict):
        type_name = type(arg).__name__
        msg = f"keys() requires a dict, got {type_name}"
        raise PebbleRuntimeError(msg, line=0, column=0)
    return list(arg.keys())


def _builtin_values(args: list[Value]) -> Value:
    """Return the values of a dictionary as a list."""
    arg = args[0]
    if not isinstance(arg, dict):
        type_name = type(arg).__name__
        msg = f"values() requires a dict, got {type_name}"
        raise PebbleRuntimeError(msg, line=0, column=0)
    return list(arg.values())


# -- Registry ------------------------------------------------------------------

type BuiltinHandler = Callable[[list[Value]], Value]

BUILTINS: dict[str, tuple[int, BuiltinHandler]] = {
    "int": (1, _builtin_int),
    "float": (1, _builtin_float),
    "type": (1, _builtin_type),
    "len": (1, _builtin_len),
    "push": (2, _builtin_push),
    "pop": (1, _builtin_pop),
    "keys": (1, _builtin_keys),
    "values": (1, _builtin_values),
}
"""Map of runtime builtin names to ``(arity, handler)`` pairs."""

# Compile-time builtins have no runtime handler — the compiler handles them.
_PRINT_ARITY = 1
_RANGE_ARITIES: tuple[int, ...] = (1, 2, 3)

_MAP_ARITY = 2
_FILTER_ARITY = 2
_REDUCE_ARITY = 3

type Arity = int | tuple[int, ...]
"""Arity of a built-in function: a single count or a tuple of accepted counts."""

_STR_ARITY = 1

BUILTIN_ARITIES: dict[str, Arity] = {
    **{name: arity for name, (arity, _) in BUILTINS.items()},
    "str": _STR_ARITY,
    "print": _PRINT_ARITY,
    "range": _RANGE_ARITIES,
    "map": _MAP_ARITY,
    "filter": _FILTER_ARITY,
    "reduce": _REDUCE_ARITY,
    "next": 1,
}
"""Map of ALL builtin names (runtime + compile-time) to arity."""


METHOD_NONE = "$METHOD_NONE"
"""Sentinel value used to pad variable-arity method calls."""

SLICE_NONE = "$SLICE_NONE"
"""Sentinel value representing an omitted slice component."""


# -- Method arities (for analyzer validation) ---------------------------------

METHOD_ARITIES: dict[str, Arity] = {
    # String methods (user-visible arg count, excluding target)
    "upper": 0,
    "lower": 0,
    "strip": 0,
    "split": (0, 1),
    "replace": 2,
    "contains": 1,
    "starts_with": 1,
    "ends_with": 1,
    "find": 1,
    "count": 1,
    "join": 1,
    "repeat": 1,
    # List methods
    "push": 1,
    "pop": 0,
    "reverse": 0,
    "sort": 0,
}
"""Map of method names to their user-visible argument count (excluding target)."""


# -- Method handler type -------------------------------------------------------

type MethodHandler = Callable[[Value, list[Value]], Value]
"""Handle a method call: take (target, filtered_args), return result."""


def _require_str_arg(arg: Value, method_name: str) -> str:
    """Validate that *arg* is a string, raising if not."""
    if not isinstance(arg, str):
        type_name = type(arg).__name__
        msg = f"{method_name}() argument must be a string, got {type_name}"
        raise PebbleRuntimeError(msg, line=0, column=0)
    return arg


def _require_str_target(target: Value, method_name: str) -> str:
    """Narrow *target* to ``str`` or raise a runtime error."""
    if not isinstance(target, str):
        type_name = type(target).__name__
        msg = f"{method_name}() requires a string target, got {type_name}"
        raise PebbleRuntimeError(msg, line=0, column=0)
    return target


def _require_list_target(target: Value, method_name: str) -> list[Value]:
    """Narrow *target* to ``list`` or raise a runtime error."""
    if not isinstance(target, list):
        type_name = type(target).__name__
        msg = f"{method_name}() requires a list target, got {type_name}"
        raise PebbleRuntimeError(msg, line=0, column=0)
    return target


# -- String method handlers ----------------------------------------------------


def _method_upper(target: Value, _args: list[Value]) -> Value:
    """Convert a string to uppercase."""
    s = _require_str_target(target, "upper")
    return s.upper()


def _method_lower(target: Value, _args: list[Value]) -> Value:
    """Convert a string to lowercase."""
    s = _require_str_target(target, "lower")
    return s.lower()


def _method_strip(target: Value, _args: list[Value]) -> Value:
    """Remove leading and trailing whitespace."""
    s = _require_str_target(target, "strip")
    return s.strip()


def _method_split(target: Value, args: list[Value]) -> Value:
    """Split a string into a list of substrings."""
    s = _require_str_target(target, "split")
    if not args:
        result: list[Value] = list(s.split())
        return result
    sep = args[0]
    if not isinstance(sep, str):
        type_name = type(sep).__name__
        msg = f"split() separator must be a string, got {type_name}"
        raise PebbleRuntimeError(msg, line=0, column=0)
    if sep == "":
        msg = "split() separator cannot be empty"
        raise PebbleRuntimeError(msg, line=0, column=0)
    parts: list[Value] = list(s.split(sep))
    return parts


def _method_replace(target: Value, args: list[Value]) -> Value:
    """Replace all occurrences of a substring."""
    s = _require_str_target(target, "replace")
    old, new = args[0], args[1]
    if not isinstance(old, str) or not isinstance(new, str):
        msg = "replace() arguments must be strings"
        raise PebbleRuntimeError(msg, line=0, column=0)
    return s.replace(old, new)


def _method_str_contains(target: Value, args: list[Value]) -> Value:
    """Check if a string contains a substring."""
    s = _require_str_target(target, "contains")
    sub = _require_str_arg(args[0], "contains")
    return sub in s


def _method_starts_with(target: Value, args: list[Value]) -> Value:
    """Check if a string starts with a prefix."""
    s = _require_str_target(target, "starts_with")
    prefix = _require_str_arg(args[0], "starts_with")
    return s.startswith(prefix)


def _method_ends_with(target: Value, args: list[Value]) -> Value:
    """Check if a string ends with a suffix."""
    s = _require_str_target(target, "ends_with")
    suffix = _require_str_arg(args[0], "ends_with")
    return s.endswith(suffix)


def _method_find(target: Value, args: list[Value]) -> Value:
    """Find the index of a substring, or -1 if not found."""
    s = _require_str_target(target, "find")
    sub = _require_str_arg(args[0], "find")
    return s.find(sub)


def _method_count(target: Value, args: list[Value]) -> Value:
    """Count non-overlapping occurrences of a substring."""
    s = _require_str_target(target, "count")
    sub = _require_str_arg(args[0], "count")
    return s.count(sub)


def _method_join(target: Value, args: list[Value]) -> Value:
    """Join a list of strings with the target as separator."""
    s = _require_str_target(target, "join")
    items = args[0]
    if not isinstance(items, list):
        type_name = type(items).__name__
        msg = f"join() argument must be a list, got {type_name}"
        raise PebbleRuntimeError(msg, line=0, column=0)
    parts: list[str] = []
    for item in items:
        if not isinstance(item, str):
            type_name = type(item).__name__
            msg = f"join() list must contain strings, got {type_name}"
            raise PebbleRuntimeError(msg, line=0, column=0)
        parts.append(item)
    return s.join(parts)


def _method_repeat(target: Value, args: list[Value]) -> Value:
    """Repeat a string n times."""
    s = _require_str_target(target, "repeat")
    n = args[0]
    if not isinstance(n, int) or isinstance(n, bool):
        type_name = type(n).__name__
        msg = f"repeat() argument must be an integer, got {type_name}"
        raise PebbleRuntimeError(msg, line=0, column=0)
    if n < 0:
        msg = "repeat() count must not be negative"
        raise PebbleRuntimeError(msg, line=0, column=0)
    return s * n


_VOID: Value = None
"""Return value for list-mutating methods (push, reverse, sort)."""


# -- List method handlers ------------------------------------------------------


def _method_list_push(target: Value, args: list[Value]) -> Value:
    """Append a value to the list. Return null."""
    lst = _require_list_target(target, "push")
    lst.append(args[0])
    return _VOID


def _method_list_pop(target: Value, _args: list[Value]) -> Value:
    """Remove and return the last element."""
    lst = _require_list_target(target, "pop")
    if not lst:
        msg = "Cannot pop from an empty list"
        raise PebbleRuntimeError(msg, line=0, column=0)
    return lst.pop()


def _method_list_contains(target: Value, args: list[Value]) -> Value:
    """Check if a list contains a value."""
    lst = _require_list_target(target, "contains")
    return args[0] in lst


def _method_list_reverse(target: Value, _args: list[Value]) -> Value:
    """Reverse the list in place."""
    lst = _require_list_target(target, "reverse")
    lst.reverse()
    return _VOID


def _method_list_sort(target: Value, _args: list[Value]) -> Value:
    """Sort the list in place."""
    lst = _require_list_target(target, "sort")
    # Check for mixed types — only allow homogeneous int or string lists
    if lst:
        first_type = type(lst[0])
        for item in lst[1:]:
            if type(item) is not first_type:
                msg = "sort() requires all elements to be the same type"
                raise PebbleRuntimeError(msg, line=0, column=0)
    lst.sort()  # type: ignore[type-var]
    return _VOID


# -- Method registries ---------------------------------------------------------

STRING_METHODS: dict[str, tuple[int, MethodHandler]] = {
    "upper": (0, _method_upper),
    "lower": (0, _method_lower),
    "strip": (0, _method_strip),
    "split": (1, _method_split),
    "replace": (2, _method_replace),
    "contains": (1, _method_str_contains),
    "starts_with": (1, _method_starts_with),
    "ends_with": (1, _method_ends_with),
    "find": (1, _method_find),
    "count": (1, _method_count),
    "join": (1, _method_join),
    "repeat": (1, _method_repeat),
}
"""Map of string method names to ``(max_arity, handler)`` pairs."""

LIST_METHODS: dict[str, tuple[int, MethodHandler]] = {
    "push": (1, _method_list_push),
    "pop": (0, _method_list_pop),
    "contains": (1, _method_list_contains),
    "reverse": (0, _method_list_reverse),
    "sort": (0, _method_list_sort),
}
"""Map of list method names to ``(max_arity, handler)`` pairs."""
