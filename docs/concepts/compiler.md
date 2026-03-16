# Compiler

The **compiler** is the part of Pebble that takes your program — after the
lexer, parser, and analyzer have all done their jobs — and turns it into
**bytecode**: a list of simple, numbered instructions that a machine can
follow step by step.

## What Does a Compiler Do?

Think of writing a recipe for a friend. Your original recipe might say:

> "If you have eggs, make an omelette. Otherwise, make toast."

That's easy for a human to read, but a very simple robot wouldn't
understand it. The compiler's job is to rewrite your recipe as a
numbered list of tiny steps:

```
0. Look up whether you have eggs.
1. If no, skip to step 5.
2. Crack the eggs.
3. Cook the omelette.
4. Skip to step 7.
5. Get the bread.
6. Make toast.
7. Done!
```

The compiler does exactly this — it walks through your program's AST (the
tree the parser built) and produces a flat list of instructions the VM can
execute one at a time.

## Key Ideas

### The Stack

The VM uses a **stack** to do its work. A stack is like a pile of plates:
you can only put a plate on **top** or take the **top** plate off. You
can't reach into the middle.

When the compiler says "load the number 42", that means "put 42 on top of
the stack". When it says "add", that means "take the top two plates off,
add them together, and put the result back on top".

```
LOAD_CONST 0    # push 3 onto the stack        → [3]
LOAD_CONST 1    # push 5 onto the stack        → [3, 5]
ADD             # pop 3 and 5, push 8          → [8]
```

### The Constant Pool

Instead of writing the actual value `42` inside every instruction, the
compiler keeps a numbered list called the **constant pool**. The
instruction just says "load constant number 0", and the VM looks up what
constant number 0 is.

This is like a recipe that says "use ingredient #3" instead of writing
"flour" every single time. It saves space and avoids repetition.

```
Constants: [42, "hello", true]
                                   ↑
LOAD_CONST 0   → pushes 42        |
LOAD_CONST 1   → pushes "hello"   |
LOAD_CONST 2   → pushes true ─────┘
```

If the same value appears twice in your program, the compiler is smart
enough to reuse the same constant pool entry instead of adding a
duplicate.

### Jump Instructions

Normal instructions run in order: 0, 1, 2, 3, and so on. But `if`
statements and loops need to **skip ahead** or **go back**. That's what
**jump** instructions do.

- `JUMP 7` means "go directly to instruction 7"
- `JUMP_IF_FALSE 5` means "if the top of the stack is false, skip to
  instruction 5"

### Backpatching

Here's a tricky problem: when the compiler starts writing an `if`
statement, it doesn't yet know *how many* instructions the body will
have. So it can't fill in the jump target right away.

The solution is called **backpatching**:

1. Write `JUMP_IF_FALSE ???` with a placeholder
2. Compile the body
3. Now you know where the body ends — go back and fill in the `???`

It's like writing "skip to step ?" in your recipe, finishing the rest,
and then going back to fill in the actual step number.

### CodeObject

Each function gets its own **CodeObject** — a separate instruction list
and constant pool. Think of it as giving each recipe its own instruction
sheet. The main program is also a CodeObject.

When you call a function, the VM switches to that function's instruction
sheet, runs it, and then comes back to where it left off.

### CALL and RETURN

- `CALL "add"` tells the VM: "go follow the instruction sheet for `add`"
- `RETURN` tells the VM: "I'm done with this sheet, go back to where you
  were before"

If a function doesn't have an explicit `return`, the compiler
automatically adds `return null` at the end — every function must hand back
*something*, even if it's nothing.

## Compilation Patterns

### Variables

```pebble
let x = 42
```

Compiles to:

```
LOAD_CONST 0     # push 42
STORE_NAME "x"   # pop and save as x
```

### Print

```pebble
print(x)
```

Compiles to:

```
LOAD_NAME "x"    # push the value of x
PRINT            # pop and print it
```

### If/Else

