# Pebble

An educational compiler and bytecode VM for the **Pebble** programming language.

Pebble is a small imperative language that compiles to bytecode and runs on a
custom stack-based virtual machine. The project is designed for learning how
compilers work, built incrementally using TDD.

## Language Features

- Integers, strings, booleans
- Variables (`let` declarations, reassignment)
- Arithmetic and comparison operators
- Control flow: `if/else`, `while`, `for`
- Functions with `return`
- `print()` built-in
- Comments (`#`)
- Curly-brace blocks, newline-delimited statements (no semicolons)

## Example

```
# Fibonacci sequence
fn fib(n) {
    if n < 2 {
        return n
    }
    return fib(n - 1) + fib(n - 2)
}

let i = 0
while i < 10 {
    print(fib(i))
    i = i + 1
}
```

## Pipeline

```
Source -> Lexer -> Parser -> Analyzer -> Code Generator -> VM
```

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
