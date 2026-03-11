# The Parser

## What Is a Parser?

Imagine a **grammar teacher** diagramming a sentence. The teacher reads the
words (tokens) and figures out the structure: "This is the subject, this is the
verb, this is the object." The result is a diagram that shows how the words
relate to each other.

A **parser** does the same thing with code. It reads the flat list of tokens
from the lexer and builds a tree -- the [AST](ast.md) -- that shows the
structure of your program.

## Why Is Parsing Hard?

Consider this expression:

```
1 + 2 * 3
```

Is the answer 7 or 9? We know from maths class that multiplication comes
before addition, so it's 7. But a computer reading left to right would see
`1 + 2` first and might get 9.

The parser's job is to **understand the rules** and build the right tree:

```
    +           NOT          *
   / \         / \          / \
  1   *       +   3        +   3
     / \     / \          / \
    2   3   1   2        1   2
   (correct)  (wrong!)   (wrong!)
```

## Precedence: Who Goes First?

**Precedence** is a fancy word for "priority". Some operators bind tighter
than others, just like multiplication before addition in maths:

| Priority | Operators | Example |
|----------|-----------|---------|
| Highest | `-x`, `not x` (unary) | `-5`, `not true` |
| | `*`, `/`, `%` | `2 * 3` |
| | `+`, `-` | `1 + 2` |
| | `<`, `<=`, `>`, `>=` | `x > 10` |
| | `==`, `!=` | `x == 5` |
| | `and` | `a and b` |
| Lowest | `or` | `a or b` |

Operators with higher priority get "pulled in" first and end up deeper in the
tree.

## Associativity: Ties Go Left

What about `10 - 3 - 2`? Both `-` operators have the same precedence, so we
need a tiebreaker. In Pebble (like most languages), arithmetic is
**left-associative**: ties are resolved left to right.

```
10 - 3 - 2   →   (10 - 3) - 2   →   5
```

If it were right-associative, it would be `10 - (3 - 2) = 9` -- a different
answer!

## Pratt Parsing

The Pebble parser uses a technique called **Pratt parsing** (named after
Vaughan Pratt, who invented it in 1973). The core idea is simple:

1. Parse the left-hand side (a number, variable, or grouped expression)
2. Look at the next token -- is it an operator?
3. If the operator's precedence is high enough, consume it and parse the
   right-hand side
4. Repeat until you hit an operator that's too weak

This single loop handles all precedence levels and associativity correctly.
It's like a tug-of-war: stronger operators pull their operands in, while
weaker operators have to wait.

## Parentheses Override Everything

Parentheses let you override the default precedence:

```
(1 + 2) * 3
```

The parser sees `(`, recursively parses the inside as a fresh expression (with
precedence reset to zero), and then continues with `* 3`. The result is:

```
    *
   / \
  +   3
 / \
1   2
```

Addition happens first because the parentheses said so.

## What Can Go Wrong?

The parser catches mistakes like:

- **Missing closing parenthesis**: `(1 + 2` → "Expected ')'"
- **Missing operand**: `1 +` → "Expected expression"
- **Unexpected token**: `)` at the start → "Unexpected token ')'"

Each error includes the exact line and column where the problem was found.

## Function Calls

When the parser sees an identifier followed by `(`, it knows this is a
**function call**, not just a variable name. It parses the comma-separated
arguments between the parentheses and wraps everything in a `FunctionCall`
node:

```
add(1 + 2, x)  →  FunctionCall("add", [BinaryOp(1, +, 2), Identifier("x")])
```

Function calls are expressions, so they can appear anywhere an expression is
valid -- as an argument to another call, on the right side of `=`, or as part
of a larger expression like `add(1, 2) + 3`.

## Beyond Expressions

Expressions are only half the story. The parser also handles **statements** --
instructions like creating variables, printing values, and controlling the flow
of your program. See [Statements](statements.md) for the full picture.

## Summary

| Concept | Analogy |
|---------|---------|
| Parser | A grammar teacher diagramming a sentence |
| Precedence | Priority -- multiplication before addition |
| Associativity | Tiebreaker -- left to right for same priority |
| Pratt parsing | A tug-of-war where stronger operators pull first |
| Parentheses | "Do this part first!" brackets |
