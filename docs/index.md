# What Is a Compiler?

Imagine you only speak English, and you need to give instructions to a robot
that only understands a list of numbered steps. You'd need a **translator** who
can read your English sentences and convert them into the robot's numbered
instructions. That translator is a **compiler**.

## The Pebble Language

**Pebble** is a small programming language designed for learning. It's simple
enough to understand completely, but powerful enough to do real things:
calculate numbers, make decisions, repeat actions, and organise code into
reusable functions.

Here's what Pebble code looks like:

```
let greeting = "Hello, world!"
print(greeting)

let count = 0
while count < 5 {
    print(count)
    count = count + 1
}
```

## How a Compiler Works

A compiler reads your code and transforms it through several stages, like an
assembly line in a factory:

```mermaid
graph LR
    A[Source Code] --> B[Lexer]
    B --> C[Parser]
    C --> D[Analyzer]
    D --> E[Type Checker]
    E --> F[Compiler]
    F --> G[Optimizer]
    G --> H[Virtual Machine]
```

1. **Lexer** -- Breaks the text into small pieces called *tokens* (like
   splitting a sentence into words)
2. **Parser** -- Arranges the tokens into a tree structure that shows how they
   relate to each other (like diagramming a sentence)
3. **Analyzer** -- Checks the tree for mistakes (like a teacher proofreading
   your essay)
4. **Type Checker** -- Verifies that values are used correctly according to
   their type annotations (like checking you don't put a word where a number
   should go)
5. **Compiler** -- Translates the tree into simple numbered instructions
   called *bytecode* (like writing a recipe as step-by-step directions)
6. **Optimizer** -- Tidies up the bytecode, pre-computing answers and removing
   steps that can never run (like a smart cook who measures 200 g of flour
   instead of two separate 100 g scoops)
7. **Virtual Machine** -- Follows the instructions one by one and produces the
   result (like a cook following a recipe)

## Why Build a Compiler?

Building a compiler teaches you how programming languages *actually work*.
Every time you write Python, JavaScript, or any other language, a compiler or
interpreter is doing these same steps behind the scenes. By building one
yourself, you peek behind the curtain and see the magic trick explained.

Think of it like learning to cook instead of just ordering food -- once you
know how it works, you understand it on a completely different level.

## Our Building Blocks

| Concept | Analogy | What It Does |
|---------|---------|-------------|
| **Lexer** | Postal worker sorting letters | Break text into tokens |
| **Tokens** | Sorted Lego bricks | The pieces the parser works with |
| **Parser** | Building with Lego | Arrange tokens into a tree |
| **AST** | The assembled Lego model | A tree showing how code is structured |
| **Analyzer** | Teacher proofreading | Check for mistakes |
| **Type Checker** | Label inspector | Verify values match their types |
| **Compiler** | Recipe writer | Translate the tree into step-by-step bytecode |
| **Optimizer** | Smart cook | Remove unnecessary steps |
| **VM** | Cook following the recipe | Execute the bytecode |

## Let's Start!

Head to [Lexer](concepts/lexer.md) to see how source code gets
broken into tokens -- the first step on the assembly line.
