# Pebble

An educational compiler and bytecode VM for the **Pebble** programming language.

Pebble is a small imperative language that compiles to bytecode and runs on a
custom stack-based virtual machine. The project is designed for learning how
compilers work, built incrementally using TDD.

## Language Features

- Integers, floats, strings, booleans
- Variables (`let` declarations, `const`, reassignment)
- Arithmetic, comparison, bitwise, and logical operators (`and`, `or`, `not`)
- Short-circuiting `and` / `or` and chained comparisons (`1 < x < 10`)
- Control flow: `if/else`, `while`, `for` loops, `match`
- Collections: lists, dicts, list comprehensions, slicing, tuple unpacking
- Functions (`fn`, `return`), default arguments, closures, and generators (`yield`)
- Async / await (`async fn`, `await`)
- Structs, classes with inheritance, and enums
- Error handling: `try` / `catch` / `finally` and `throw`
- Modules and imports (`import`, `from ... import`)
- String interpolation (`"hello {name}"`)
- `print()` built-in
- Comments (`#`)
- Curly-brace blocks, newline-delimited statements (no semicolons)

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
Source -> Lexer -> Parser -> Analyzer -> Module Resolver -> Type Checker -> Compiler -> Optimizer -> VM
```

See the [documentation](https://robcox2910.github.io/pebble-lang/) for a
kid-friendly walk-through of each stage.

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

## Related Projects

Pebble is part of an educational series where every layer of the
computing stack is built from scratch:

| Project | What It Teaches |
|---------|----------------|
| [PyOS](https://github.com/robcox2910/py-os) | Operating systems |
| [PyDB](https://github.com/robcox2910/pydb) | Relational databases |
| [PyStack](https://github.com/robcox2910/pystack) | Full-stack integration |
| [PyWeb](https://github.com/robcox2910/pyweb) | HTTP web servers |
| [PyGit](https://github.com/robcox2910/pygit) | Version control |
| [PyCrypt](https://github.com/robcox2910/pycrypt) | Cryptography |
| [PyNet](https://github.com/robcox2910/pynet) | Networking |
| [PySearch](https://github.com/robcox2910/pysearch) | Full-text search |
| [PyMQ](https://github.com/robcox2910/pymq) | Message queues |

All projects use TDD, comprehensive documentation with real-world
analogies, and are designed for learners aged 12+.

## License

MIT
