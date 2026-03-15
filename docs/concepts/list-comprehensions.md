# List Comprehensions

## The Assembly Line

Imagine a factory assembly line. Raw parts come in on a conveyor belt,
each part gets transformed by a machine, and the finished items drop into
a box at the end. Some factories also have an **inspector** who checks
each part before it reaches the machine -- parts that fail the check get
tossed out.

A list comprehension works the same way:

1. **Conveyor belt** -- `range()` feeds in the raw numbers.
2. **Machine** -- an expression transforms each number.
3. **Inspector** (optional) -- a condition decides which numbers get
   through.
4. **Box** -- the result is a brand-new list.

## Basic Syntax

```pebble
[expression for variable in range(...)]
```

This reads almost like English: *"give me `expression` **for** each
`variable` **in** `range(...)`"*.

```pebble
let nums = [x for x in range(5)]
print(nums)   # prints: [0, 1, 2, 3, 4]
```

Here the "machine" just passes each value through unchanged.

## Transforming Values

Put any expression before `for` to transform each value:

```pebble
let doubled = [x * 2 for x in range(5)]
print(doubled)   # prints: [0, 2, 4, 6, 8]
```

```pebble
let squares = [x * x for x in range(6)]
print(squares)   # prints: [0, 1, 4, 9, 16, 25]
```

## Adding a Filter

Add `if condition` after the iterable to keep only values that pass the
test:

```pebble
[expression for variable in range(...) if condition]
```

```pebble
let big = [x for x in range(10) if x > 5]
print(big)   # prints: [6, 7, 8, 9]
```

Combine transformation **and** filtering:

```pebble
let big_squares = [x * x for x in range(6) if x > 2]
print(big_squares)   # prints: [9, 16, 25]
```

## Practical Examples

### Even numbers

```pebble
let evens = [x for x in range(10) if x % 2 == 0]
print(evens)   # prints: [0, 2, 4, 6, 8]
```

### Countdown

```pebble
let countdown = [10 - i for i in range(5)]
print(countdown)   # prints: [10, 9, 8, 7, 6]
```

### Using range with two or three arguments

All three `range()` forms work inside comprehensions:

```pebble
print([x for x in range(2, 5)])       # prints: [2, 3, 4]
print([x for x in range(0, 10, 3)])   # prints: [0, 3, 6, 9]
```

## Comprehension vs. For Loop

A list comprehension is a short way to write a common pattern. These
two snippets do the same thing:

**For loop:**

```pebble
let result = []
for x in range(5) {
    if x > 2 {
        result.push(x * x)
    }
}
print(result)   # prints: [9, 16, 25]
```

**Comprehension:**

```pebble
let result = [x * x for x in range(5) if x > 2]
print(result)   # prints: [9, 16, 25]
```

The comprehension packs the same idea into a single line.

## Rules

- The iterable must be a `range()` call (1, 2, or 3 arguments).
- The loop variable is **scoped** to the comprehension -- it does not
  leak into the surrounding code.
- The result is always a brand-new list.
- You can use comprehensions anywhere an expression is allowed --
  inside `print()`, as a function argument, assigned to a variable, etc.

## How It Works Under the Hood

When the **compiler** sees `[x * 2 for x in range(5)]`, it emits
roughly this sequence:

1. `BUILD_LIST 0` -- create an empty list.
2. Store the list in a hidden variable (like `$comp_0`).
3. Set up the loop (same way `for` loops work).
4. For each iteration:
    - If there's a filter, check the condition. Skip this iteration
      if it's false.
    - Evaluate the mapping expression.
    - `LIST_APPEND "$comp_0"` -- pop the value and append it to the
      hidden list.
5. After the loop, load `$comp_0` back onto the stack.

The `LIST_APPEND` instruction is the only new opcode. Everything else
reuses the existing `for`-loop machinery.

## Summary

| Part                | Example              | What it does                    |
| ------------------- | -------------------- | ------------------------------- |
| Mapping expression  | `x * 2`              | Transform each value            |
| `for var in range()` | `for x in range(5)` | Produce raw values              |
| `if condition`      | `if x > 2`           | Keep only matching values       |
| Result              | `[...]`              | A new list of transformed items |
