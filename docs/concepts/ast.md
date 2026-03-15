# The Abstract Syntax Tree (AST)

## From Bricks to a Model

In the [Tokens](tokens.md) chapter we compared tokens to Lego bricks sorted
by colour and shape. Now imagine you've finished sorting and it's time to
**build something**. You follow the instructions and snap the bricks together
into a spaceship, a house, or a dragon.

The **Abstract Syntax Tree** (or AST) is that assembled model. It's a tree-
shaped structure where each piece knows what it is and how it connects to the
pieces around it. The parser reads the flat list of tokens and builds this
tree.

## Why a Tree?

Consider this expression:

```
1 + 2 * 3
```

If you read left to right, you might think the answer is 9 (do `1 + 2` first,
then `* 3`). But maths says multiplication comes before addition, so the
answer is actually 7 (`2 * 3` first, then `1 +`).

A flat list of tokens can't show this. But a tree can:

```
    +
   / \
  1   *
     / \
    2   3
```

The `*` is deeper in the tree, so it gets evaluated first. The tree
**encodes the rules** of the language -- no ambiguity, no guessing.

## Node Types

Every piece of the tree is called a **node**. Pebble has two families of
nodes:

### Expression Nodes (produce a value)

| Node | Example | What It Holds |
|------|---------|---------------|
| `IntegerLiteral` | `42` | The number value |
| `StringLiteral` | `"hello"` | The string value |
| `BooleanLiteral` | `true` | True or false |
| `Identifier` | `score` | A variable name |
| `UnaryOp` | `-x`, `not flag` | An operator and one operand |
| `BinaryOp` | `a + b` | Left operand, operator, right operand |
| `FunctionCall` | `print(x)` | Function name and argument list |
| `StringInterpolation` | `"hi {name}"` | Text parts mixed with expressions |
| `ArrayLiteral` | `[1, 2, 3]` | A list of element expressions |
| `DictLiteral` | `{"a": 1}` | A list of key-value pair expressions |
| `IndexAccess` | `xs[0]` | A target and an index expression |

### Statement Nodes (do something)

| Node | Example | What It Holds |
|------|---------|---------------|
| `Assignment` | `let x = 42` | Variable name and initial value |
| `Reassignment` | `x = 10` | Variable name and new value |
| `PrintStatement` | `print("hi")` | The expression to print |
| `IfStatement` | `if cond { } else { }` | Condition, then-body, else-body |
| `WhileLoop` | `while cond { }` | Condition and loop body |
| `ForLoop` | `for i in range(10) { }` | Variable, iterable, loop body |
| `FunctionDef` | `fn add(a, b) { }` | Name, parameters, body |
| `ReturnStatement` | `return 42` | The value to return (or nothing) |
| `IndexAssignment` | `xs[0] = 42` | Target, index, and new value |
| `BreakStatement` | `break` | Exit the nearest loop |
| `ContinueStatement` | `continue` | Skip to the next loop iteration |
| `MatchStatement` | `match x { case 1 { } }` | Value, list of cases with patterns and bodies |
| `ImportStatement` | `import "math.pbl"` | The path to the module file |
| `FromImportStatement` | `from "utils.pbl" import add` | The path and the names to import |

The **Program** node sits at the very top and holds the list of all top-level
statements.

## Expressions vs Statements

This is a really important difference:

- An **expression** produces a value. `2 + 3` produces `5`. `"hello"` produces
  the string `hello`. You can put an expression anywhere a value is expected.

- A **statement** *does* something but doesn't produce a value you can use.
  `let x = 5` creates a variable. `print("hi")` outputs text. You can't write
  `let y = let x = 5` because `let x = 5` isn't an expression.

Think of it like this: an expression is an **answer** on a test, and a
statement is an **instruction** on a to-do list.

## Every Node Knows Where It Came From

Just like tokens, every AST node carries a **source location** (line and
column). This means if something goes wrong later -- say you try to add a
number to a string -- the compiler can point to the exact `+` in your code
and say "this is the problem".

## Frozen and Immutable

All AST nodes are **frozen** (immutable). Once the parser builds the tree,
nobody can change it. This is important because later stages of the compiler
(the analyser, the code generator) need to trust that the tree won't change
out from under them. It's like laminating a document -- once it's sealed, it
stays exactly as it is.

## A Complete Example

Here's what the AST looks like for this tiny program:

```
let x = 1 + 2
print(x)
```

```
Program
├── Assignment
│   ├── name: "x"
│   └── value: BinaryOp
│       ├── left: IntegerLiteral(1)
│       ├── operator: "+"
│       └── right: IntegerLiteral(2)
└── PrintStatement
    └── expression: Identifier("x")
```

The flat text has been transformed into a structured tree that the rest of the
compiler can walk through, node by node.
