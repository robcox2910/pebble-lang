# Types

Every value in Pebble is one of **seven types**. Think of a type as a label
that tells you what *kind* of thing a value is -- just like how you'd sort
items in a toolbox into screwdrivers, hammers, and wrenches.

## The Seven Types

| Type    | What it is                      | Examples                  |
|---------|---------------------------------|---------------------------|
| `int`   | A whole number                  | `0`, `42`, `-7`           |
| `float` | A number with a decimal point   | `3.14`, `0.5`, `1.0`      |
| `str`   | A piece of text                 | `"hello"`, `""`           |
| `bool`  | True or false                   | `true`, `false`           |
| `list`  | An ordered collection           | `[1, 2, 3]`, `[]`        |
| `dict`  | A collection of key-value pairs | `{"name": "Alice"}`      |
| `fn`    | A function                      | `fn(x) { return x * 2 }` |

## Checking a Type: `type()`

The built-in `type()` function tells you what type a value is. It always
returns a string:

```pebble
print(type(42))        # prints: int
print(type(3.14))      # prints: float
print(type("hello"))   # prints: str
print(type(true))      # prints: bool
print(type([1, 2]))    # prints: list
print(type({}))        # prints: dict
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

| Type    | Operators                    | Methods                     | More info                      |
|---------|------------------------------|-----------------------------|--------------------------------|
| `int`   | `+ - * / // % **`, bitwise, comparisons | --           | [Operators](operators.md)      |
| `float` | `+ - * / // % **`, comparisons | --                       | [Operators](operators.md)      |
| `str`   | `+` (join)                   | `upper()`, `split()`, etc.  | [String Methods](strings.md)   |
| `bool`  | `and`, `or`, `not`           | --                          | [Statements](statements.md)    |
| `list`  | `+` (concatenate)            | `push()`, `pop()`, etc.     | [Arrays](arrays.md)            |
| `dict`  | index `d["key"]`             | --                          | [Dictionaries](dicts.md)       |
| `fn`    | call `f()`                   | --                          | [Functions](functions.md)      |

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

## Summary

| Concept | Analogy |
|---------|---------|
| Type | A label on a toolbox drawer |
| `type()` | Reading the label to see what's inside |
| `int` vs `float` | "3 apples" vs "3.5 apples" |
| Mixed arithmetic | Pouring a small glass into a big one -- the result is always big (float) |
| `/` vs `//` | Sharing pizza: `/` tells you the exact amount, `//` tells you whole slices only |
| No auto-conversion | You can't hammer with a screwdriver |
| `str()` / `int()` / `float()` | Reshaping a tool to fit a different drawer |
