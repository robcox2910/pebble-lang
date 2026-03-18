# REPL

The **REPL** (Read-Eval-Print Loop) is an interactive mode where you can type
Pebble code one line at a time and see results immediately. It's like having a
conversation with the language — you type something, it responds, and you can
keep going.

## Starting the REPL

Run `pebble` with no arguments:

```
$ pebble
pebble>
```

The `pebble>` prompt means the REPL is waiting for your input.

## Trying Things Out

Type any Pebble code and press Enter:

```
pebble> print(1 + 2)
3
pebble> print("Hello!")
Hello!
```

## Variables Stick Around

When you declare a variable, it stays available for future inputs:

```
pebble> let x = 42
pebble> let y = 8
pebble> print(x + y)
50
```

You can change variables too:

```
pebble> x = 100
pebble> print(x)
100
```

## Functions Persist Too

Define a function on one line, call it on the next:

```
pebble> fn double(n) { return n * 2 }
pebble> print(double(21))
42
```

## Multi-Line Input

When your code has a `{` that hasn't been closed yet, the REPL knows you're
not done and shows `...` to ask for more:

```
pebble> fn greet(name) {
...     print("Hello {name}!")
... }
pebble> greet("Alice")
Hello Alice!
```

The REPL counts opening `{` and closing `}` braces. It keeps reading lines
until they balance.

## Errors Don't Crash

If you make a mistake, the REPL shows an error message and lets you keep
going — it doesn't quit:

```
pebble> print(1 / 0)
Error: Division by zero
pebble> print("still working!")
still working!
```

Your previous variables and functions are still there after an error.

## Exiting

Press **Ctrl-D** (or **Ctrl-Z** on Windows) to exit the REPL.

## How It Works

Behind the scenes, the REPL maintains persistent state across inputs:

1. **Variables** — Every variable you declare is saved and available in future
   inputs.
2. **Functions** — Function definitions are kept in a registry so you can call
   them later.
3. **Analyzer scope** — The semantic analyzer remembers what names exist, so it
   can catch errors like "undeclared variable" correctly.

Each input goes through the same pipeline as a regular Pebble file:

```
Input → Lexer → Parser → Analyzer → Type Checker → Compiler → Optimizer → VM
```

The difference is that the VM starts each input with the variables from
previous successful inputs, and the function registry accumulates across
inputs.

```
Input 1: let x = 10
  → VM runs with {}          → saves {x: 10}

Input 2: print(x + 5)
  → VM runs with {x: 10}    → prints 15, saves {x: 10}

Input 3: x = 20
  → VM runs with {x: 10}    → saves {x: 20}
```
