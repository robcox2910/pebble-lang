"""Post-compilation bytecode optimizer for Pebble.

Apply peephole optimization passes to a :class:`~pebble.bytecode.CompiledProgram`
after the compiler has emitted bytecode and before the VM executes it.

Current passes:

* **Constant folding** — pre-compute arithmetic on literal operands.
* **Dead code elimination** — remove unreachable instructions after
  ``RETURN``, ``JUMP``, or ``HALT``.
"""

import operator

from pebble.bytecode import CodeObject, CompiledProgram, Instruction, OpCode

# ---------------------------------------------------------------------------
# Shared constants
# ---------------------------------------------------------------------------

# Opcodes that carry an absolute instruction-index operand
_JUMP_OPCODES: frozenset[OpCode] = frozenset(
    {
        OpCode.JUMP,
        OpCode.JUMP_IF_FALSE,
        OpCode.FOR_ITER,
        OpCode.SETUP_TRY,
    }
)

# ---------------------------------------------------------------------------
# Binary ops eligible for constant folding
# ---------------------------------------------------------------------------

type _Numeric = int | float
type _ConstType = type  # isinstance-compatible type or tuple of types
type _TypeSpec = _ConstType | tuple[_ConstType, ...]

# Sentinel distinct from any valid constant (including None/null).
_NO_FOLD: object = object()


def _logical_and(a: object, b: object) -> object:
    """Pebble logical AND — return *a* if falsy, else *b*."""
    return a if not a else b


def _logical_or(a: object, b: object) -> object:
    """Pebble logical OR — return *a* if truthy, else *b*."""
    return a or b


_BINARY_FOLDERS: dict[OpCode, tuple[_TypeSpec, _TypeSpec, object]] = {
    OpCode.ADD: ((int, float, str), (int, float, str), operator.add),
    OpCode.SUBTRACT: ((int, float), (int, float), operator.sub),
    OpCode.MULTIPLY: ((int, float), (int, float), operator.mul),
    OpCode.POWER: ((int, float), (int, float), operator.pow),
    OpCode.DIVIDE: ((int, float), (int, float), operator.truediv),
    OpCode.FLOOR_DIVIDE: ((int, float), (int, float), operator.floordiv),
    OpCode.MODULO: ((int, float), (int, float), operator.mod),
    # Comparisons
    OpCode.EQUAL: (
        (int, float, str, bool, type(None)),
        (int, float, str, bool, type(None)),
        operator.eq,
    ),
    OpCode.NOT_EQUAL: (
        (int, float, str, bool, type(None)),
        (int, float, str, bool, type(None)),
        operator.ne,
    ),
    OpCode.LESS_THAN: ((int, float), (int, float), operator.lt),
    OpCode.LESS_EQUAL: ((int, float), (int, float), operator.le),
    OpCode.GREATER_THAN: ((int, float), (int, float), operator.gt),
    OpCode.GREATER_EQUAL: ((int, float), (int, float), operator.ge),
    # Logical — use Pebble's short-circuit semantics, NOT bitwise operators.
    # Python's operator.and_/or_ are bitwise and crash on str/None.
    OpCode.AND: (
        (bool, int, float, str, type(None)),
        (bool, int, float, str, type(None)),
        _logical_and,
    ),
    OpCode.OR: (
        (bool, int, float, str, type(None)),
        (bool, int, float, str, type(None)),
        _logical_or,
    ),
    # Bitwise binary
    OpCode.BIT_AND: ((int,), (int,), operator.and_),
    OpCode.BIT_OR: ((int,), (int,), operator.or_),
    OpCode.BIT_XOR: ((int,), (int,), operator.xor),
    OpCode.LEFT_SHIFT: ((int,), (int,), operator.lshift),
    OpCode.RIGHT_SHIFT: ((int,), (int,), operator.rshift),
}

# Ops that must not fold when the right operand is zero
_ZERO_GUARDED: frozenset[OpCode] = frozenset(
    {
        OpCode.DIVIDE,
        OpCode.FLOOR_DIVIDE,
        OpCode.MODULO,
    }
)

