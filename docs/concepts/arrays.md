# Arrays

An **array** (Pebble calls them **lists**) is an ordered collection of values.
Think of it like a row of numbered boxes — each box holds one value, and you
can look up a box by its number.

## Creating a List

Put values between square brackets, separated by commas:

```pebble
let xs = [10, 20, 30]
print(xs)   # prints: [10, 20, 30]
```

An empty list has nothing between the brackets:

```pebble
let empty = []
print(empty)   # prints: []
```

Lists can hold any mix of types:

```pebble
let mixed = [1, "hello", true]
print(mixed)   # prints: [1, hello, true]
```

You can even put lists inside lists:

```pebble
let grid = [[1, 2], [3, 4]]
print(grid)   # prints: [[1, 2], [3, 4]]
```

You can also build a list from a loop using a
[list comprehension](list-comprehensions.md):

```pebble
let squares = [x * x for x in range(5)]
print(squares)   # prints: [0, 1, 4, 9, 16]
```

## Reading an Element

Use square brackets after the list name with an **index** — the position
number. Positions start at **0**, not 1:

```pebble
let fruits = ["apple", "banana", "cherry"]
print(fruits[0])   # prints: apple
print(fruits[1])   # prints: banana
print(fruits[2])   # prints: cherry
```

You can also use a variable as the index:

```pebble
let i = 1
print(fruits[i])   # prints: banana
```

If you use an index that is too big (or too negative), Pebble stops with an
error:

```pebble
print(fruits[99])   # Error: Index 99 out of bounds for list of length 3
```

## Negative Indexing

Sometimes you want to grab items from the **end** of a list without
knowing exactly how long it is. Negative indices let you count backwards:
`-1` is the last element, `-2` is the second-to-last, and so on.

Think of a queue of people. Positive indices count from the **front** of the
line — 0 is the first person, 1 is the second. Negative indices count from
the **back** — -1 is the last person, -2 is the one just before them.

```pebble
let colours = ["red", "green", "blue"]
print(colours[-1])   # prints: blue
print(colours[-2])   # prints: green
print(colours[-3])   # prints: red
```

You can also **assign** using negative indices:

```pebble
let scores = [10, 20, 30]
scores[-1] = 99
print(scores)   # prints: [10, 20, 99]
```

If you go too far back, you get an error — just like going too far forward:

```pebble
let xs = [1, 2, 3]
print(xs[-10])   # Error: Index -10 out of bounds for list of length 3
```

Under the hood, the VM simply converts the negative index:
`-1` becomes `len - 1`, `-2` becomes `len - 2`, and so on. Then it looks up
that position the normal way.

## Slicing

**Slicing** lets you grab a portion of a list (or string) in one step — like
tearing a page out of a notebook. You write `xs[start:stop]`, where `start`
is the first index to include and `stop` is the first index to *exclude*.

```
  xs = [10, 20, 30, 40, 50]
         0   1   2   3   4     ← indices

  xs[1:4]
         start ↓       ↓ stop (excluded)
        [10, 20, 30, 40, 50]
              ──────────
         result: [20, 30, 40]

  xs[::2]   (step = 2, take every other element)
        [10, 20, 30, 40, 50]
          ✓       ✓       ✓
         result: [10, 30, 50]
```

```pebble
let xs = [10, 20, 30, 40, 50]
print(xs[1:3])   # prints: [20, 30]
```

You can leave out parts:

```pebble
print(xs[:3])    # first three: [10, 20, 30]
print(xs[2:])    # from index 2 onward: [30, 40, 50]
print(xs[:])     # a full copy: [10, 20, 30, 40, 50]
```

Add a **step** after a second colon to skip elements:

```pebble
print(xs[::2])   # every other: [10, 30, 50]
print(xs[1:4:2]) # index 1 and 3: [20, 40]
```

A negative step reverses the direction:

```pebble
print(xs[::-1])  # reversed: [50, 40, 30, 20, 10]
```

Negative indices work too — just like regular indexing:

```pebble
print(xs[-2:])   # last two: [40, 50]
print(xs[:-1])   # everything except the last: [10, 20, 30, 40]
```

If your indices go past the end, Pebble silently clamps them — no error:

```pebble
print(xs[0:100]) # [10, 20, 30, 40, 50]
```

