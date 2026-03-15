# Tuple Unpacking

## The Gift Box with Multiple Items

Imagine getting a gift box that holds several items inside -- a toy car,
a book, and a sticker. When you open the box, you take each item out
and put it somewhere specific: the car goes on the shelf, the book on
the desk, the sticker on your notebook.

**Tuple unpacking** works the same way. A function hands you a "box"
(a list) with multiple values, and you unpack each value into its own
variable in one go.

## Returning Multiple Values

A function can return more than one value by separating them with
commas:

```pebble
fn swap(a, b) {
    return b, a
}
```

Under the hood, `return b, a` is sugar for `return [b, a]` -- it
creates a list and returns it. But the comma syntax reads more
naturally.

## Unpacking with `let`

Use `let` with multiple names on the left side to unpack a list into
separate variables:

```pebble
let x, y = swap(1, 2)
print(x)   # prints: 2
print(y)   # prints: 1
```

You can unpack any list, not just function results:

```pebble
let a, b, c = [10, 20, 30]
print(a)   # prints: 10
print(b)   # prints: 20
print(c)   # prints: 30
```

## Unpacking with `const`

Use `const` to unpack into variables that cannot be changed later:

```pebble
const lo, hi = [1, 100]
# lo and hi are now locked -- trying to reassign them is an error
```

## Reassignment Unpacking

If the variables already exist, you can unpack into them without
`let` or `const`:

```pebble
let a = 0
let b = 0
a, b = [3, 4]
print(a)   # prints: 3
print(b)   # prints: 4
```

This is especially useful for the **swap idiom** -- swapping two
variables without a temporary:

```pebble
let x = 1
let y = 2
x, y = [y, x]
print(x)   # prints: 2
print(y)   # prints: 1
```

## Error Cases

Pebble checks at runtime that the list has exactly the right number of
elements:

```pebble
let a, b = [1, 2, 3]   # Error: Expected 2 values to unpack, got 3
let x, y, z = [1, 2]   # Error: Expected 3 values to unpack, got 2
let p, q = 42           # Error: Cannot unpack int, expected a list
```

## Practical Examples

### Swap

```pebble
fn swap(a, b) {
    return b, a
}
let x, y = swap(1, 2)
print(x)   # prints: 2
print(y)   # prints: 1
```

### Min and Max

```pebble
fn min_max(a, b) {
    if a < b {
        return a, b
    }
    return b, a
}
let lo, hi = min_max(7, 3)
print(lo)   # prints: 3
print(hi)   # prints: 7
```

### Divmod (quotient and remainder)

```pebble
fn divmod(a, b) {
    return a // b, a % b
}
let q, r = divmod(17, 5)
print(q)   # prints: 3
print(r)   # prints: 2
```

## Rules

- The number of names on the left **must** match the number of
  elements in the list on the right.
- `return a, b, c` is sugar for `return [a, b, c]`.
- `let` and `const` unpacking creates new variables.
- Reassignment unpacking (`x, y = ...`) requires the variables to
  already exist and not be `const`.
- You can unpack any expression that produces a list -- a literal, a
  function call, a list comprehension, or even an index into a list of
  lists.

## How It Works Under the Hood

When the compiler sees `let x, y = [1, 2]`, it emits:

1. Compile the right-hand side (the list `[1, 2]`).
2. `UNPACK_SEQUENCE 2` -- pop the list from the stack, check that it
   has exactly 2 elements, then push each element onto the stack
   (first element ends up on top).
3. `STORE_NAME "x"` -- pop the top value and store it as `x`.
4. `STORE_NAME "y"` -- pop the next value and store it as `y`.

The `UNPACK_SEQUENCE` instruction is the only new opcode. It validates
the list length and pushes elements in the right order so that the
first name gets the first element.

## Summary

| Syntax               | What it does                                  |
| -------------------- | --------------------------------------------- |
| `return a, b`        | Return a list `[a, b]` (sugar)                |
| `let x, y = expr`    | Unpack into new variables                     |
| `const x, y = expr`  | Unpack into new constants                     |
| `x, y = expr`        | Unpack into existing variables                |
| `UNPACK_SEQUENCE N`  | VM instruction: validate list length, push N  |