```pebble
if x > 10 {
    print(x)
} else {
    print(0)
}
```

Compiles to:

```
0  LOAD_NAME "x"
1  LOAD_CONST 0        # 10
2  GREATER_THAN
3  JUMP_IF_FALSE 7     # skip to else
4  LOAD_NAME "x"
5  PRINT
6  JUMP 9              # skip past else
7  LOAD_CONST 1        # 0
8  PRINT
9  HALT
```

### Else If

An `else if` chain compiles to exactly the same bytecode as manually
nested `if`/`else` blocks — because that's what the parser turns it into
before the compiler ever sees it.

```pebble
if true {
    print(1)
} else if false {
    print(2)
} else {
    print(3)
}
```

Compiles to:

```
0   LOAD_CONST 0        # true
1   JUMP_IF_FALSE 5     # skip to inner if
2   LOAD_CONST 1        # 1
3   PRINT
4   JUMP 11             # skip past everything
5   LOAD_CONST 2        # false
6   JUMP_IF_FALSE 10    # skip to else
7   LOAD_CONST 3        # 2
8   PRINT
9   JUMP 11             # skip past else
10  LOAD_CONST 4        # 3
11  PRINT
12  HALT
```

Each `else if` introduces another `JUMP_IF_FALSE` / `JUMP` pair — the
same pattern as a plain `if`/`else`, just repeated.

### While Loop

```pebble
let x = 0
while x < 3 {
    x = x + 1
}
```

Compiles to:

```
0  LOAD_CONST 0        # 0
1  STORE_NAME "x"
2  LOAD_NAME "x"       ← loop starts here
3  LOAD_CONST 1        # 3
4  LESS_THAN
5  JUMP_IF_FALSE 11    # exit loop
6  LOAD_NAME "x"
7  LOAD_CONST 2        # 1
8  ADD
9  STORE_NAME "x"
10 JUMP 2              ← go back to the start
11 HALT
```

### For Loop

