# Standard Library

Pebble comes with a small set of **built-in functions** you can call from
anywhere in your program. You don't need to import anything — they're always
available.

## print(value)

Display a value on screen. Every Pebble type is automatically converted to
text:

```pebble
print(42)          # prints: 42
print("hello")     # prints: hello
print(true)        # prints: true
print([1, 2, 3])   # prints: [1, 2, 3]
```

`print()` always adds a newline at the end.

## range(n)

Generate a sequence of numbers from `0` up to (but **not** including) `n`.
It's used with `for` loops to repeat something a specific number of times:

```pebble
for i in range(4) {
    print(i)
}
# prints: 0, 1, 2, 3 (each on its own line)
```

Think of `range(4)` as saying "count from 0 up to 3". The number you give is
the **stop** point — the counting stops just before it.

!!! note
    `range()` can only be used inside a `for` loop. The compiler translates
    `for i in range(n)` into a counting while-loop behind the scenes.

## str(value)

Convert any value to its text form:

```pebble
print(str(42))      # prints: 42
print(str(true))    # prints: true
print(str([1, 2]))  # prints: [1, 2]
```

This is the same conversion that happens automatically inside `{…}` string
interpolation.

## int(value)

Convert a text string to a whole number:

```pebble
let age = int("12")
print(age + 1)   # prints: 13
```

If the string doesn't look like a number, Pebble stops with an error:

```pebble
int("hello")   # Error: Cannot convert 'hello' to int
```

Passing an integer to `int()` gives back the same number (handy if you're
not sure what type you have):

```pebble
print(int(42))   # prints: 42
```

## type(value)

Find out what kind of value something is:

```pebble
print(type(42))        # prints: int
print(type("hello"))   # prints: str
print(type(true))      # prints: bool
print(type([1, 2]))    # prints: list
```

The result is always a string like `"int"`, `"str"`, `"bool"`, or `"list"`.
You can use it in conditions:

```pebble
let x = 42
if type(x) == "int" {
    print("it is a number")
}
```

## len(value)

Count the number of items in a list, or characters in a string:

```pebble
print(len([10, 20, 30]))   # prints: 3
print(len("hello"))         # prints: 5
print(len([]))              # prints: 0
```

## push(list, value)

Add a value to the **end** of a list. This changes the list itself (it
doesn't create a new one):

```pebble
let xs = [1, 2, 3]
push(xs, 4)
print(xs)   # prints: [1, 2, 3, 4]
```

Think of it like adding another person to the back of a queue.

## pop(list)

Remove and give back the **last** value from a list:

```pebble
let xs = [1, 2, 3]
let last = pop(xs)
print(last)   # prints: 3
print(xs)     # prints: [1, 2]
```

If the list is empty, Pebble stops with an error — you can't take something
from an empty container.

## Putting It All Together

You can combine these to do useful things. Here's a program that builds a
list dynamically:

```pebble
let numbers = []
for i in range(5) {
    push(numbers, i * i)
}
print(numbers)   # prints: [0, 1, 4, 9, 16]
```

And here's a simple stack (last-in, first-out):

```pebble
let stack = []
push(stack, "first")
push(stack, "second")
push(stack, "third")

let top = pop(stack)
print("popped: {top}")         # prints: popped: third
print("size: {len(stack)}")    # prints: size: 2
```

## How It Works Under the Hood

Every built-in function lives in a Python module called `builtins.py`. It
holds a dictionary mapping each function's name to two things:

1. **Arity** — how many arguments the function expects (so the analyzer can
   check you passed the right number).
2. **Handler** — the Python function that actually does the work.

When the VM encounters a `CALL` instruction, it checks this dictionary
first. If the name matches a builtin, it pops the arguments off the stack,
calls the handler, and pushes the result back. If there's no match, it
looks for a user-defined function instead.

Think of it like a restaurant kitchen. The built-in functions are the dishes
already on the menu — the chef knows how to make them without a recipe card.
Your own functions are custom orders that need their own recipe (a
`CodeObject`).