# Ops that must not fold when the right operand is negative
_NEGATIVE_SHIFT_GUARDED: frozenset[OpCode] = frozenset(
    {
        OpCode.LEFT_SHIFT,
        OpCode.RIGHT_SHIFT,
    }
)

# Binary ops where booleans are allowed as operands
_BOOL_SAFE_OPS: frozenset[OpCode] = frozenset(
    {
        OpCode.EQUAL,
        OpCode.NOT_EQUAL,
        OpCode.LESS_THAN,
        OpCode.LESS_EQUAL,
        OpCode.GREATER_THAN,
        OpCode.GREATER_EQUAL,
        OpCode.AND,
        OpCode.OR,
    }
)

# ---------------------------------------------------------------------------
# Unary ops eligible for constant folding
# ---------------------------------------------------------------------------

_UNARY_FOLDERS: dict[OpCode, tuple[_TypeSpec, object]] = {
    OpCode.NEGATE: ((int, float), operator.neg),
    OpCode.NOT: ((bool, int, float, str, type(None)), operator.not_),
    OpCode.BIT_NOT: ((int,), operator.invert),
}


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------


def optimize(program: CompiledProgram) -> CompiledProgram:
    """Apply all optimization passes to every CodeObject in *program*."""
    optimized_main = _optimize_code_object(program.main)
    optimized_functions = {
        name: _optimize_code_object(code) for name, code in program.functions.items()
    }
    return CompiledProgram(
        main=optimized_main,
        functions=optimized_functions,
        structs=program.structs,
        struct_field_types=program.struct_field_types,
        class_methods=program.class_methods,
        enums=program.enums,
        class_parents=program.class_parents,
    )


# ---------------------------------------------------------------------------
# Per-CodeObject pipeline
# ---------------------------------------------------------------------------


def _optimize_code_object(code: CodeObject) -> CodeObject:
    """Apply all passes to a single CodeObject, returning the optimized copy."""
    instructions = list(code.instructions)
    constants: list[int | float | str | bool | None] = list(code.constants)

    # Loop constant folding until no more folds are possible
    while True:
        instructions, constants, changed = _fold_constants(instructions, constants)
        if not changed:
            break

    # Dead code elimination
    instructions = _eliminate_dead_code(instructions)

    result = CodeObject(
        name=code.name,
        parameters=list(code.parameters),
        cell_variables=list(code.cell_variables),
        free_variables=list(code.free_variables),
        param_types=list(code.param_types),
        return_type=code.return_type,
        is_generator=code.is_generator,
        is_async=code.is_async,
    )
    # Rebuild constant pool through add_constant (which deduplicates),
    # then remap LOAD_CONST operands from old indices to new indices.
    old_to_new_const: dict[int, int] = {}
    for old_idx, c in enumerate(constants):
        old_to_new_const[old_idx] = result.add_constant(c)

    result.instructions = [
        Instruction(OpCode.LOAD_CONST, old_to_new_const[instr.operand], instr.location)
        if instr.opcode == OpCode.LOAD_CONST and isinstance(instr.operand, int)
        else instr
        for instr in instructions
    ]
    return result


# ---------------------------------------------------------------------------
# Pass 1 — Constant folding
# ---------------------------------------------------------------------------


def _build_jump_targets(instructions: list[Instruction]) -> frozenset[int]:
    """Return the set of instruction indices that are jump targets."""
    return frozenset(
        instr.operand
        for instr in instructions
        if instr.opcode in _JUMP_OPCODES and isinstance(instr.operand, int)
    )


def _rewrite_jump_operands(
    instructions: list[Instruction],
    offset_map: dict[int, int],
) -> list[Instruction]:
    """Rewrite jump operands using *offset_map*."""
    result: list[Instruction] = []
    for instr in instructions:
        if instr.opcode in _JUMP_OPCODES and isinstance(instr.operand, int):
            new_target = offset_map.get(instr.operand, instr.operand)
            result.append(Instruction(instr.opcode, new_target, instr.location))
        else:
            result.append(instr)
    return result