A `for` loop like `for i in range(3) { ... }` is actually rewritten as a
`while` loop behind the scenes. The compiler creates a hidden variable
(with a `$` prefix so it can't clash with your variable names) to store
the limit:

```
$for_limit_0 = 3   # hidden limit
i = 0               # start at zero
while i < $for_limit_0 {
    ... body ...
    i = i + 1       # increment
}
```

### Break and Continue

`break` and `continue` are compiled using the same `JUMP` instruction --
no new opcodes needed! The trick is knowing *where* to jump.

**Break** exits the loop, so it jumps to the instruction *after* the loop.
**Continue** skips to the next iteration:

- In a `while` loop, `continue` jumps back to the **condition check**
- In a `for` loop, `continue` jumps to the **increment** section
  (so the loop variable still gets updated)

The compiler uses **backpatching** for both (remember the "skip to step ?"
trick from the [Backpatching](#backpatching) section above). When it sees
`break` or `continue`, it emits `JUMP 0` with a placeholder target. After
the loop is fully compiled, it goes back and fills in the real target.

```
WHILE with break/continue:

0  [condition]               ← continue jumps here
1  JUMP_IF_FALSE exit
2  [body]
3  JUMP 0 (break → exit)    ← break emits this
4  JUMP 0 (continue → 0)    ← continue emits this
5  JUMP 0                    ← back to condition
exit:                        ← break targets here
```

```
FOR with break/continue:

0  [init limit + variable]
4  [condition: var < limit]  ← loop start
7  JUMP_IF_FALSE exit
8  [body]
   JUMP 0 (continue → inc)  ← continue emits this
   JUMP 0 (break → exit)    ← break emits this
inc:                         ← continue targets here
   [var = var + 1]
   JUMP 4                   ← back to condition
exit:                        ← break targets here
```

The compiler keeps a **stack of loop contexts** so that nested loops
work correctly -- `break` in an inner loop only exits that inner loop,
not the outer one.

### Functions

```pebble
fn add(a, b) {
    return a + b
}
```

Creates a separate CodeObject named `"add"`:

```
LOAD_NAME "a"
LOAD_NAME "b"
ADD
RETURN
```

The main program doesn't contain any of the function's instructions — it
just knows the function exists so it can `CALL` it later.

## The Full OpCode Set

| OpCode | Operand | What it does |
|--------|---------|--------------|
| `LOAD_CONST` | index | Push a constant onto the stack |
| `STORE_NAME` | name | Pop the top value and save it as a variable |
| `LOAD_NAME` | name | Push a variable's value onto the stack |
| `ADD` | — | Pop two values, push their sum |
| `SUBTRACT` | — | Pop two values, push the difference |
| `MULTIPLY` | — | Pop two values, push the product |
| `DIVIDE` | — | Pop two values, push the quotient (always a float) |
| `FLOOR_DIVIDE` | — | Pop two values, push the floored quotient |
| `MODULO` | — | Pop two values, push the remainder |
| `POWER` | — | Pop two values, push left raised to right |
| `NEGATE` | — | Pop a value, push its negation |
| `NOT` | — | Pop a value, push its logical NOT |
| `BIT_AND` | — | Pop two ints, push bitwise AND |
| `BIT_OR` | — | Pop two ints, push bitwise OR |
| `BIT_XOR` | — | Pop two ints, push bitwise XOR |
| `BIT_NOT` | — | Pop an int, push bitwise NOT |
| `LEFT_SHIFT` | — | Pop two ints, push left shifted by right |
| `RIGHT_SHIFT` | — | Pop two ints, push left shifted right by right |
| `EQUAL` | — | Pop two values, push whether they're equal |
| `NOT_EQUAL` | — | Pop two values, push whether they differ |
| `LESS_THAN` | — | Pop two values, push whether left < right |
| `LESS_EQUAL` | — | Pop two values, push whether left <= right |
| `GREATER_THAN` | — | Pop two values, push whether left > right |
| `GREATER_EQUAL` | — | Pop two values, push whether left >= right |
| `AND` | — | Pop two values, push logical AND |
| `OR` | — | Pop two values, push logical OR |
| `JUMP` | target | Jump to a specific instruction |
| `JUMP_IF_FALSE` | target | Jump if the top of the stack is false |
| `POP` | — | Discard the top value on the stack |
| `CALL` | name | Call a function by name |
| `RETURN` | — | Return from a function |
| `BUILD_STRING` | count | Pop *count* values, convert to text, join them |
| `BUILD_LIST` | count | Pop *count* values and create a list |
| `LIST_APPEND` | name | Pop a value and append it to the named list variable |
| `BUILD_DICT` | count | Pop *count* key-value pairs and create a dict |
| `INDEX_GET` | — | Pop an index and a target (list or dict), push the element |
| `INDEX_SET` | — | Pop value, index, target; change the element (dict upserts) |
| `CALL_METHOD` | name | Call a built-in method on the top-of-stack value |
| `CALL_INSTANCE_METHOD` | name:count | Call a class method with *count* extra args |
| `SLICE_GET` | — | Pop step, stop, start, target; push sliced result |
| `SETUP_TRY` | target | Push an exception handler pointing at *target* |
| `POP_TRY` | — | Remove the top exception handler |
| `THROW` | — | Pop a value and raise it as an exception |
| `MAKE_CLOSURE` | name | Create a closure from a function + captured Cells |
| `LOAD_CELL` | name | Push a captured variable's value |
| `STORE_CELL` | name | Pop and store into a captured variable |
| `UNPACK_SEQUENCE` | count | Pop a list, push each of its *count* elements |
| `CHECK_TYPE` | type | Pop a value and error if it doesn't match the type |
| `GET_FIELD` | name | Pop a struct instance, push the named field's value |
| `SET_FIELD` | name | Pop value and struct instance, set the named field |
| `PRINT` | — | Pop and print the top value |
| `HALT` | — | Stop the program |
