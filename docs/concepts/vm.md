# Virtual Machine

The **virtual machine** (VM) is the part of Pebble that actually *runs*
your program. The compiler turned your code into a list of numbered
instructions. The VM reads those instructions one by one and does what
they say.

## What Is a Virtual Machine?

Imagine a robot sitting at a desk. On the desk is:

- **An instruction sheet** — the numbered list the compiler made
- **A finger** pointing to the current step (the *instruction pointer*)
- **A pile of plates** where it can stack numbers (the *value stack*)

The robot reads the step its finger is on, does it, moves its finger to
the next step, and repeats. When it reaches `HALT`, it stops.

```
Instruction pointer
     ↓
 0:  LOAD_CONST 0     # push 3 onto the stack
 1:  LOAD_CONST 1     # push 5 onto the stack
 2:  ADD              # pop 3 and 5, push 8
 3:  PRINT            # pop 8 and print it
 4:  HALT             # stop
```

## The Value Stack

The stack is a pile of plates. You can only touch the **top**:

- **Push** = put a plate on top
- **Pop** = take the top plate off

```
LOAD_CONST 0 (= 3)     →  [3]
LOAD_CONST 1 (= 5)     →  [3, 5]
ADD                     →  [8]         ← popped 3 and 5, pushed 8
PRINT                   →  []          ← popped 8, printed "8"
```

This is called **LIFO**: Last In, First Out. The last plate you put on
is the first one you take off — just like a real pile of plates.

## Frames: Bookmarks for Function Calls

When the VM calls a function, it needs to remember where it was in the
main program so it can come back later. It does this with **frames**.

A **frame** is like a bookmark. It remembers:

- Which instruction sheet you were following (the function's `CodeObject`)
- Which step you were on (the instruction pointer)
- Your local variables

### How CALL works

When the VM sees `CALL "add"`:

1. It looks up the function `"add"` and finds its instruction sheet
2. It pops the arguments from the stack and pairs them with parameter names
3. It creates a new frame (a new bookmark) for the function
4. It puts the new frame on top of a *frame stack* (a pile of bookmarks!)
5. It starts following the function's instructions

### How RETURN works

When the VM sees `RETURN`:

1. It pops the return value from the stack
2. It removes the current frame (throws away the bookmark)
3. It pushes the return value back onto the stack
4. It's now back in the calling function's frame — right where it left off

Think of it like asking a friend for help:

> "Hey, can you add 3 and 5 for me?"
>
> Your friend goes away, works it out, comes back and says "8".
>
> You write down 8 and carry on with your own recipe.

## How Variables Work

Each frame has its own set of variables — a private notebook. When the
VM sees `STORE_NAME "x"`, it writes the value in the current frame's
notebook. When it sees `LOAD_NAME "x"`, it reads from the current
frame's notebook.

Because each frame has its *own* notebook, a variable called `x` inside
one function doesn't interfere with a variable called `x` in another
function. They're on separate pages.

## Print Formatting

Pebble has its own rules for printing values:

| Pebble value | What gets printed |
|--------------|-------------------|
| `42` | `42` |
| `3.14` | `3.14` |
| `"hello"` | `hello` (no quotes) |
| `true` | `true` (lowercase) |
| `false` | `false` (lowercase) |
| `null` | `null` |
| `[1, 2, 3]` | `[1, 2, 3]` |
| `{"a": 1}` | `{a: 1}` |
| a closure | `<fn name>` |
| a struct instance | `Point(x=10, y=20)` |
| an enum variant | `Color.Red` |
| a generator | `<generator name>` |

This is different from Python, which would print `True` and `False`
with capital letters.

## Runtime Errors

Some problems can't be caught until the program is actually running.
These are called **runtime errors**:

| Problem | Error message |
|---------|---------------|
| `1 / 0` | Division by zero |
| `1 % 0` | Division by zero |
| `"hi" - 1` | Unsupported operand types for -: str and int |
| `-"hi"` | Unsupported operand type for negation: str |
| `xs[99]` (list) | Index 99 out of bounds for list of length 3 |
| `d["missing"]` (dict) | Key 'missing' not found in dict |
| `d[42] = 1` (dict) | Dict keys must be strings, got int |

When a runtime error happens, the VM stops and reports what went wrong.

## Class Method Calls

When you call a method on a class instance (like `dog.bark()`), the
VM uses a special opcode called `CALL_INSTANCE_METHOD`. It works like
`CALL` but with an extra step: it automatically passes the instance
as the `self` parameter.

```
LOAD_NAME "dog"
CALL_INSTANCE_METHOD "bark:0"
```

The operand `"bark:0"` encodes the method name and the number of extra
arguments (not counting `self`). The VM pops the arguments, pops the
target instance, looks up the mangled function name (`"Dog.bark"`),
binds `self` to the instance, and pushes a new frame.

See [Classes](classes.md) for the full story.

## Putting It All Together

Here's what happens when you run `pebble hello.pbl`:

```
hello.pbl → Lexer → Parser → Analyzer → Compiler → VM → output
```

1. The **lexer** breaks the source into tokens
2. The **parser** builds a tree (AST)
3. The **analyzer** checks for mistakes
4. The **compiler** turns the tree into bytecode instructions
5. The **VM** follows those instructions and produces output

## A Complete Example

```pebble
fn double(n) {
    return n * 2
}
print(double(5))
```

The compiler produces:

**Main instructions:**

```
0  LOAD_CONST 0     # push 5
1  CALL "double"    # call the function
2  PRINT            # print the result
3  HALT
```

**double instructions:**

```
0  LOAD_NAME "n"    # push the parameter
1  LOAD_CONST 0     # push 2
2  MULTIPLY         # n * 2
3  RETURN           # hand back the result
```

The VM runs it like this:

1. Push `5` → stack: `[5]`
2. CALL `"double"` → new frame, `n = 5`, stack: `[]`
3. Push `n` (which is `5`) → stack: `[5]`
4. Push `2` → stack: `[5, 2]`
5. MULTIPLY → stack: `[10]`
6. RETURN → pop frame, push `10` → stack: `[10]`
7. PRINT → pop and print `10`
8. HALT → done!

Output: `10`
