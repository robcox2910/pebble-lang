# Pebble

An educational compiler and bytecode VM for the **Pebble** programming language.

Pebble is a small imperative language that compiles to bytecode and runs on a
custom stack-based virtual machine. The project is designed for learning how
compilers work, built incrementally using TDD.

## Language Features

- Integers, strings, booleans
- Variables (`let` declarations, reassignment)
- Arithmetic, comparison, and logical operators (`and`, `or`, `not`)
- Control flow: `if/else`, `while`, `for` loops
- Functions (`fn`, `return`)
- `print()` built-in
- Comments (`#`)
- Curly-brace blocks, newline-delimited statements (no semicolons)

**Coming soon:** VM execution

## Example

```
let count = 0
while count < 5 {
    if count > 0 {
        print(count)
    }
    count = count + 1
}
```

## Pipeline

```
Source -> Lexer -> Parser -> Analyzer -> Compiler -> [VM]
```

Stages in `[ ]` are planned but not yet implemented.

## Quick Start

```bash
# Install dependencies
uv sync --all-extras

# Run tests
uv run pytest

# Lint and type check
uv run ruff check .
uv run pyright src tests
```

## Documentation

Full docs at [robcox2910.github.io/pebble-lang](https://robcox2910.github.io/pebble-lang/)

## License

MIT
