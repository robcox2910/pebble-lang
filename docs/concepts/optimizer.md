# Optimizer

The **optimizer** is an extra step in the Pebble pipeline. After the
compiler has turned your program into bytecode, the optimizer looks at
those instructions and tidies them up — making them shorter and faster
without changing what the program does.

## What Is an Optimizer?

Imagine you wrote a recipe:

> Step 4: Measure 100 g of flour.
> Step 5: Measure another 100 g of flour.
> Step 6: Mix the two piles together.

A smart cook would notice: "Why not just measure 200 g of flour and
skip straight to mixing?" That is **optimization** — getting the same
result with fewer steps.

In a compiler, the "recipe steps" are bytecode instructions. The
optimizer reads them and replaces patterns that do unnecessary work.

## Constant Folding

**Constant folding** replaces arithmetic on values that are already
known at compile time.

When you write:

```pebble
print(1 + 2)
```

The compiler turns that into three instructions:

```
LOAD_CONST 0    # push 1
LOAD_CONST 1    # push 2
ADD             # pop both, push 3
```

But the optimizer notices: "Both operands are constants — I can
calculate the answer right now!" It replaces those three instructions
with just one:

```
LOAD_CONST 2    # push 3 (pre-computed)
```

### What Gets Folded?

The optimizer folds all the operations it can compute safely:

| Category      | Operations                     |
|--------------|-------------------------------|
| Arithmetic   | `+` `-` `*` `/` `//` `%` `**` |
| Comparisons  | `==` `!=` `<` `<=` `>` `>=`   |
| Logical      | `and` `or` `not`               |
| Bitwise      | `&` `\|` `^` `~` `<<` `>>`    |
| Unary        | `-` (negate) `not` `~`         |
| Strings      | `"hello" + " world"`           |

### Cascading Folds

Longer expressions get folded in multiple rounds. Take `1 + 2 + 3`:

```
Round 1:  LOAD_CONST 1, LOAD_CONST 2, ADD  →  LOAD_CONST 3
          Now we have: LOAD_CONST 3, LOAD_CONST 3, ADD

Round 2:  LOAD_CONST 3, LOAD_CONST 3, ADD  →  LOAD_CONST 6
```

The optimizer loops until nothing changes, so even long chains of
constants collapse into a single instruction.

### Safety Rules

The optimizer is careful **not** to fold things that might cause
errors:

- **Division by zero** — `10 / 0` is kept as-is so the VM can report
  the error at runtime with the correct line number
- **Negative shifts** — `1 << -1` is kept for the same reason
- **Booleans in arithmetic** — Pebble doesn't treat `true` as the
  number 1, so `-true` is left alone
- **Jump boundaries** — if another instruction might jump into the
  middle of a foldable sequence, the fold is skipped (see below)

## Dead Code Elimination

**Dead code elimination** (DCE) removes instructions that can never
run. If the program can never reach a line, there is no point keeping
it in the bytecode.

### How It Works

After a `return`, an unconditional `jump`, or `halt`, the instructions
that follow are **dead** — normal execution will never reach them.

```pebble
fn greet() {
    return "hello"
    print("this never runs")   # dead code!
}
```

The compiler emits instructions for the `print` call, but the
optimizer removes them because the `return` already ended the function.

### Jump Targets Stay Alive

There is one important exception: if another instruction **jumps to**
a line after a `return`, that line is still reachable.

```
0  LOAD_CONST 0
1  JUMP_IF_FALSE 4    ← might jump to index 4
2  LOAD_CONST 1
3  RETURN
4  LOAD_CONST 2       ← jump target — still alive!
5  RETURN
```

The optimizer keeps index 4 and 5 because `JUMP_IF_FALSE` at index 1
can land there.

### Conditional Jumps

A `JUMP_IF_FALSE` does **not** make the next instruction dead. The
fall-through path is still valid when the condition is true:

```
0  LOAD_CONST 0
1  JUMP_IF_FALSE 4
2  LOAD_CONST 1       ← still alive (condition was true)
3  PRINT
4  HALT
```

Only truly **unconditional** terminators (`RETURN`, `JUMP`, `HALT`)
start a dead region.

## How It Works Under the Hood

### The Pipeline

The optimizer sits between the compiler and the VM:

```
Source → Lexer → Parser → Analyzer → Type Checker → Compiler → Optimizer → VM
```

It receives a `CompiledProgram` and returns a new `CompiledProgram`
with optimized instructions. Every `CodeObject` (the main program
**and** each function) is optimized independently.

### Jump Adjustment

When folding replaces three instructions with one, every instruction
after the fold shifts to a lower index. Jump targets that pointed at
those later instructions now point to the wrong place.

The optimizer tracks where each old instruction ended up and rewrites
every jump operand to match the new positions. The same adjustment
happens after dead code elimination removes instructions.

### Peephole Window

The optimizer uses a technique called **peephole optimization**. It
slides a small window (2–3 instructions) across the bytecode, looking
for patterns it can simplify. It is like proofreading a recipe one
sentence at a time instead of rewriting the whole thing from scratch.

## Summary

- The **optimizer** improves bytecode after compilation, before the VM
  runs it
- **Constant folding** pre-computes arithmetic on known values, turning
  three instructions into one
- **Dead code elimination** removes instructions that can never execute
- Jump targets are carefully adjusted when instructions are removed
- The optimizer loops until no more improvements are possible
- Safety rules prevent folding operations that would hide runtime
  errors
