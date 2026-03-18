# Linter

## What Is a Linter?

Imagine a teacher reading your essay. They don't just check if the sentences are grammatically correct -- they also make suggestions like "this paragraph is hard to follow" or "you used a word but never explained what it means." The essay still *works*, but the suggestions help make it *better*.

A **linter** is like that teacher for your code. It reads your program and points out things that aren't necessarily *wrong* (the program still runs!) but are probably mistakes or could be improved.

## Linter vs. Analyzer

Pebble already has a **semantic analyzer** that catches real errors -- using a variable you never declared, calling a function with the wrong number of arguments, or writing `return` outside a function. The analyzer finds things that would *break* your program.

The linter is different. It catches things that *probably* aren't what you meant:

| Tool | What it catches | Effect |
|------|----------------|--------|
| **Analyzer** | Real errors | Program won't run |
| **Linter** | Style issues & likely mistakes | Program runs, but something seems off |

## Using the Linter

```
pebble lint myfile.pbl
```

The linter prints warnings in a standard format and exits with code 1 if any warnings are found:

```
myfile.pbl:3:1: W001 Unused variable 'temp'
myfile.pbl:7:1: W004 Empty block
```

## Lint Rules

### W001 -- Unused Variable

If you declare a variable but never use it, that's suspicious. Maybe you made a typo, or maybe you forgot to finish some code.

```pebble
let x = 42      # W001: Unused variable 'x'
let y = 10
print(y)         # y is used, no warning
```

**Exceptions** (no warning):

- **Function parameters** -- It's normal to have unused parameters in callbacks or method overrides
- **Underscore-prefixed names** like `_temp` -- The `_` prefix is a convention meaning "I know I'm not using this"
- **Function/class/struct/enum names** -- Defining a function counts as "using" its name

### W002 -- Naming Conventions

Consistent naming makes code much easier to read. Pebble follows a common convention:

- **Variables and functions**: `snake_case` (lowercase with underscores)
- **Classes, structs, and enums**: `PascalCase` (each word capitalized)

```pebble
let myVariable = 1      # W002: should be my_variable
fn doSomething() { }    # W002: should be do_something
class my_class { }      # W002: should be MyClass
```

**Exceptions**:

- Names starting with `_` are not checked (they're private/intentional)
- Internal names starting with `$` (like `$anon_0` for anonymous functions) are skipped

### W003 -- Unreachable Code

If you write code after a `return`, `break`, `continue`, or `throw`, that code can never run. It's almost certainly a mistake.

```pebble
fn example() {
    return 42
    print("never runs")  # W003: Unreachable code
}
```

Note that `return` inside an `if` branch does **not** make the code after the `if` unreachable -- only one branch runs!

```pebble
fn example(x) {
    if x {
        return 1      # Only this branch returns early
    }
    return 2          # This is still reachable -- no warning
}
```

### W004 -- Empty Block

An empty block usually means you forgot to write the body:

```pebble
if condition {
    # W004: Empty block
}

fn placeholder() {
    # W004: Empty block
}
```

This catches empty `if`, `else`, `while`, `for`, `try`, `catch`, `finally`, and function bodies.

## How It Works

The linter uses the same **AST walking** technique as the semantic analyzer, but instead of raising errors, it collects warnings in a list.

For **W001 (unused variables)**, the linter uses a two-pass approach:

1. Walk the entire AST, recording every variable *declaration* (where it's created) and every variable *read* (where it's used)
2. After walking everything, check which declarations have no matching reads

This two-pass design means the linter correctly handles forward references -- using a variable before it's declared in the source order (which is possible inside functions).

For **W002 (naming)**, the linter checks names at their declaration site using regular expressions:

- `^_?[a-z][a-z0-9_]*$` for snake_case
- `^[A-Z][a-zA-Z0-9]*$` for PascalCase

For **W003 (unreachable code)**, the linter watches for "terminal" statements (`return`, `break`, `continue`, `throw`) inside a block. Any statement that comes after a terminal one gets flagged.

For **W004 (empty blocks)**, the linter simply checks `len(body) == 0` for every block-carrying node.

## Designing Good Lint Rules

Real-world linters like ESLint (JavaScript), Clippy (Rust), and Pylint (Python) have hundreds of rules. When designing a lint rule, you want to balance:

- **Usefulness** -- Does this rule catch real mistakes people make?
- **False positives** -- Will this rule warn about code that's actually fine?
- **Annoyance factor** -- Will programmers find this rule helpful or just noisy?

That's why our W001 rule doesn't warn about unused function parameters -- that would be annoying because unused parameters are extremely common and usually intentional. The `_` prefix convention gives programmers a way to say "I know this is unused" without triggering a warning.
