"""AST-based code formatter for the Pebble language.

Produce canonical, readable output from any valid Pebble source:

    formatted = Formatter(source).format()

The formatter parses source into an AST, walks every node, and emits
consistently styled code with 4-space indentation, operator spacing,
and brace placement. Comments are extracted separately and interleaved
at their original line positions.
"""

from pebble.ast_nodes import (
    ArrayLiteral,
    Assignment,
    AsyncFunctionDef,
    AwaitExpression,
    BinaryOp,
    BooleanLiteral,
    BreakStatement,
    CapturePattern,
    ClassDef,
    ConstAssignment,
    ContinueStatement,
    DictLiteral,
    EnumDef,
    EnumPattern,
    Expression,
    FieldAccess,
    FieldAssignment,
    FloatLiteral,
    ForLoop,
    FromImportStatement,
    FunctionCall,
    FunctionDef,
    FunctionExpression,
    Identifier,
    IfStatement,
    ImportStatement,
    IndexAccess,
    IndexAssignment,
    IntegerLiteral,
    ListComprehension,
    LiteralPattern,
    MatchCase,
    MatchStatement,
    MethodCall,
    NullLiteral,
    OrPattern,
    Parameter,
    Pattern,
    PrintStatement,
    Program,
    Reassignment,
    ReturnStatement,
    SliceAccess,
    Statement,
    StringInterpolation,
    StringLiteral,
    StructDef,
    SuperMethodCall,
    ThrowStatement,
    TryCatch,
    UnaryOp,
    UnpackAssignment,
    UnpackConstAssignment,
    UnpackReassignment,
    WhileLoop,
    WildcardPattern,
    YieldStatement,
)
from pebble.lexer import Lexer
from pebble.parser import Parser

__all__ = ["Formatter", "extract_comments"]

# -- Escape map (inverse of Lexer._ESCAPE_MAP) --------------------------------

_REVERSE_ESCAPE: dict[str, str] = {
    "\n": "\\n",
    "\t": "\\t",
    "\\": "\\\\",
    '"': '\\"',
    "{": "\\{",
    "\0": "\\0",
}

# -- Operator precedence (mirrors parser._INFIX_PRECEDENCE) --------------------

_OPERATOR_PRECEDENCE: dict[str, int] = {
    "or": 1,
    "and": 2,
    "==": 3,
    "!=": 3,
    "<": 4,
    "<=": 4,
    ">": 4,
    ">=": 4,
    "|": 5,
    "^": 6,
    "&": 7,
    "<<": 8,
    ">>": 8,
    "+": 9,
    "-": 9,
    "*": 10,
    "/": 10,
    "//": 10,
    "%": 10,
    "**": 11,
}

_RIGHT_ASSOCIATIVE_OPS: frozenset[str] = frozenset({"**"})

# Statements that introduce definitions (get blank lines between them)
_DEFINITION_TYPES = (FunctionDef, AsyncFunctionDef, StructDef, ClassDef, EnumDef)

_INDENT = "    "


# -- Comment extraction --------------------------------------------------------


def _scan_string_char(source: str, pos: int, length: int) -> tuple[int, bool, int]:
    """Advance past one character inside a string literal.

    Return ``(new_pos, still_in_string, interp_depth_delta)``.
    """
    ch = source[pos]
    if ch == "\\" and pos + 1 < length:
        return pos + 2, True, 0
    if ch == "{":
        return pos + 1, False, 1  # entering interpolation
    if ch == '"':
        return pos + 1, False, 0  # closing quote
    return pos + 1, True, 0


def _scan_interp_char(
    source: str, pos: int, interp_depth: int
) -> tuple[int, int, bool, str | None]:
    """Advance past one character inside an interpolation expression.

    Return ``(new_pos, new_depth, entered_string, comment_or_none)``.
    """
    ch = source[pos]
    if ch == "{":
        return pos + 1, interp_depth + 1, False, None
    if ch == "}":
        new_depth = interp_depth - 1
        return pos + 1, new_depth, new_depth == 0, None
    if ch == '"':
        return pos + 1, interp_depth, True, None
    if ch == "#":
        comment = source[pos:].split("\n", maxsplit=1)[0]
        return pos + len(comment), interp_depth, False, comment
    return pos + 1, interp_depth, False, None


