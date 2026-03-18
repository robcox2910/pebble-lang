# Formatter

## What Is a Formatter?

Imagine you share a bedroom with a sibling. You both put your clothes away, but in totally different ways -- one person folds everything neatly and the other just shoves things into drawers. A **formatter** is like a robot that goes through the whole room and organizes everything in the exact same way, every time.

In programming, a formatter takes your code and rewrites it so it follows consistent style rules. The code does the exact same thing as before -- the formatter only changes how it *looks*, not how it *works*.

## Why Format Code?

When many people work on the same project, everyone has slightly different habits:

- Some people put spaces around `+`, others don't
- Some people indent with 2 spaces, others with 4
- Some people like blank lines between functions, others don't

These differences make code harder to read. A formatter eliminates all arguments about style by applying one set of rules automatically.

## Using the Formatter

Format a file in place (rewrites the file):

```
pebble fmt myfile.pbl
```

Check if a file is already formatted (useful in CI):

```
pebble fmt --check myfile.pbl
```

The `--check` flag exits with code 1 if the file isn't formatted, without modifying it. This is handy for automated checks that ensure all code is formatted before it's merged.

## What the Formatter Does

### Consistent Indentation

All blocks use 4-space indentation:

```pebble
# Before (messy)
if true {
  print(1)
    print(2)
 }

# After (clean)
if true {
    print(1)
    print(2)
}
```

### Operator Spacing

Binary operators always get spaces around them:

```pebble
# Before
let x = 1+2*3

# After
let x = 1 + 2 * 3
```

### Brace Placement

Opening braces go on the same line. Closing braces get their own line:

```pebble
if x > 10 {
    print(x)
} else {
    print(0)
}
```

### Blank Lines Between Definitions

Functions, classes, structs, and enums are separated by blank lines:

```pebble
fn add(a, b) {
    return a + b
}

fn multiply(a, b) {
    return a * b
}
```

### Comment Preservation

The formatter keeps your comments in place:

```pebble
# Calculate the total
let total = price + tax  # includes shipping
```

## How It Works

The formatter works in three steps:

1. **Extract comments** -- Since the lexer discards `#` comments, the formatter does a separate pass over the raw source text to find and remember every comment, along with which line it was on.

2. **Parse and walk the AST** -- The source is lexed and parsed normally into an Abstract Syntax Tree. The formatter walks every node in the tree and produces clean, consistently-styled output.

3. **Interleave comments** -- The extracted comments are inserted back into the formatted output at their original positions.

This approach is called **AST-based formatting**. It's the same technique used by famous formatters like Go's `gofmt`, Rust's `rustfmt`, and Python's `black`. Because the formatter rebuilds the code from the AST, the output is always canonical -- formatting the same code twice always produces the same result.

### Parenthesization

One tricky part is knowing when to add parentheses. The AST doesn't store parentheses -- it stores the expression tree structure. So `(1 + 2) * 3` becomes a multiply node with an add node as its left child.

The formatter uses a **precedence table** (the same one the parser uses!) to decide: if a child expression has lower precedence than its parent, wrap it in parentheses. So the add child (`+`, precedence 9) inside a multiply parent (`*`, precedence 10) gets parenthesized because 9 < 10.

### String Escaping

Another challenge: the AST stores decoded string values. A string literal `"hello\nworld"` becomes a `StringLiteral` node whose value contains an actual newline character. The formatter must **re-escape** these characters when outputting the string, converting the real newline back to `\n`.

## Idempotency

A good formatter is **idempotent** -- formatting already-formatted code produces the exact same output. You can run `pebble fmt` as many times as you like and the result won't change after the first time. This is an important property because it means the formatter is predictable and won't create noisy diffs.
