# Closures

A **closure** is a function that remembers variables from the place where it
was created, even after that place has finished running.

Think of it like a backpack: when a function is born inside another function,
it packs up any variables it needs from the outside and carries them along
wherever it goes.

## A Simple Example

```pebble
fn make_greeter(greeting) {
    fn greet(name) {
        print("{greeting}, {name}!")
    }
    return greet
}

let hello = make_greeter("Hello")
hello("Alice")    # prints: Hello, Alice!
hello("Bob")      # prints: Hello, Bob!
```

Here `greet` **captures** the `greeting` parameter from `make_greeter`. Even
after `make_greeter` finishes, the closure still has access to `greeting`.

## Closures Remember State

Closures don't just read captured variables — they can change them too. This
lets you create little "state machines" that remember things between calls:

```pebble
fn make_counter() {
    let count = 0
    fn increment() {
        count = count + 1
        return count
    }
    return increment
}

let counter = make_counter()
print(counter())   # prints: 1
print(counter())   # prints: 2
print(counter())   # prints: 3
```

Each time you call `counter()`, the captured `count` variable goes up by one.

The variable lives inside a special container called a **Cell**. Think of a
Cell like a shared whiteboard on a wall — both the outer function and the
closure can look at it and erase-and-rewrite the number on it. Because they
share the same whiteboard (not separate copies), changes made by one are
seen by the other.

## Independent Closures

Every time you call the outer function, you get a brand-new closure with its
own private copy of the captured variables:

```pebble
fn make_counter() {
    let count = 0
    fn increment() {
        count = count + 1
        return count
    }
    return increment
}

let a = make_counter()
let b = make_counter()
print(a())   # prints: 1
print(a())   # prints: 2
print(b())   # prints: 1  (b has its own count!)
```

Closures `a` and `b` each have their own `count` — changing one doesn't
affect the other.

## How It Works Under the Hood

When the compiler sees a function that uses a variable from an outer function,
it marks that variable as **captured**:

1. **Cell variables** — In the outer function, the captured variable is stored
   in a `Cell` (a small mutable box) instead of a regular variable slot.
2. **Free variables** — The inner function knows it needs to look in its Cell
   storage instead of its local variables.
3. **MAKE_CLOSURE** — When the inner function definition runs, the VM creates
   a `Closure` object that bundles the function's compiled code with references
   to the Cells from the outer function's frame.

```
Outer function's frame          Closure object
+-------------------+          +------------------+
| cells:            |   shared | code: inner's    |
|   count → Cell(0) | ←------→|   instructions   |
+-------------------+          | cells: [Cell(0)] |
                               +------------------+
```

Because the Cell is **shared** (not copied), when the closure mutates `count`,
the outer function sees the change too — and vice versa.

### New Opcodes

| Opcode | Operand | What it does |
|--------|---------|--------------|
| `STORE_CELL` | variable name | Pop the stack and store into a Cell |
| `LOAD_CELL` | variable name | Push a Cell's current value onto the stack |
| `MAKE_CLOSURE` | function name | Create a Closure from a function + captured Cells |

### The Analyzer's Job

The semantic analyzer detects captures during its walk of the AST. When it sees
a variable used inside a function but declared in a different (outer) function,
it records:

- The outer function has a **cell variable** (its local needs Cell storage).
- The inner function has a **free variable** (it captures from outside).

The compiler uses this information to decide whether to emit `STORE_NAME` /
`LOAD_NAME` (regular variables) or `STORE_CELL` / `LOAD_CELL` (captured
variables).

## Closures as Values

Closures are first-class values in Pebble — you can store them in variables,
return them from functions, and pass them as arguments.

```pebble
fn make_adder(n) {
    fn add(x) {
        return n + x
    }
    return add
}

let add5 = make_adder(5)
let add10 = make_adder(10)
print(add5(3))    # prints: 8
print(add10(3))   # prints: 13
print(type(add5)) # prints: fn
```

The `type()` function returns `"fn"` for closures, and printing a closure
shows `<fn name>`.

Closures work perfectly as callbacks for [higher-order
functions](higher-order.md) like `map`, `filter`, and `reduce`.