def _fold_constants(
    instructions: list[Instruction],
    constants: list[int | float | str | bool | None],
) -> tuple[list[Instruction], list[int | float | str | bool | None], bool]:
    """Fold constant binary and unary operations in a single pass.

    Return *(new_instructions, constants, changed)*.  Jump operands are
    adjusted to reflect removed instructions.
    """
    jump_targets = _build_jump_targets(instructions)
    new_instrs: list[Instruction] = []
    old_to_new: dict[int, int] = {}
    changed = False
    i = 0

    while i < len(instructions):
        instr = instructions[i]
        new_pos = len(new_instrs)

        # Try binary fold: LOAD_CONST a, LOAD_CONST b, OP → LOAD_CONST result
        if _can_binary_fold(instructions, i, jump_targets):
            folded, constants = _apply_binary_fold(instructions, i, constants)
            if folded is not None:
                new_instrs.append(folded)
                old_to_new[i] = old_to_new[i + 1] = old_to_new[i + 2] = new_pos
                i += 3
                changed = True
                continue

        # Try unary fold: LOAD_CONST a, UNARY_OP → LOAD_CONST result
        if _can_unary_fold(instructions, i, jump_targets):
            folded, constants = _apply_unary_fold(instructions, i, constants)
            if folded is not None:
                new_instrs.append(folded)
                old_to_new[i] = old_to_new[i + 1] = new_pos
                i += 2
                changed = True
                continue

        old_to_new[i] = new_pos
        new_instrs.append(instr)
        i += 1

    if not changed:
        return new_instrs, constants, False

    return _rewrite_jump_operands(new_instrs, old_to_new), constants, True


def _can_binary_fold(
    instructions: list[Instruction],
    i: int,
    jump_targets: frozenset[int],
) -> bool:
    """Check if instructions at *i* form a foldable binary pattern."""
    return (
        instructions[i].opcode == OpCode.LOAD_CONST
        and i + 2 < len(instructions)
        and instructions[i + 1].opcode == OpCode.LOAD_CONST
        and (i + 1) not in jump_targets
        and instructions[i + 2].opcode in _BINARY_FOLDERS
    )


def _apply_binary_fold(
    instructions: list[Instruction],
    i: int,
    constants: list[int | float | str | bool | None],
) -> tuple[Instruction | None, list[int | float | str | bool | None]]:
    """Attempt to fold a binary pattern starting at *i*.

    Return *(replacement_instruction, constants)* or *(None, constants)*.
    """
    a_idx = instructions[i].operand
    b_idx = instructions[i + 1].operand
    op = instructions[i + 2].opcode

    if not isinstance(a_idx, int) or not isinstance(b_idx, int):
        return None, constants

    folded = _try_fold_binary(op, constants[a_idx], constants[b_idx])
    if folded is _NO_FOLD:
        return None, constants

    result_idx = len(constants)
    constants.append(folded)  # type: ignore[arg-type]
    return Instruction(OpCode.LOAD_CONST, result_idx, instructions[i].location), constants


def _can_unary_fold(
    instructions: list[Instruction],
    i: int,
    jump_targets: frozenset[int],
) -> bool:
    """Check if instructions at *i* form a foldable unary pattern."""
    return (
        instructions[i].opcode == OpCode.LOAD_CONST
        and i not in jump_targets
        and i + 1 < len(instructions)
        and instructions[i + 1].opcode in _UNARY_FOLDERS
    )


def _apply_unary_fold(
    instructions: list[Instruction],
    i: int,
    constants: list[int | float | str | bool | None],
) -> tuple[Instruction | None, list[int | float | str | bool | None]]:
    """Attempt to fold a unary pattern starting at *i*.

    Return *(replacement_instruction, constants)* or *(None, constants)*.
    """
    a_idx = instructions[i].operand
    if not isinstance(a_idx, int):
        return None, constants

    folded = _try_fold_unary(instructions[i + 1].opcode, constants[a_idx])
    if folded is _NO_FOLD:
        return None, constants

    result_idx = len(constants)
    constants.append(folded)  # type: ignore[arg-type]
    return Instruction(OpCode.LOAD_CONST, result_idx, instructions[i].location), constants


