# Types

Every value in Pebble is one of **six types**. Think of a type as a label
that tells you what *kind* of thing a value is -- just like how you'd sort
items in a toolbox into screwdrivers, hammers, and wrenches.

## The Six Types

| Type   | What it is                | Examples                 |
|--------|---------------------------|--------------------------|
| `int`  | A whole number            | `0`, `42`, `-7`          |
| `str`  | A piece of text           | `"hello"`, `""`          |
| `bool` | True or false             | `true`, `false`          |
| `list` | An ordered collection     | `[1, 2, 3]`, `[]`       |
| `dict` | A collection of key-value pairs | `{"name": "Alice"}` |
| `fn`   | A function                | `fn(x) { return x * 2 }`|

## Checking a Type: `type()`

The built-in `type()` function tells you what type a value is. It always
returns a string:

```pebble
print(type(42))        # prints: int
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

| Type   | Operators         | Methods                | More info                   |
|--------|-------------------|------------------------|-----------------------------|
| `int`  | `+ - * / %`, comparisons | --              | [Statements](statements.md) |
| `str`  | `+` (join)        | `upper()`, `split()`, etc. | [String Methods](strings.md) |
| `bool` | `and`, `or`, `not`| --                     | [Statements](statements.md) |
| `list` | `+` (concatenate) | `push()`, `pop()`, etc. | [Arrays](arrays.md)         |
| `dict` | index `d["key"]`  | --                     | [Dictionaries](dicts.md)    |
| `fn`   | call `f()`        | --                     | [Functions](functions.md)   |

## Automatic Conversions

Pebble does **not** automatically convert between types. If you try to add
a number and a string, you get an error:

```pebble
print(1 + "hello")   # Error: Cannot add int and str
```

To convert explicitly, use `str()` or `int()`:

```pebble
let x = 42
print("answer: " + str(x))   # prints: answer: 42

let s = "7"
print(int(s) + 3)             # prints: 10
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
| No auto-conversion | You can't hammer with a screwdriver |
| `str()` / `int()` | Reshaping a tool to fit a different drawer |
