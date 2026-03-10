# Error Messages

## Why Do Errors Matter?

Imagine you're doing a maths test and your teacher marks one answer wrong --
but doesn't tell you *which* question, *which* part, or *what* went wrong.
Frustrating, right?

A good compiler is like a helpful teacher. When something goes wrong, it
doesn't just say "Error!" -- it circles the exact mistake on your homework,
underlines the word, and explains what it expected instead.

## The Pebble Error System

Pebble has a family of error types, one for each stage of the compiler:

| Error Type | When It Happens | Example |
|------------|----------------|---------|
| **LexerError** | Scanning characters | Unterminated string `"hello` |
| **ParseError** | Arranging tokens into a tree | Missing closing `)` |
| **SemanticError** | Checking the tree for logic mistakes | Using a variable that doesn't exist |
| **PebbleRuntimeError** | Running the bytecode | Dividing by zero |

All of them are part of the same family (they inherit from `PebbleError`), so
the compiler can catch *any* Pebble error when it needs to.

## Anatomy of an Error

Every Pebble error carries three pieces of information:

1. **Message** -- What went wrong, in plain English
2. **Line** -- Which line of your code has the problem
3. **Column** -- Which column (character position) on that line

## The Caret Pointer

When Pebble reports an error, it shows you the broken line from your source
code and draws a little arrow (`^`) pointing to the exact spot:

```
1 | let x = @
        ^
Unexpected character '@'
```

This is like a teacher using a red pen to circle the mistake. You don't have to
hunt through your whole program -- the compiler shows you right where to look.

Here's one from line 3 of a longer program:

```
3 | print(x + )
               ^
Expected expression after '+'
```

## Collecting Multiple Errors

Some compilers stop at the first error they find. That's like a teacher who
reads one sentence of your essay, finds a spelling mistake, and hands it
straight back without reading the rest.

Pebble's **ErrorCollector** is smarter. It gathers up all the errors it can
find and reports them all at once. That way, you can fix several mistakes in one
go instead of playing whack-a-mole -- fix one, run again, find the next, fix
it, run again...

```
1 | let x = @
            ^
Unexpected character '@'

3 | print(y
            ^
Expected ')' after argument
```

Two errors, reported together. Much more efficient!

## Summary

| Concept | Analogy |
|---------|---------|
| Error message | A teacher circling mistakes on your homework |
| Line & column | "Page 3, second paragraph, fifth word" |
| Caret pointer | A red arrow drawn under the mistake |
| ErrorCollector | Marking all mistakes at once, not just the first |
