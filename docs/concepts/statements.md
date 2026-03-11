# Statements

## Expressions vs Statements

Think of a kitchen. An **expression** is like asking "How much is 2 + 3?" --
you get an answer back (5). A **statement** is like saying "Put the eggs in the
fridge" -- it's an instruction that *does* something but doesn't give you an
answer.

In Pebble:

- **Expressions** produce a value: `1 + 2`, `x > 10`, `true`
- **Statements** perform an action: create a variable, print something, make a
  decision

## Variable Declarations: `let`

To create a new variable, use `let`:

```pebble
let name = "Alice"
let age = 12
let score = 80 + 15
```

This is like writing a label on a box and putting something inside. The `let`
keyword says "I'm creating something new", the name is the label, and the value
after `=` is what goes in the box.

## Reassignment

Once a variable exists, you can change what's inside:

```pebble
let count = 0
count = count + 1
```

Notice there's no `let` the second time -- you're not creating a new box, just
replacing what's inside an existing one.

## Printing: `print()`

To display a value on screen:

```pebble
print(42)
print("Hello, world!")
print(x + y)
```

The parentheses are required -- `print` is written like a function call. You can
put any expression inside.

## Making Decisions: `if` / `else`

Sometimes your program needs to choose between two paths, like a fork in a road:

```pebble
if score > 90 {
    print("Excellent!")
} else {
    print("Keep trying!")
}
```

The condition (`score > 90`) is an expression that produces `true` or `false`.
If it's `true`, the first block runs. If it's `false`, the `else` block runs.

The `else` part is optional:

```pebble
if raining {
    print("Bring an umbrella")
}
```

## Repeating Things: `while`

A `while` loop is like a broken record -- it keeps doing the same thing until
you tell it to stop:

```pebble
let i = 0
while i < 5 {
    print(i)
    i = i + 1
}
```

This prints `0`, `1`, `2`, `3`, `4`. Each time around the loop, the condition
is checked again. When `i` reaches `5`, the condition `i < 5` becomes `false`
and the loop stops.

!!! warning "Infinite loops"
    If the condition never becomes `false`, the loop runs forever! Always make
    sure something inside the loop changes so the condition will eventually
    fail.

## Blocks: Curly Braces

The `{ }` curly braces group statements together into a **block**. Think of
them like the walls of a room -- everything between `{` and `}` belongs
together.

```pebble
if condition {
    let x = 10
    print(x)
}
```

Blocks appear after `if`, `else`, `while`, `for`, and `fn`. Each block can
contain any number of statements (even zero!).

## Newlines as Separators

In Pebble, each statement goes on its own line. There are no semicolons --
newlines tell the parser "that statement is done, start the next one."

```pebble
let x = 1
let y = 2
print(x + y)
```

Blank lines between statements are fine -- the parser simply skips them.

## How the Parser Handles Statements

When the parser sees a new line, it peeks at the first token to decide what kind
of statement it is:

| First token | Statement type |
|-------------|---------------|
| `let` | Variable declaration |
| `if` | If/else statement |
| `while` | While loop |
| `for` | For loop |
| `fn` | Function definition |
| `return` | Return statement |
| `print` | Print statement |
| identifier followed by `=` | Reassignment |
| anything else | Expression statement |

This is called **recursive descent** -- the parser looks at the next token and
"descends" into the right parsing function. Each function knows exactly how its
statement is structured and what tokens to expect.

## What Can Go Wrong?

The parser catches mistakes like:

- `let = 5` -- "Expected variable name after 'let'"
- `let x 5` -- "Expected '=' after variable name"
- `print 42` -- "Expected '(' after 'print'"
- `print(42` -- "Expected ')' after print argument"
- `if true print(1)` -- "Expected '{'"

Each error message tells you exactly what the parser expected and where the
problem was found.

## Summary

| Concept | Analogy |
|---------|---------|
| Expression | A question that gives you an answer |
| Statement | An instruction on a to-do list |
| `let` | Writing a label on a new box |
| Reassignment | Replacing what's inside an existing box |
| `if/else` | A fork in the road |
| `while` | A broken record that keeps replaying |
| `for` | Roll call -- go through each item one by one |
| `fn` / `return` | A recipe card you can reuse |
| Block `{ }` | Walls of a room grouping things together |
| Newlines | Periods at the end of sentences |

For more on functions and for loops, see [Functions](functions.md).
