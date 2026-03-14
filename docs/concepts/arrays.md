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