def extract_comments(source: str) -> dict[int, str]:
    """Extract ``#`` comments from raw source, keyed by 1-based line number.

    Track string and interpolation state so ``#`` inside string literals
    or interpolated expressions is not treated as a comment.
    """
    comments: dict[int, str] = {}
    line = 1
    pos = 0
    length = len(source)
    in_string = False
    interp_depth = 0

    while pos < length:
        ch = source[pos]

        if ch == "\n":
            line += 1
            pos += 1
            continue

        if in_string:
            pos, in_string, delta = _scan_string_char(source, pos, length)
            if delta:
                interp_depth = 1
            continue

        if interp_depth > 0:
            pos, interp_depth, entered_string, comment = _scan_interp_char(
                source, pos, interp_depth
            )
            if entered_string:
                in_string = True
            if comment is not None:
                comments[line] = comment
            continue

        if ch == '"':
            in_string = True
            pos += 1
            continue

        if ch == "#":
            comment = source[pos:].split("\n", maxsplit=1)[0]
            comments[line] = comment
            pos += len(comment)
            continue

        pos += 1

    return comments


# -- String escaping -----------------------------------------------------------


def _escape_string(value: str) -> str:
    """Re-escape a decoded string value for output."""
    chars: list[str] = []
    for ch in value:
        if ch in _REVERSE_ESCAPE:
            chars.append(_REVERSE_ESCAPE[ch])
        else:
            chars.append(ch)
    return "".join(chars)


# -- Comment classification ----------------------------------------------------


def _classify_comments(
    source: str,
    comments: dict[int, str],
) -> tuple[dict[int, str], dict[int, str]]:
    """Split comments into standalone and inline.

    Return ``(standalone, inline)`` dicts keyed by line number.
    """
    source_lines = source.split("\n")
    standalone: dict[int, str] = {}
    inline: dict[int, str] = {}
    for line_no, comment in comments.items():
        if line_no <= len(source_lines):
            src_line = source_lines[line_no - 1].strip()
            if src_line == comment.strip():
                standalone[line_no] = comment
            else:
                inline[line_no] = comment
    return standalone, inline


def _count_code_lines_before(source: str, comments: dict[int, str], target_line: int) -> int:
    """Count non-comment, non-blank source lines before *target_line*."""
    source_lines = source.split("\n")
    count = 0
    for i in range(1, target_line):
        if i not in comments:
            line = source_lines[i - 1].strip() if i <= len(source_lines) else ""
            if line and not line.startswith("#"):
                count += 1
    return count


# -- Formatter -----------------------------------------------------------------