def _try_fold_binary(  # noqa: PLR0911
    op: OpCode,
    a: int | float | str | bool | None,
    b: int | float | str | bool | None,
) -> int | float | str | bool | None | object:
    """Attempt to fold a binary operation on two constants.

    Return the result value, or :data:`_NO_FOLD` if the fold is not safe.
    """
    if op not in _BINARY_FOLDERS:
        return _NO_FOLD

    allowed_a, allowed_b, func = _BINARY_FOLDERS[op]

    # Never fold bools as numeric — Pebble treats them differently.
    if (isinstance(a, bool) or isinstance(b, bool)) and op not in _BOOL_SAFE_OPS:
        return _NO_FOLD

    if not isinstance(a, allowed_a) or not isinstance(b, allowed_b):
        return _NO_FOLD

    # Never fold division/modulo by zero or negative shifts — let the VM raise
    if (op in _ZERO_GUARDED and isinstance(b, (int, float)) and b == 0) or (
        op in _NEGATIVE_SHIFT_GUARDED and isinstance(b, int) and b < 0
    ):
        return _NO_FOLD

    # Type compatibility: ADD requires matching types (or int+float)
    if op == OpCode.ADD and isinstance(a, str) != isinstance(b, str):
        return _NO_FOLD

    result = func(a, b)  # type: ignore[operator]

    # POWER can produce complex (e.g. (-1)**0.5) — not a valid Pebble type
    if isinstance(result, complex):
        return _NO_FOLD

    return result  # pyright: ignore[reportUnknownVariableType]


def _try_fold_unary(
    op: OpCode,
    a: int | float | str | bool | None,
) -> int | float | str | bool | None | object:
    """Attempt to fold a unary operation on a constant.

    Return the result value, or :data:`_NO_FOLD` if the fold is not safe.
    """
    if op not in _UNARY_FOLDERS:
        return _NO_FOLD

    allowed, func = _UNARY_FOLDERS[op]

    # Never fold bools as numeric (NEGATE / BIT_NOT)
    if isinstance(a, bool) and op in {OpCode.NEGATE, OpCode.BIT_NOT}:
        return _NO_FOLD

    if not isinstance(a, allowed):
        return _NO_FOLD

    return func(a)  # type: ignore[operator]


# ---------------------------------------------------------------------------
# Pass 2 — Dead code elimination
# ---------------------------------------------------------------------------

# Opcodes that unconditionally end execution of the current path
_TERMINAL_OPCODES: frozenset[OpCode] = frozenset(
    {
        OpCode.RETURN,
        OpCode.JUMP,
        OpCode.HALT,
        OpCode.THROW,
    }
)


def _eliminate_dead_code(instructions: list[Instruction]) -> list[Instruction]:
    """Remove unreachable instructions and adjust jump targets.

    After a RETURN, JUMP, or HALT, mark subsequent instructions as dead
    until hitting an index that is a jump target.
    """
    if not instructions:
        return instructions

    jump_targets = _build_jump_targets(instructions)
    live = _mark_live_instructions(instructions, jump_targets)

    # Build old→new index map and collect live instructions
    old_to_new: dict[int, int] = {}
    new_instrs: list[Instruction] = []
    for old_idx, instr in enumerate(instructions):
        if live[old_idx]:
            old_to_new[old_idx] = len(new_instrs)
            new_instrs.append(instr)

    # For dead indices, map to the next live instruction
    _fill_dead_index_map(old_to_new, len(instructions), len(new_instrs))

    return _rewrite_jump_operands(new_instrs, old_to_new)


def _mark_live_instructions(
    instructions: list[Instruction],
    jump_targets: frozenset[int],
) -> list[bool]:
    """Mark each instruction as live or dead."""
    live = [True] * len(instructions)
    dead = False
    for i, instr in enumerate(instructions):
        if dead:
            if i in jump_targets:
                dead = False
            else:
                live[i] = False
                continue
        if instr.opcode in _TERMINAL_OPCODES:
            dead = True
    return live


def _fill_dead_index_map(
    old_to_new: dict[int, int],
    old_len: int,
    new_len: int,
) -> None:
    """Map dead instruction indices to the next live instruction index."""
    next_live = new_len
    for old_idx in range(old_len - 1, -1, -1):
        if old_idx in old_to_new:
            next_live = old_to_new[old_idx]
        else:
            old_to_new[old_idx] = next_live
