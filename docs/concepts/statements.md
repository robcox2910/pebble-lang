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

## Else If Chains

What if there are more than two paths? Think of a traffic light: it can be
green, yellow, or red — three choices, not just two. You *could* nest `if`
inside `else`, but that gets messy fast. Instead, use `else if`:

```pebble
if colour == "green" {
    print("Go!")
} else if colour == "yellow" {
    print("Slow down")
} else {
    print("Stop")
}
```

You can chain as many `else if` branches as you need:

```pebble
let score = 85
if score > 90 {
    print("A")
} else if score > 80 {
    print("B")
} else if score > 70 {
    print("C")
} else {
    print("D")
}
```

The computer checks each condition from top to bottom and runs the **first**
one that's true. If none are true, the `else` block runs (if there is one).

The final `else` is optional — without it, nothing happens if no condition
matches.

Under the hood, `else if` is just a shortcut. The parser turns it into a
nested `if` inside the `else` block, exactly as if you had written:

```pebble
if score > 90 {
    print("A")
} else {
    if score > 80 {
        print("B")
    } else {
        print("C")
    }
}
```

Both versions produce identical bytecode — `else if` just looks tidier.

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

## Counting: `for`

A `for` loop is like roll call — you go through a list of numbers one at a
time:

```pebble
for i in range(5) {
    print(i)
}
```

This prints `0`, `1`, `2`, `3`, `4`. The variable `i` starts at `0` and
counts up to (but not including) `5`.

You can use the loop variable inside the body:

```pebble
for i in range(3) {
    print(i * i)
}
```

This prints the squares: `0`, `1`, `4`.

Behind the scenes, the compiler turns a `for` loop into a `while` loop with
a hidden counter variable. You don't need to worry about that — just think
of it as "do this N times, and give me the number each time".

## Exiting Early: `break`

Sometimes you want to stop a loop before it finishes all its repetitions,
like leaving a cinema in the middle of a film. That's what `break` does --
it immediately exits the nearest loop:

```pebble
let x = 0
while true {
    if x == 3 { break }
    x = x + 1
}
print(x)
```

This prints `3`. Without `break`, the `while true` loop would run forever.
But as soon as `x` reaches 3, `break` jumps out of the loop.

`break` works in `for` loops too:

```pebble
for i in range(10) {
    if i == 3 { break }
    print(i)
}
```

This prints `0`, `1`, `2` and then stops -- even though `range(10)` would
normally count all the way to 9.

!!! warning "Only inside loops"
    You can only use `break` inside a `while` or `for` loop. Writing it
    outside a loop is an error.

## Skipping Ahead: `continue`

Sometimes you don't want to stop the whole loop, just skip the rest of
*this particular go-around* and move on to the next one. Think of it like
flipping past a song you don't like on a playlist -- you skip the song but
keep listening to the rest. That's `continue`:

```pebble
for i in range(5) {
    if i == 2 { continue }
    print(i)
}
```

This prints `0`, `1`, `3`, `4` -- it skips `2` but keeps going through
the rest of the numbers.

In a `while` loop, `continue` jumps back to the condition check:

```pebble
let total = 0
let i = 0
while i < 5 {
    i = i + 1
    if i == 3 { continue }
    total = total + i
}
print(total)
```

This prints `12` (1 + 2 + 4 + 5 -- skipping 3).

### Nested Loops

When `break` or `continue` is inside nested loops, it only affects the
**innermost** loop:

```pebble
for i in range(3) {
    for j in range(3) {
        if j == 1 { break }
        print(j)
    }
}
```

This prints `0`, `0`, `0`. The `break` exits the inner `j` loop each time,
but the outer `i` loop keeps going.

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
| `break` | Break statement |
| `continue` | Continue statement |
| `print` | Print statement |
| identifier followed by `=` | Reassignment |
| anything else | Expression statement |

This is called **recursive descent** -- the parser looks at the next token and
"descends" into the right parsing function. Each function knows exactly how its
statement is structured and what tokens to expect.

## What Can Go Wrong?

After parsing, the [semantic analyzer](analyzer.md) checks that declarations
make sense -- for example, that every variable you use was declared, and that
functions get the right number of arguments.

The parser catches *syntax* mistakes like:

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
| `else if` | A traffic light with many signals |
| `while` | A broken record that keeps replaying |
| `for` | Roll call -- go through each item one by one |
| `break` | Walking out of a cinema early |
| `continue` | Skipping a song on a playlist |
| `fn` / `return` | A recipe card you can reuse |
| Block `{ }` | Walls of a room grouping things together |
| Newlines | Periods at the end of sentences |

For more on functions and for loops, see [Functions](functions.md).
