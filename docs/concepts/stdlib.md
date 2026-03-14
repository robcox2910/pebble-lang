# Standard Library

Pebble comes with a small set of **built-in functions** you can call from
anywhere in your program. You don't need to import anything — they're always
available.

## print(value)

Display a value on screen. Every Pebble type is automatically converted to
text:

```pebble
print(42)              # prints: 42
print("hello")         # prints: hello
print(true)            # prints: true
print([1, 2, 3])       # prints: [1, 2, 3]
print({"a": 1})        # prints: {a: 1}
```

`print()` always adds a newline at the end.

## range(...)

Generate a sequence of numbers for a `for` loop. There are three ways to
call it:

### range(stop)

Count from `0` up to (but **not** including) `stop`:

```pebble
for i in range(4) {
    print(i)
}
# prints: 0, 1, 2, 3 (each on its own line)
```

Think of `range(4)` as saying "count from 0 up to 3".

### range(start, stop)

Count from `start` up to (but **not** including) `stop`:

```pebble
for i in range(2, 5) {
    print(i)
}
# prints: 2, 3, 4
```

If `start` equals `stop`, the loop body never runs.

### range(start, stop, step)

Count from `start` toward `stop`, adding `step` each time:

```pebble
for i in range(0, 10, 2) {
    print(i)
}
# prints: 0, 2, 4, 6, 8
```

The `step` can be **negative** to count backwards:

```pebble
for i in range(5, 0, -1) {
    print(i)
}
# prints: 5, 4, 3, 2, 1
```

If the step goes the wrong direction (e.g. `range(0, 5, -1)`), the loop
body never runs — there's nothing to count through.

!!! note
    `range()` can only be used inside a `for` loop. The compiler translates
    `for i in range(...)` into a counting while-loop behind the scenes.

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
print(type({}))        # prints: dict
```

The result is always a string like `"int"`, `"str"`, `"bool"`, `"list"`, or
`"dict"`.
You can use it in conditions:

```pebble
let x = 42
if type(x) == "int" {
    print("it is a number")
}
```

## len(value)

Count the number of items in a list or dict, or characters in a string:

```pebble
print(len([10, 20, 30]))       # prints: 3
print(len("hello"))             # prints: 5
print(len({"a": 1, "b": 2}))  # prints: 2
print(len([]))                  # prints: 0
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

## keys(dict)

Return a list of all the keys in a dictionary, in the order they were added:

```pebble
let d = {"name": "Alice", "age": 12}
print(keys(d))   # prints: [name, age]
```

If the dictionary is empty, you get an empty list:

```pebble
print(keys({}))   # prints: []
```

## values(dict)

Return a list of all the values in a dictionary, in the order they were added:

```pebble
let d = {"name": "Alice", "age": 12}
print(values(d))   # prints: [Alice, 12]
```

If the dictionary is empty, you get an empty list:

```pebble
print(values({}))   # prints: []
```

## map(fn, list)

Apply a function to every element and return a new list of results. The first
argument can be a named function or an anonymous function (`fn(...) { ... }`):

```pebble
fn double(x) { return x * 2 }
print(map(double, [1, 2, 3]))   # prints: [2, 4, 6]
```

You can also use an anonymous function:

```pebble
print(map(fn(x) { return x + 10 }, [1, 2, 3]))   # prints: [11, 12, 13]
```

See [Higher-Order Functions](higher-order.md) for more details.

## filter(fn, list)

Keep only the elements where the function returns `true`:

```pebble
fn is_even(x) { return x % 2 == 0 }
print(filter(is_even, [1, 2, 3, 4]))   # prints: [2, 4]
```

See [Higher-Order Functions](higher-order.md) for more details.

## reduce(fn, list, initial)

Combine all elements into a single value using a function and a starting
value:

```pebble
fn add(a, b) { return a + b }
print(reduce(add, [1, 2, 3], 0))   # prints: 6
```

See [Higher-Order Functions](higher-order.md) for more details.

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
