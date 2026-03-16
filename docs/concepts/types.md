# Types

Every value in Pebble is one of **nine types**. Think of a type as a label
that tells you what *kind* of thing a value is -- just like how you'd sort
items in a toolbox into screwdrivers, hammers, and wrenches.

## The Nine Types

| Type     | What it is                      | Examples                  |
|----------|---------------------------------|---------------------------|
| `int`    | A whole number                  | `0`, `42`, `-7`           |
| `float`  | A number with a decimal point   | `3.14`, `0.5`, `1.0`      |
| `str`    | A piece of text                 | `"hello"`, `""`           |
| `bool`   | True or false                   | `true`, `false`           |
| `null`   | Nothing / no value              | `null`                    |
| `list`   | An ordered collection           | `[1, 2, 3]`, `[]`        |
| `dict`   | A collection of key-value pairs | `{"name": "Alice"}`      |
| `fn`     | A function                      | `fn(x) { return x * 2 }` |
| *struct* | A custom data type you define   | `Point(10, 20)`          |

## Checking a Type: `type()`

The built-in `type()` function tells you what type a value is. It always
returns a string:

```pebble
print(type(42))        # prints: int
print(type(3.14))      # prints: float
print(type("hello"))   # prints: str
print(type(true))      # prints: bool
print(type(null))      # prints: null
print(type([1, 2]))    # prints: list
print(type({}))        # prints: dict
```

For structs, `type()` returns the struct's name:

```pebble
struct Point { x, y }
let p = Point(10, 20)
print(type(p))         # prints: Point
```

You can use it in conditions:

```pebble
let x = 42
if type(x) == "int" {
    print("it is a number")
}
```

## What Each Type Can Do

Different types support different operations and methods. Here's a quick
map:

| Type     | Operators                    | Methods                     | More info                      |
|----------|------------------------------|-----------------------------|--------------------------------|
| `int`    | `+ - * / // % **`, bitwise, comparisons | --           | [Operators](operators.md)      |
| `float`  | `+ - * / // % **`, comparisons | --                       | [Operators](operators.md)      |
| `str`    | `+` (join)                   | `upper()`, `split()`, etc.  | [String Methods](strings.md)   |
| `bool`   | `and`, `or`, `not`           | --                          | [Statements](statements.md)    |
| `null`   | `==`, `!=`, `not`            | --                          | (this page)                    |
| `list`   | `+` (concatenate)            | `push()`, `pop()`, etc.     | [Arrays](arrays.md)            |
| `dict`   | index `d["key"]`             | --                          | [Dictionaries](dicts.md)       |
| `fn`     | call `f()`                   | --                          | [Functions](functions.md)      |
| *struct* | `.field`, `==`               | --                          | [Structs](structs.md), [Classes](classes.md) |

## Null

The `null` type represents **nothing** -- the absence of a value. Think of
it like an empty box: it's not that the box contains zero or an empty
string, it's that there's genuinely nothing inside.

```pebble
let x = null
print(x)          # prints: null
print(type(null))  # prints: null
```

### When does null appear?

- **Explicitly**: you write `null` in your code.
- **Implicit return**: a function that doesn't `return` a value gives back
  `null` automatically.
- **Bare return**: writing `return` without a value gives back `null`.
- **Void methods**: list methods like `push()`, `reverse()`, and `sort()`
  return `null` because they modify the list in place.

```pebble
fn greet() { print("hi") }
print(greet())   # prints: hi  then  null
```

### Null is falsy

In conditions, `null` behaves like `false` -- it means "no":

```pebble
if null { print("yes") } else { print("no") }   # prints: no
print(not null)                                   # prints: true
```

### Null is not zero

`null` is different from `0`, `false`, and `""`. It means "nothing at
all", not "zero" or "empty":

```pebble
print(null == 0)      # prints: false
print(null == false)   # prints: false
print(null == "")      # prints: false
print(null == null)    # prints: true
```

### What null can't do

You can't do maths or comparisons (other than `==` / `!=`) with null --
it's not a number:

```pebble
null + 1    # Error: Unsupported operand types for +
null < 1    # Error: Unsupported operand types for <
```

## Integers vs Floats

An **integer** (`int`) is a whole number with no decimal point. A **float**
is a number *with* a decimal point. Think of it like measuring: if you say
"3 apples" that's an integer, but "3.5 apples" is a float.

```pebble
print(type(42))    # prints: int
print(type(3.14))  # prints: float
print(type(1.0))   # prints: float   (the .0 makes it a float!)
```

### Mixed Arithmetic

When you mix `int` and `float` in a calculation, the result is always a
`float`. Pebble "widens" the integer to match -- like pouring water from
a small glass into a big one:

```pebble
print(1 + 2.0)    # prints: 3.0   (int + float = float)
print(3.0 * 2)    # prints: 6.0   (float * int = float)
print(5.5 - 2)    # prints: 3.5
```

### Two Kinds of Division

The `/` operator always gives you a `float`, even when the numbers divide
evenly. If you want whole-number division (throwing away the remainder),
use `//`:

```pebble
print(7 / 2)      # prints: 3.5   (true division — always float)
print(6 / 2)      # prints: 3.0   (still a float!)
print(7 // 2)     # prints: 3     (floor division — whole number)
```

### Converting Between int and float

Use `float()` to turn an integer or string into a float, and `int()` to
go the other way (it chops off the decimal part):

```pebble
print(float(42))     # prints: 42.0
print(float("3.14")) # prints: 3.14
print(int(3.7))      # prints: 3    (truncates toward zero)
print(int(-2.9))     # prints: -2   (truncates toward zero)
```

## Automatic Conversions

Pebble does **not** automatically convert between unrelated types. If you
try to add a number and a string, you get an error:

```pebble
print(1 + "hello")   # Error: Cannot add int and str
```

To convert explicitly, use `str()`, `int()`, or `float()`:

```pebble
let x = 42
print("answer: " + str(x))   # prints: answer: 42

let s = "7"
print(int(s) + 3)             # prints: 10

let f = "3.14"
print(float(f) + 1)           # prints: 4.140000000000001
```

Or use string interpolation, which converts automatically:

```pebble
let x = 42
print("answer: {x}")   # prints: answer: 42
```

## Type Annotations

You can add **type annotations** to variables, function parameters, return
values, and struct fields to tell Pebble what kind of value belongs there.
Pebble checks the annotations at runtime and raises an error if the value
doesn't match:

```pebble
let x: Int = 5
let y: Null = null
fn add(a: Int, b: Int) -> Int { return a + b }
struct Point { x: Float, y: Float }
```

Annotations are completely optional -- see
[Type Annotations](type-annotations.md) for the full guide.

## Summary

| Concept | Analogy |
|---------|---------|
| Type | A label on a toolbox drawer (structs get their own custom label) |
| `type()` | Reading the label to see what's inside |
| `null` | An empty box -- not zero, not empty string, just *nothing* |
| `int` vs `float` | "3 apples" vs "3.5 apples" |
| Mixed arithmetic | Pouring a small glass into a big one -- the result is always big (float) |
| `/` vs `//` | Sharing pizza: `/` tells you the exact amount, `//` tells you whole slices only |
| No auto-conversion | You can't hammer with a screwdriver |
| `str()` / `int()` / `float()` | Reshaping a tool to fit a different drawer |
