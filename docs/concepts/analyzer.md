# Semantic Analysis

## What Is Semantic Analysis?

Imagine you write an essay and run spell-check. It catches misspelt words and
broken grammar, but it can't tell you whether your sentences *make sense*. You
could write "The cat drove the ocean to school" -- every word is spelt right and
the grammar is fine, but the meaning is nonsense.

The **semantic analyzer** is the sense-checker for your program. The parser
already checked the grammar (syntax), but the analyzer walks through the AST and
asks: "Does this program actually make logical sense?"

## Why the Parser Isn't Enough

The parser makes sure your code *looks right*:

```pebble
let x = 5
print(y)
```

The parser is perfectly happy with this -- every token is in the right place.
But wait: we never declared `y`! The program's grammar is fine, but its *meaning*
is broken. That's where the analyzer steps in and says: "Hold on, `y` doesn't
exist."

Here are some things the parser **cannot** catch:

| Problem | Example |
|---------|---------|
| Using a variable that doesn't exist | `print(y)` when `y` was never declared |
| Declaring the same variable twice | `let x = 1` then `let x = 2` in the same block |
| Calling a function that doesn't exist | `foo()` when `foo` was never defined |
| Wrong number of arguments | `add(1)` when `add` takes two parameters |
| Returning outside a function | `return 42` at the top level |

## Scopes: Rooms in a Building

A **scope** is like a room in a building. When you declare a variable, you're
writing its name on a whiteboard in that room. Anyone in the room can see it.

```pebble
let x = 10

if true {
    let y = 20
    print(x)    # Can see x (it's in the hallway)
    print(y)    # Can see y (it's in this room)
}

print(x)        # Fine -- x is still on the hallway whiteboard
print(y)        # Error! y's whiteboard is in the if-room, and we left
```

The rules are simple:

- **You can always look outward** -- from a room into the hallway, from the
  hallway into the lobby
- **You can never look inward** -- from the hallway into a room
- **Sibling rooms can't see each other** -- the `if` room and the `else` room
  are separate

### What Creates a New Scope?

| Construct | New scope for... |
|-----------|------------------|
| `if { }` | The if-body |
| `else { }` | The else-body |
| `while { }` | The loop body |
| `for i in ... { }` | The loop variable and body |
| `fn f() { }` | The parameters and body |

## Variable Checks

### Declaration

When you write `let x = 5`, the analyzer writes `x` on the current room's
whiteboard. If `x` is already there, it raises an error:

```pebble
let x = 1
let x = 2    # Error: Variable 'x' already declared
```

But if you're in a *different* room (an inner scope), you can use the same name.
This is called **shadowing** -- your local `x` temporarily hides the outer one:

```pebble
let x = 1
if true {
    let x = 99   # Fine -- this is a different room
    print(x)     # Prints 99
}
print(x)         # Prints 1 -- the outer x was never changed
```

### Using a Variable

When you use a variable name, the analyzer checks: "Is this name on any
whiteboard I can see?" It starts in the current room and walks outward through
every enclosing scope until it reaches the global scope. If it never finds the
name, you get an error:

```pebble
print(z)    # Error: Undeclared variable 'z'
```

### Reassignment

Reassignment (`x = 10`) only works if `x` was already declared somewhere
visible. You can't reassign a variable that doesn't exist:

```pebble
x = 5    # Error: Undeclared variable 'x'
```

## Function Checks

### Declaring a Function

When you write `fn greet() { ... }`, the analyzer registers `greet` as a
function. Functions live in a separate namespace from variables, so you could
have a variable called `greet` and a function called `greet` without conflict.

Just like variables, you can't declare two functions with the same name in the
same scope:

```pebble
fn greet() { print("hi") }
fn greet() { print("bye") }   # Error: Function 'greet' already defined
```

### Calling a Function

When you call a function, the analyzer checks two things:

1. **Does the function exist?** If you call `foo()` but never defined `foo`,
   that's an error.
2. **Did you pass the right number of arguments?** If `add` takes two
   parameters but you only pass one, that's an error too.

```pebble
fn add(a, b) {
    return a + b
}

add(1)        # Error: Function 'add' expects 2 arguments, got 1
add(1, 2, 3)  # Error: Function 'add' expects 2 arguments, got 3
add(1, 2)     # Fine!
```

### No Hoisting

Pebble reads your program from top to bottom. You must define a function
*before* you call it:

```pebble
greet()                    # Error: Undeclared function 'greet'
fn greet() { print("hi") }
```

### Built-in Functions

`print` and `range` are built-in -- they're already on the whiteboard when your
program starts. You never need to declare them:

```pebble
print("hello")    # Works -- print is built in (1 argument)
range(10)         # Works -- range is built in (1 argument)
```

## Return Checks

A `return` statement can only appear inside a function. Using it at the top
level makes no sense -- there's no function to return from:

```pebble
return 42    # Error: Return statement outside function
```

Inside a function, you can return from any depth of nesting:

```pebble
fn check(x) {
    if x > 0 {
        return x     # Fine -- we're inside fn check
    }
    return 0
}
```

## Block Scoping in Action

Here's a bigger example showing how scopes nest:

```pebble
let total = 0                # Global scope

fn process(n) {              # New scope: n is a parameter
    for i in range(n) {      # New scope: i is the loop variable
        if i > 0 {           # New scope
            let temp = i     # Only visible inside this if-block
            total = total + temp
        }
    }
    # i is gone here (left the for-room)
    # temp is gone here (left the if-room)
    # n is still visible (we're still in the function)
}
```

## Error Examples

| Code | Error |
|------|-------|
| `print(x)` | Undeclared variable 'x' |
| `let x = 1` then `let x = 2` | Variable 'x' already declared |
| `x = 5` (no `let`) | Undeclared variable 'x' |
| `foo()` | Undeclared function 'foo' |
| `fn f(a) {}` then `f(1, 2)` | Function 'f' expects 1 argument, got 2 |
| `return 42` (top level) | Return statement outside function |
| `let x = x` | Undeclared variable 'x' (x isn't declared yet when the value is evaluated) |

## Summary

| Concept | Analogy |
|---------|---------|
| Semantic analysis | A teacher checking your essay for sense, not just spelling |
| Scope | A room in a building with a whiteboard |
| Declaration | Writing a name on the whiteboard |
| Resolution | Looking for a name on whiteboards you can see |
| Shadowing | An inner room's whiteboard hiding an outer one |
| Undeclared variable | Trying to pick up a package that isn't addressed to you |
| Arity check | A recipe that needs 2 eggs -- you can't use 1 or 3 |
| Return outside function | Trying to "send back" when nobody asked you a question |
