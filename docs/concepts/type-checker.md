# Type Checker

The **type checker** is a new step in the Pebble pipeline that catches
type mistakes *before* your program runs. Think of it as a
spell-checker for types — it reads through your code and flags obvious
problems so you can fix them right away.

## The Spell-Checker for Types

Imagine you are writing a letter. A spell-checker underlines misspelled
words *while you type*, before you print the letter. You do not have to
print it, read it, and then notice the mistake.

The type checker does the same thing for types. If you write:

```pebble
let x: Int = "hello"
```

The type checker sees: "You promised `x` would be an `Int`, but you
gave it a `String`." It raises an error immediately — before the
program even starts running.

## Static vs Dynamic Checking

Pebble now has **two** layers of type checking:

| Layer | When it runs | What it catches |
|-------|-------------|----------------|
| **Static** (type checker) | Before the program runs | Obvious mismatches the checker can figure out by reading the code |
| **Dynamic** (runtime) | While the program runs | Everything else — values from `input()`, complex logic, etc. |

Think of it like boarding a plane:

- **Static checking** is showing your ticket at the gate — they verify
  your name matches *before* you sit down.
- **Dynamic checking** is the flight attendant checking seat numbers
  *after* you board — they catch anything the gate missed.

Both layers work together. The static checker catches the easy mistakes
early, and the runtime checks remain as a safety net for everything
else.

## What the Type Checker Does

The type checker walks through your code and checks four things:

### 1. Annotated Assignments

When you add a type annotation to a variable, the checker verifies the
value matches:

```pebble
let x: Int = 42        # passes — 42 is an Int
let y: String = 42     # fails — 42 is not a String
let z = 42             # passes — no annotation, no check
```

### 2. Function Arguments

When you call a function with typed parameters, the checker verifies
each argument:

```pebble
fn add(a: Int, b: Int) -> Int {
    return a + b
}
add(1, 2)          # passes — both are Int
add("hi", 2)       # fails — "hi" is not an Int
```

### 3. Function Returns

When a function declares a return type, the checker verifies the
`return` value:

```pebble
fn greet() -> String {
    return "hello"     # passes — "hello" is a String
}

fn broken() -> Int {
    return "oops"      # fails — "oops" is not an Int
}
```

### 4. Struct Construction

When a struct has typed fields, the checker verifies each argument to
the constructor:

```pebble
struct Point { x: Float, y: Float }
Point(1.0, 2.0)       # passes — both are Float
Point(1, 2.0)          # fails — 1 is not a Float
```

## Type Inference

The type checker does not just look at annotations — it also *figures
out* what type each expression produces. This is called **type
inference**.

```pebble
let x = 42             # inferred as Int
let y = x + 1          # inferred as Int (Int + Int = Int)
let z: Int = y         # passes — y is Int
```

Here is how the checker infers types for different expressions:

| Expression | Inferred type |
|-----------|--------------|
| `42` | `Int` |
| `3.14` | `Float` |
| `"hello"` | `String` |
| `true` / `false` | `Bool` |
| `null` | `Null` |
| `1 + 2` | `Int` (both Int → Int) |
| `1 + 2.0` | `Float` (Int + Float → Float) |
| `"a" + "b"` | `String` |
| `10 / 3` | `Float` (division always returns Float) |
| `1 < 2` | `Bool` (comparisons return Bool) |
| `not true` | `Bool` |
| `[1, 2, 3]` | `List` |
| `{"a": 1}` | `Dict` |
| `fn(x) { ... }` | `Fn` |
| `Point(1.0, 2.0)` | `Point` (struct type) |

## Gradual Typing

Pebble uses **gradual typing** — you choose how much type information
to add. Code without annotations is completely fine:

```pebble
let x = 5              # no annotation — no checking
fn add(a, b) {         # no parameter types — no checking
    return a + b
}
```

Under the hood, unannotated values are assigned a special type called
`Unknown`. The rule is simple: **`Unknown` is compatible with
everything.** If the checker cannot figure out a type, it does not
complain — it leaves the check to the runtime.

This means you can gradually add types to your code. Start with no
annotations, then add them where you want extra safety.

## The Two Safety Nets

The static type checker and the runtime type checker are like two
safety nets at different heights:

```
┌─────────────────────────────────┐
│         Your Program            │
├─────────────────────────────────┤
│  Static Type Checker (early)    │  ← catches obvious mismatches
├─────────────────────────────────┤
│  Compiler + Optimizer           │
├─────────────────────────────────┤
│  Runtime Type Checker (late)    │  ← catches dynamic mismatches
├─────────────────────────────────┤
│          VM Output              │
└─────────────────────────────────┘
```

The static checker catches what it can see by reading the code. The
runtime checker catches everything else — values computed at runtime,
user input, catch variables, and complex control flow.

## How It Works Under the Hood

### The Pipeline

The type checker sits between the analyzer and the compiler:

```
Source → Lexer → Parser → Analyzer → Type Checker → Compiler → Optimizer → VM
```

It receives the analyzed AST and walks every statement, inferring types
for expressions and checking them against annotations.

### Two-Pass Walk

The type checker makes two passes over the program:

1. **Signature collection** — scan all function definitions, structs,
   and classes to learn their parameter types and return types. This
   handles forward references (calling a function before it is
   defined).

2. **Type checking** — walk every statement, infer expression types,
   and check annotations.

### Scoped Type Environment

The checker tracks variable types in a scoped environment (just like
the analyzer tracks variable declarations). Each function, loop, or
block gets its own scope:

```pebble
let x: Int = 5         # x is Int in the outer scope
fn f() {
    let x: String = "hi"  # x is String inside f
}
```

## Summary

- The **type checker** catches type mismatches *before* your program
  runs — like a spell-checker for types
- It checks **assignments**, **function arguments**, **return values**,
  and **struct construction**
- It uses **type inference** to figure out expression types
  automatically
- **Gradual typing** means unannotated code is left alone — `Unknown`
  is compatible with everything
- The **runtime checks** remain as a safety net for dynamic values
- The checker uses a **two-pass walk** to handle forward references