But a step of zero is an error (you'd never move forward!):

```pebble
print(xs[::0])   # Error: Slice step cannot be zero
```

### Slicing strings

Slicing works on strings just the same way:

```pebble
let s = "hello"
print(s[1:4])    # prints: ell
print(s[::-1])   # prints: olleh
```

### Slicing creates a copy

Slicing always produces a **new** list (or string). The original stays
untouched:

```pebble
let xs = [10, 20, 30]
let ys = xs[:]
ys[0] = 99
print(xs[0])   # prints: 10  (original unchanged)
```

Under the hood the compiler pushes the target, start, stop, and step onto
the stack, then emits a `SLICE_GET` instruction. The VM uses Python's built-in
slice machinery to do the heavy lifting — handling negative indices, clamping,
and stepping all in one go.

## List Methods

Lists have their own set of **methods** you can call using dot notation —
the same `value.method()` pattern used by [strings](strings.md).

### push()

Add a value to the end of the list:

```pebble
let xs = [1, 2, 3]
xs.push(4)
print(xs)   # prints: [1, 2, 3, 4]
```

!!! note
    The functional form `push(xs, 4)` still works too.

### pop()

Remove and return the last element:

```pebble
let xs = [1, 2, 3]
let last = xs.pop()
print(last)   # prints: 3
print(xs)     # prints: [1, 2]
```

Popping from an empty list is an error.

!!! note
    The functional form `pop(xs)` still works too.

### contains()

Check if a value is in the list:

```pebble
let xs = [1, 2, 3]
print(xs.contains(2))    # prints: true
print(xs.contains(99))   # prints: false
```

### reverse()

Reverse the list in place:

```pebble
let xs = [1, 2, 3]
xs.reverse()
print(xs)   # prints: [3, 2, 1]
```

### sort()

Sort the list in place:

```pebble
let xs = [3, 1, 2]
xs.sort()
print(xs)   # prints: [1, 2, 3]
```

Sorting works on lists of all integers or all strings. Mixing types is an
error.

### Quick Reference

| Method          | Args | Returns | Description                 |
| --------------- | ---- | ------- | --------------------------- |
| `push(value)`   | 1    | `null`  | Append to end               |
| `pop()`         | 0    | value   | Remove and return last      |
| `contains(val)` | 1    | bool    | Is `val` in the list?       |
| `reverse()`     | 0    | `null`  | Reverse in place            |
| `sort()`        | 0    | `null`  | Sort in place               |

## Changing an Element

Assign to a specific position to replace the value in that box:

```pebble
let scores = [0, 0, 0]
scores[1] = 42
print(scores)   # prints: [0, 42, 0]
```

## Finding the Length

The built-in `len()` function tells you how many elements a list has:

```pebble
let xs = [10, 20, 30, 40]
print(len(xs))   # prints: 4
print(len([]))   # prints: 0
```

`len()` also works on strings:

```pebble
print(len("hello"))   # prints: 5
```

## Looping Over a List

Combine `for` + `range` + indexing to visit every element:

```pebble
let colours = ["red", "green", "blue"]
for i in range(len(colours)) {
    print(colours[i])
}
```

This prints each colour on its own line.

## Lists with Other Features

### String Interpolation

You can use list elements inside `{…}` strings:

```pebble
let xs = [1, 2, 3]
print("first: {xs[0]}, total: {len(xs)}")
# prints: first: 1, total: 3
```

### Functions

Lists can be passed to functions and returned from them:

```pebble
fn first(xs) { return xs[0] }
print(first([42, 99]))   # prints: 42
```

## How It Works Under the Hood

When the **compiler** sees `[1, 2, 3]`, it emits instructions to push each
element onto the stack, then a `BUILD_LIST 3` instruction. The **VM** pops
three values and bundles them into a single list value.

For `xs[0]`, the compiler emits code to push the list and the index, then an
`INDEX_GET` instruction. The VM pops both, looks up the element, and pushes
it back.

For `xs[0] = 42`, the compiler pushes the list, index, and new value, then
emits `INDEX_SET`. The VM pops all three and changes the element in place.

Think of `BUILD_LIST` like packing items into a backpack — you hand over
three separate things and get one backpack back. `INDEX_GET` is reaching into
a specific pocket by number, and `INDEX_SET` is swapping what's in that
pocket for something new.

### The Full Journey

Here's how `let xs = [1, 2]` travels through the whole pipeline:

1. **Lexer** — produces tokens: `LET`, `IDENTIFIER("xs")`, `EQUAL`,
   `LEFT_BRACKET`, `INTEGER(1)`, `COMMA`, `INTEGER(2)`, `RIGHT_BRACKET`
2. **Parser** — builds an `Assignment` node whose value is an
   `ArrayLiteral` containing two `IntegerLiteral` nodes
3. **Analyzer** — checks that the variable name is valid
4. **Compiler** — emits `LOAD_CONST 0`, `LOAD_CONST 1`, `BUILD_LIST 2`,
   `STORE_NAME "xs"`
5. **VM** — pushes `1` and `2`, packs them into a list, stores the list as
   `xs`

Every feature in Pebble follows this same path from text to running code.
