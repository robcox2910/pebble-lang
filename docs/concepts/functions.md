# Functions

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

### Default Parameters

Sometimes a recipe has a go-to ingredient that you use *most* of the time.
Instead of writing it out every single call, you can put a **default value**
right on the recipe card. Think of it as pre-filling an ingredient slot with
your usual choice -- you can still swap it out, but if you don't, the default
kicks in.

```pebble
fn greet(name, greeting = "Hello") {
    print("{greeting} {name}")
}

greet("Alice")          # prints: Hello Alice
greet("Alice", "Hi")    # prints: Hi Alice
```

`greeting` has a default of `"Hello"`. When you call `greet("Alice")`, you
only pass one argument, so `greeting` uses its default. When you call
`greet("Alice", "Hi")`, the `"Hi"` you provided overrides the default.

You can have several defaults:

```pebble
fn make_point(x, y = 0, z = 0) {
    return [x, y, z]
}

print(make_point(5))         # prints: [5, 0, 0]
print(make_point(5, 10))     # prints: [5, 10, 0]
print(make_point(5, 10, 15)) # prints: [5, 10, 15]
```

**Rules to remember:**

- Required parameters must come **before** any with defaults. You can't write
  `fn f(a = 1, b)` -- Pebble won't know which slot `b` should fill.
- Defaults must be **literal values** (numbers, strings, booleans, or
  `null`). You can't use a variable or an expression like `1 + 2` as a
  default.

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

A function can also `return` without a value (a bare return), which gives
back `null` -- meaning "nothing here, I'm done":

```pebble
fn maybe_print(x) {
    if x < 0 {
        return
    }
    print(x)
}
```

## Returning Multiple Values

Sometimes a function needs to hand back more than one result -- like a
recipe that produces both a main dish and a side dish. Pebble lets you
return multiple values by separating them with commas:

```pebble
fn swap(a, b) {
    return b, a
}

let x, y = swap(1, 2)
print(x)   # prints: 2
print(y)   # prints: 1
```

Under the hood, `return b, a` creates a list `[b, a]` and returns it.
On the other side, `let x, y = ...` unpacks the list so each value
lands in its own variable.

See [Tuple Unpacking](tuple-unpacking.md) for the full story --
including `const` unpacking, reassignment unpacking, and the swap
idiom.

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

Here's a program that uses functions with other features:

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

Functions can contain loops, conditions, and other statements -- you can
nest them however you like to build up complex behaviour from simple pieces.

## What Can Go Wrong?

The parser catches several mistakes:

| Code | Error |
|------|-------|
| `foo(1, 2` | Expected ')' after arguments |
| `foo(1,)` | Unexpected token ')' |
| `fn () { }` | Expected function name after 'fn' |
| `fn greet { }` | Expected '(' after function name |
| `fn f(a = 1, b) { }` | Required parameter cannot follow a parameter with a default |
| `fn f(a = 1 + 2) { }` | Default parameter values must be literals |

## Summary

| Concept | Analogy |
|---------|---------|
| Function | A recipe card |
| Parameter | An ingredient slot on the recipe |
| Default parameter | A pre-filled ingredient slot |
| Argument | The actual ingredient you hand over |
| `return` | Handing back the finished dish |
| Function call `()` | Using a recipe |
