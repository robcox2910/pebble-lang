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
Source -> Lexer -> Parser -> Analyzer -> Compiler -> VM
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