class Formatter:
    """Format Pebble source code into canonical style.

    Usage::

        formatted = Formatter(source).format()
    """

    def __init__(self, source: str) -> None:
        """Create a formatter for the given source text."""
        self._source = source
        self._comments = extract_comments(source)
        self._indent = 0
        self._lines: list[str] = []

    def format(self) -> str:
        """Return the formatted source code."""
        if not self._source.strip():
            return "\n"

        tokens = Lexer(self._source).tokenize()
        program = Parser(tokens).parse()
        self._format_program(program)
        return self._build_output()

    # -- Output building -------------------------------------------------------

    def _emit(self, text: str) -> None:
        """Append a formatted line (with current indentation)."""
        self._lines.append(f"{_INDENT * self._indent}{text}")

    def _build_output(self) -> str:
        """Build final output with comments interleaved."""
        result = self._interleave_comments()
        # Collapse multiple blank lines into one
        while "\n\n\n" in result:
            result = result.replace("\n\n\n", "\n\n")
        if not result.endswith("\n"):
            result += "\n"
        return result

    def _interleave_comments(self) -> str:
        """Interleave extracted comments into the formatted output."""
        if not self._comments:
            return "\n".join(self._lines)

        standalone, inline = _classify_comments(self._source, self._comments)
        out_lines = "\n".join(self._lines).split("\n")
        source_lines = self._source.split("\n")

        result_lines: list[str] = []
        used: set[int] = set()

        # Emit standalone comments that appear before any code
        src_line = 1
        while src_line in standalone:
            result_lines.append(standalone[src_line])
            used.add(src_line)
            src_line += 1

        for idx, raw_line in enumerate(out_lines):
            # Append inline comment if the formatted line matches
            annotated = self._attach_inline_comment(raw_line, inline, source_lines, used)
            result_lines.append(annotated)

            # Insert any standalone comments that belong after this line
            self._insert_standalone_after(idx, out_lines, standalone, used, result_lines)

        # Append remaining comments at end of file
        result_lines.extend(self._comments[ln] for ln in sorted(self._comments) if ln not in used)
        return "\n".join(result_lines)

    @staticmethod
    def _attach_inline_comment(
        line: str,
        inline: dict[int, str],
        source_lines: list[str],
        used: set[int],
    ) -> str:
        """Attach an inline comment to *line* if one matches."""
        stripped = line.strip()
        if not stripped:
            return line
        for ln, cmt in inline.items():
            if ln in used:
                continue
            src = source_lines[ln - 1] if ln <= len(source_lines) else ""
            src_code = src.split("#")[0].strip()
            if src_code and stripped.startswith(src_code.split()[0]):
                used.add(ln)
                return f"{line}  {cmt}"
        return line

    def _insert_standalone_after(
        self,
        idx: int,
        out_lines: list[str],
        standalone: dict[int, str],
        used: set[int],
        result_lines: list[str],
    ) -> None:
        """Insert standalone comments that belong between idx and idx+1."""
        if idx >= len(out_lines) - 1:
            return
        # Count how many non-blank formatted lines we've seen so far
        fmt_code_count = sum(1 for i in range(idx + 1) if out_lines[i].strip())
        for ln in sorted(standalone):
            if ln in used:
                continue
            code_before = _count_code_lines_before(self._source, self._comments, ln)
            if fmt_code_count == code_before:
                result_lines.append(standalone[ln])
                used.add(ln)

    # -- Program ---------------------------------------------------------------

    def _format_program(self, program: Program) -> None:
        """Format the top-level program statements."""
        prev_was_def = False
        for stmt in program.statements:
            is_def = isinstance(stmt, _DEFINITION_TYPES)
            if (is_def or prev_was_def) and self._lines and self._lines[-1] != "":
                self._lines.append("")
            self._format_statement(stmt)
            prev_was_def = is_def

    # -- Statements ------------------------------------------------------------

    def _format_statement(self, stmt: Statement) -> None:  # noqa: C901, PLR0912, PLR0915
        """Format a single statement."""
        match stmt:
            case Assignment():
                self._format_assignment(stmt)
            case ConstAssignment():
                self._format_const_assignment(stmt)
            case UnpackAssignment():
                self._format_unpack_assignment(stmt, "let")
            case UnpackConstAssignment():
                self._format_unpack_assignment(stmt, "const")
            case Reassignment():
                self._emit(f"{stmt.name} = {self._format_expression(stmt.value)}")
            case UnpackReassignment():
                names = ", ".join(stmt.names)
                self._emit(f"{names} = {self._format_expression(stmt.value)}")
            case PrintStatement():
                self._emit(f"print({self._format_expression(stmt.expression)})")
            case IfStatement():
                self._format_if(stmt)
            case WhileLoop():
                self._format_while(stmt)
            case ForLoop():
                self._format_for(stmt)
            case FunctionDef():
                self._format_function_def(stmt)
            case AsyncFunctionDef():
                self._format_async_function_def(stmt)
            case ReturnStatement():
                if stmt.value is None:
                    self._emit("return")
                else:
                    self._emit(f"return {self._format_expression(stmt.value)}")
            case YieldStatement():
                if stmt.value is None:
                    self._emit("yield")
                else:
                    self._emit(f"yield {self._format_expression(stmt.value)}")
            case BreakStatement():
                self._emit("break")
            case ContinueStatement():
                self._emit("continue")
            case IndexAssignment():
                target = self._format_expression(stmt.target)
                index = self._format_expression(stmt.index)
                value = self._format_expression(stmt.value)
                self._emit(f"{target}[{index}] = {value}")
            case FieldAssignment():
                target = self._format_expression(stmt.target)
                value = self._format_expression(stmt.value)
                self._emit(f"{target}.{stmt.field} = {value}")
            case TryCatch():
                self._format_try_catch(stmt)
            case ThrowStatement():
                self._emit(f"throw {self._format_expression(stmt.value)}")
            case MatchStatement():
                self._format_match(stmt)
            case StructDef():
                self._format_struct(stmt)
            case ClassDef():
                self._format_class(stmt)
            case EnumDef():
                self._format_enum(stmt)
            case ImportStatement():
                self._emit(f'import "{_escape_string(stmt.path)}"')
            case FromImportStatement():
                names = ", ".join(stmt.names)
                self._emit(f'from "{_escape_string(stmt.path)}" import {names}')
            case _:
                # Expression statement (bare function call, etc.)
                self._emit(self._format_expression(stmt))  # type: ignore[arg-type]

    def _format_assignment(self, stmt: Assignment) -> None:
        """Format a let declaration."""
        type_str = f": {stmt.type_annotation}" if stmt.type_annotation else ""
        self._emit(f"let {stmt.name}{type_str} = {self._format_expression(stmt.value)}")

    def _format_const_assignment(self, stmt: ConstAssignment) -> None:
        """Format a const declaration."""
        type_str = f": {stmt.type_annotation}" if stmt.type_annotation else ""
        self._emit(f"const {stmt.name}{type_str} = {self._format_expression(stmt.value)}")

    def _format_unpack_assignment(
        self, stmt: UnpackAssignment | UnpackConstAssignment, keyword: str
    ) -> None:
        """Format a let/const unpack assignment."""
        names = ", ".join(stmt.names)
        self._emit(f"{keyword} {names} = {self._format_expression(stmt.value)}")

    def _format_if(self, stmt: IfStatement) -> None:
        """Format an if/else statement."""
        cond = self._format_expression(stmt.condition)
        self._emit(f"if {cond} {{")
        self._format_block(stmt.body)
        if stmt.else_body is None:
            self._emit("}")
            return
        # Detect else-if chain
        if len(stmt.else_body) == 1 and isinstance(stmt.else_body[0], IfStatement):
            self._format_else_if(stmt.else_body[0])
        else:
            self._emit("} else {")
            self._format_block(stmt.else_body)
            self._emit("}")

    def _format_else_if(self, inner: IfStatement) -> None:
        """Format an else-if chain continuation."""
        inner_cond = self._format_expression(inner.condition)
        self._emit(f"}} else if {inner_cond} {{")
        self._format_block(inner.body)
        if inner.else_body is None:
            self._emit("}")
            return
        if len(inner.else_body) == 1 and isinstance(inner.else_body[0], IfStatement):
            self._format_else_if(inner.else_body[0])
        else:
            self._emit("} else {")
            self._format_block(inner.else_body)
            self._emit("}")

    def _format_while(self, stmt: WhileLoop) -> None:
        """Format a while loop."""
        cond = self._format_expression(stmt.condition)
        self._emit(f"while {cond} {{")
        self._format_block(stmt.body)
        self._emit("}")

    def _format_for(self, stmt: ForLoop) -> None:
        """Format a for loop."""
        iterable = self._format_expression(stmt.iterable)
        self._emit(f"for {stmt.variable} in {iterable} {{")
        self._format_block(stmt.body)
        self._emit("}")

    def _format_function_def(self, stmt: FunctionDef) -> None:
        """Format a function definition."""
        params = self._format_params(stmt.parameters)
        ret = f" -> {stmt.return_type}" if stmt.return_type else ""
        self._emit(f"fn {stmt.name}({params}){ret} {{")
        self._format_block(stmt.body)
        self._emit("}")

    def _format_async_function_def(self, stmt: AsyncFunctionDef) -> None:
        """Format an async function definition."""
        params = self._format_params(stmt.parameters)
        ret = f" -> {stmt.return_type}" if stmt.return_type else ""
        self._emit(f"async fn {stmt.name}({params}){ret} {{")
        self._format_block(stmt.body)
        self._emit("}")

    def _format_try_catch(self, stmt: TryCatch) -> None:
        """Format a try/catch/finally statement."""
        self._emit("try {")
        self._format_block(stmt.body)
        catch_var = f" {stmt.catch_variable}" if stmt.catch_variable else ""
        self._emit(f"}} catch{catch_var} {{")
        self._format_block(stmt.catch_body)
        if stmt.finally_body is not None:
            self._emit("} finally {")
            self._format_block(stmt.finally_body)
        self._emit("}")

    def _format_match(self, stmt: MatchStatement) -> None:
        """Format a match statement."""
        value = self._format_expression(stmt.value)
        self._emit(f"match {value} {{")
        self._indent += 1
        for case in stmt.cases:
            self._format_match_case(case)
        self._indent -= 1
        self._emit("}")

    def _format_match_case(self, case: MatchCase) -> None:
        """Format a single match case."""
        pattern = self._format_pattern(case.pattern)
        self._emit(f"case {pattern} {{")
        self._format_block(case.body)
        self._emit("}")

    def _format_struct(self, stmt: StructDef) -> None:
        """Format a struct definition."""
        self._emit(f"struct {stmt.name} {{")
        self._indent += 1
        for i, field in enumerate(stmt.fields):
            suffix = "," if i < len(stmt.fields) - 1 else ""
            type_str = f": {field.type_annotation}" if field.type_annotation else ""
            self._emit(f"{field.name}{type_str}{suffix}")
        self._indent -= 1
        self._emit("}")

    def _format_class(self, stmt: ClassDef) -> None:
        """Format a class definition."""
        extends = f" extends {stmt.parent}" if stmt.parent else ""
        self._emit(f"class {stmt.name}{extends} {{")
        self._indent += 1
        for i, field in enumerate(stmt.fields):
            suffix = "," if i < len(stmt.fields) - 1 or stmt.methods else ""
            type_str = f": {field.type_annotation}" if field.type_annotation else ""
            self._emit(f"{field.name}{type_str}{suffix}")
        if stmt.fields and stmt.methods:
            self._lines.append("")  # blank line between fields and methods
        for i, method in enumerate(stmt.methods):
            params = self._format_params(method.parameters)
            ret = f" -> {method.return_type}" if method.return_type else ""
            self._emit(f"fn {method.name}({params}){ret} {{")
            self._format_block(method.body)
            self._emit("}")
            if i < len(stmt.methods) - 1:
                self._lines.append("")  # blank line between methods
        self._indent -= 1
        self._emit("}")

    def _format_enum(self, stmt: EnumDef) -> None:
        """Format an enum definition."""
        self._emit(f"enum {stmt.name} {{")
        self._indent += 1
        for i, variant in enumerate(stmt.variants):
            suffix = "," if i < len(stmt.variants) - 1 else ""
            self._emit(f"{variant}{suffix}")
        self._indent -= 1
        self._emit("}")

    # -- Block helper ----------------------------------------------------------

    def _format_block(self, stmts: list[Statement]) -> None:
        """Format a block of statements with increased indentation."""
        self._indent += 1
        for stmt in stmts:
            self._format_statement(stmt)
        self._indent -= 1

    # -- Parameter formatting --------------------------------------------------

    def _format_params(self, params: list[Parameter]) -> str:
        """Format a parameter list."""
        parts: list[str] = []
        for p in params:
            s = p.name
            if p.type_annotation:
                s += f": {p.type_annotation}"
            if p.default is not None:
                s += f" = {self._format_expression(p.default)}"
            parts.append(s)
        return ", ".join(parts)

    # -- Pattern formatting ----------------------------------------------------

    def _format_pattern(self, pattern: Pattern) -> str:
        """Format a match pattern."""
        match pattern:
            case LiteralPattern():
                return self._format_literal_pattern_value(pattern.value)
            case WildcardPattern():
                return "_"
            case CapturePattern():
                return f"let {pattern.name}"
            case OrPattern():
                parts = [self._format_literal_pattern_value(p.value) for p in pattern.patterns]
                return " | ".join(parts)
            case EnumPattern():
                return f"{pattern.enum_name}.{pattern.variant_name}"

    @staticmethod
    def _format_literal_pattern_value(value: int | float | str | bool | None) -> str:
        """Format a literal value used in a pattern."""
        if value is None:
            return "null"
        if isinstance(value, bool):
            return "true" if value else "false"
        if isinstance(value, str):
            return f'"{_escape_string(value)}"'
        return str(value)

    # -- Expressions -----------------------------------------------------------

    def _format_expression(self, expr: Expression) -> str:  # noqa: C901, PLR0912, PLR0911
        """Format an expression node to a string."""
        match expr:
            case IntegerLiteral():
                return str(expr.value)
            case FloatLiteral():
                return str(expr.value)
            case StringLiteral():
                return f'"{_escape_string(expr.value)}"'
            case BooleanLiteral():
                return "true" if expr.value else "false"
            case NullLiteral():
                return "null"
            case Identifier():
                return expr.name
            case UnaryOp():
                operand = self._format_expression(expr.operand)
                if expr.operator == "not":
                    return f"not {operand}"
                return f"{expr.operator}{operand}"
            case BinaryOp():
                return self._format_binary_op(expr)
            case FunctionCall():
                args = ", ".join(self._format_expression(a) for a in expr.arguments)
                return f"{expr.name}({args})"
            case StringInterpolation():
                return self._format_interpolation(expr)
            case ArrayLiteral():
                elements = ", ".join(self._format_expression(e) for e in expr.elements)
                return f"[{elements}]"
            case ListComprehension():
                mapping = self._format_expression(expr.mapping)
                iterable = self._format_expression(expr.iterable)
                cond = f" if {self._format_expression(expr.condition)}" if expr.condition else ""
                return f"[{mapping} for {expr.variable} in {iterable}{cond}]"
            case DictLiteral():
                entries = ", ".join(
                    f"{self._format_expression(k)}: {self._format_expression(v)}"
                    for k, v in expr.entries
                )
                return f"{{{entries}}}"
            case IndexAccess():
                target = self._format_expression(expr.target)
                index = self._format_expression(expr.index)
                return f"{target}[{index}]"
            case SliceAccess():
                return self._format_slice(expr)
            case MethodCall():
                target = self._format_expression(expr.target)
                args = ", ".join(self._format_expression(a) for a in expr.arguments)
                return f"{target}.{expr.method}({args})"
            case FieldAccess():
                target = self._format_expression(expr.target)
                return f"{target}.{expr.field}"
            case FunctionExpression():
                return self._format_function_expression(expr)
            case SuperMethodCall():
                args = ", ".join(self._format_expression(a) for a in expr.arguments)
                return f"super.{expr.method}({args})"
            case AwaitExpression():
                return f"await {self._format_expression(expr.value)}"

    def _format_binary_op(self, expr: BinaryOp) -> str:
        """Format a binary operation with precedence-based parenthesization."""
        left = self._format_expression(expr.left)
        right = self._format_expression(expr.right)
        my_prec = _OPERATOR_PRECEDENCE.get(expr.operator, 0)

        if isinstance(expr.left, BinaryOp):
            left_prec = _OPERATOR_PRECEDENCE.get(expr.left.operator, 0)
            if left_prec < my_prec:
                left = f"({left})"

        if isinstance(expr.right, BinaryOp):
            right_prec = _OPERATOR_PRECEDENCE.get(expr.right.operator, 0)
            if right_prec < my_prec:
                right = f"({right})"

        return f"{left} {expr.operator} {right}"

    def _format_interpolation(self, expr: StringInterpolation) -> str:
        """Format a string interpolation expression."""
        parts: list[str] = []
        for part in expr.parts:
            if isinstance(part, StringLiteral):
                parts.append(_escape_string(part.value))
            else:
                parts.append(f"{{{self._format_expression(part)}}}")
        return f'"{"".join(parts)}"'

    def _format_slice(self, expr: SliceAccess) -> str:
        """Format a slice access expression."""
        target = self._format_expression(expr.target)
        start = self._format_expression(expr.start) if expr.start else ""
        stop = self._format_expression(expr.stop) if expr.stop else ""
        if expr.step is not None:
            step = self._format_expression(expr.step)
            return f"{target}[{start}:{stop}:{step}]"
        return f"{target}[{start}:{stop}]"

    def _format_function_expression(self, expr: FunctionExpression) -> str:
        """Format an anonymous function expression."""
        params = self._format_params(expr.parameters)
        ret = f" -> {expr.return_type}" if expr.return_type else ""
        # Function expressions get their body formatted inline
        body_lines: list[str] = []
        saved_lines = self._lines
        saved_indent = self._indent
        self._lines = body_lines
        self._indent = 0
        self._format_block(expr.body)
        self._lines = saved_lines
        self._indent = saved_indent

        if not body_lines:
            return f"fn({params}){ret} {{}}"

        result = f"fn({params}){ret} {{\n"
        for line in body_lines:
            if line:
                result += f"{_INDENT * (self._indent + 1)}{line.lstrip()}\n"
            else:
                result += "\n"
        result += f"{_INDENT * self._indent}}}"
        return result
