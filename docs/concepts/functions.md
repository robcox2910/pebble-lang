# Functions & For Loops

## What Is a Function?

A **function** is like a **recipe card**. You write down the steps once, give
it a name, and then use that recipe whenever you need it -- without rewriting
the whole thing.

```pebble
fn greet() {
    print("Hello!")
}

greet()
greet()
```

Here `greet` is a recipe that prints "Hello!". We **call** (use) it twice, so
"Hello!" appears twice.

## Defining a Function: `fn`

To create a function, use the `fn` keyword:

```pebble
fn name(parameters) {
    body
}
```

- **`fn`** -- tells Pebble "I'm writing a new recipe"
- **name** -- the label on the recipe card (e.g. `greet`, `add`, `square`)
- **parameters** -- ingredient slots (more on these below)
- **body** -- the instructions inside `{ }`

### Parameters: The Ingredient Slots

Parameters are like blank spaces on a recipe card where you write in the
specific ingredients each time you use it:

```pebble
fn add(a, b) {
    return a + b
}
```

`a` and `b` are **parameters** -- placeholders that get filled in when you
call the function.

## Calling a Function

To use a function, write its name followed by parentheses with the values
(called **arguments**) you want to pass in:

```pebble
add(3, 4)
```

Here `3` and `4` are **arguments** -- the actual ingredients you hand to the
recipe. They fill the parameter slots: `a` gets `3`, `b` gets `4`.

You can call functions with zero, one, or many arguments:

```pebble
greet()           # no arguments
square(5)         # one argument
add(10, 20)       # two arguments
```

Arguments can be any expression, not just simple values:

```pebble
add(1 + 2, x)
add(square(3), 4)
```

That second line shows **nested calls** -- a function call inside another
function call, like a recipe that says "first make the sauce (another recipe),
then add it to the dish."

## Giving Back a Result: `return`

The `return` keyword is like handing back the finished dish. It sends a value
out of the function:

```pebble
fn square(x) {
    return x * x
}

let result = square(5)
print(result)
```

A function can also `return` without a value (a bare return), which just
means "stop here, I'm done":

```pebble
fn maybe_print(x) {
    if x < 0 {
        return
    }
    print(x)
}
```

## Going Through Items: `for` Loops

A **for loop** is like doing a **roll call** -- you go through a list of items
one by one, doing something with each one:

```pebble
for i in range(5) {
    print(i)
}
```

This prints `0`, `1`, `2`, `3`, `4`. Each time around the loop, `i` takes
the next value from `range(5)`.

The structure is:

```
for variable in iterable {
    body
}
```

- **variable** -- a name that holds the current item (like `i`)
- **iterable** -- something that produces items to loop over
- **body** -- what to do with each item

You can also give `range` a starting point, or a step size:

```pebble
for i in range(2, 5) {
    print(i)
}
# prints: 2, 3, 4

for i in range(0, 10, 2) {
    print(i)
}
# prints: 0, 2, 4, 6, 8

for i in range(5, 0, -1) {
    print(i)
}
# prints: 5, 4, 3, 2, 1
```

See [Standard Library](stdlib.md) for all `range()` forms.

### For vs While

Both `for` and `while` repeat things, but they're suited for different jobs:

| | `for` | `while` |
|---|---|---|
| Best for | Going through a collection | Repeating until a condition changes |
| Counter needed? | Built-in (`i` in `for i in ...`) | You manage it yourself |
| Analogy | Roll call | Broken record |

## Functions Are Values

In Pebble, functions are **first-class values** -- just like numbers and
strings. That means you can store a function in a variable, put it in a list,
or pass it as an argument to another function:

```pebble
fn double(x) { return x * 2 }

let f = double
print(f(5))          # prints: 10
print(type(double))  # prints: fn
```

Think of it this way: the recipe card itself is a thing you can pick up, hand
to someone, or put in a drawer. You can use it later, or give it to a
different chef.

### Anonymous Functions

Sometimes you need a tiny recipe that you'll only use once. Instead of giving
it a name, you can write it inline:

```pebble
let triple = fn(x) { return x * 3 }
print(triple(4))   # prints: 12
```

This creates a function without the usual `fn name(...)` form -- just
`fn(params) { body }` directly in an expression. It's especially useful with
[higher-order functions](higher-order.md) like `map`, `filter`, and `reduce`.

## Putting It All Together

Here's a program that uses functions and for loops together:

```pebble
fn greet(name) {
    print(name)
}

fn count_up(n) {
    for i in range(n) {
        print(i)
    }
}

greet("Alice")
count_up(3)
```

Functions can contain for loops, for loops can contain if statements -- you can
nest them however you like to build up complex behaviour from simple pieces.

## What Can Go Wrong?

The parser catches several mistakes:

| Code | Error |
|------|-------|
| `foo(1, 2` | Expected ')' after arguments |
| `foo(1,)` | Unexpected token ')' |
| `for in items { }` | Expected loop variable after 'for' |
| `for i items { }` | Expected 'in' after loop variable |
| `fn () { }` | Expected function name after 'fn' |
| `fn greet { }` | Expected '(' after function name |

## Summary

| Concept | Analogy |
|---------|---------|
| Function | A recipe card |
| Parameter | An ingredient slot on the recipe |
| Argument | The actual ingredient you hand over |
| `return` | Handing back the finished dish |
| `for` loop | Roll call -- go through each item one by one |
| Function call `()` | Using a recipe |
