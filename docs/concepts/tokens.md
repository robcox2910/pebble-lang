# Tokens

## What Is a Token?

Imagine you have a big box of **Lego bricks**. Before you can build anything,
you need to sort them: red bricks in one pile, blue bricks in another, flat
pieces here, wheels there. Once they're sorted, you know exactly what you have
to work with.

A **token** is a sorted Lego brick. The compiler reads your source code --
which is just a long string of characters -- and sorts each piece into a
labelled category. The number `42` becomes an "integer token". The word `let`
becomes a "keyword token". The symbol `+` becomes an "operator token".

This sorting step is called **tokenization** (or *lexical analysis*, if you
want the fancy name), and the program that does it is called a **lexer**.

## Why Not Just Read Characters?

You *could* try to understand code one character at a time, but it would be
like trying to read a book one letter at a time instead of one word at a time.
By grouping characters into tokens first, the rest of the compiler can think in
terms of whole words and symbols, which is much easier.

## Token Categories

Pebble groups its tokens into several families:

### Literals -- The Raw Values

These are the actual data values in your code:

| Token | Example | What It Means |
|-------|---------|---------------|
| `INTEGER` | `42` | A whole number |
| `FLOAT` | `3.14` | A number with a decimal point |
| `STRING` | `"hello"` | A piece of text |
| `IDENTIFIER` | `score` | A name you gave to something |

When a string contains `{...}` interpolation (like `"hello {name}"`), the lexer
splits it into special tokens instead of a plain `STRING`:

| Token | Example piece | What It Means |
|-------|--------------|---------------|
| `STRING_START` | `"hello "` | The text before the first `{` |
| `STRING_MIDDLE` | `" and "` | Text between two `{...}` sections |
| `STRING_END` | `"!"` | The text after the last `}` |

### Keywords -- Reserved Words

Keywords are special words that Pebble has claimed for itself. You can't use
them as variable names because they already mean something:

| Token | Word | What It Does |
|-------|------|--------------|
| `LET` | `let` | Declare a new variable |
| `IF` | `if` | Start a conditional branch |
| `ELSE` | `else` | The alternative branch |
| `WHILE` | `while` | Start a loop |
| `FOR` | `for` | Start a counting loop |
| `IN` | `in` | Used with `for` loops |
| `FN` | `fn` | Define a function |
| `RETURN` | `return` | Send a value back from a function |
| `BREAK` | `break` | Exit a loop early |
| `CONTINUE` | `continue` | Skip to the next loop iteration |
| `TRUE` | `true` | The boolean value true |
| `FALSE` | `false` | The boolean value false |
| `AND` | `and` | Logical "both must be true" |
| `OR` | `or` | Logical "at least one must be true" |
| `NOT` | `not` | Logical "flip true to false" |
| `MATCH` | `match` | Start a pattern-matching block |
| `CASE` | `case` | Define one arm of a match block |
| `IMPORT` | `import` | Bring definitions in from another file |
| `FROM` | `from` | Choose which file to import from |

### Operators -- The Action Symbols

Operators tell Pebble to *do* something with values:

| Token | Symbol | What It Does |
|-------|--------|--------------|
| `PLUS` | `+` | Add two numbers |
| `MINUS` | `-` | Subtract (or negate) |
| `STAR` | `*` | Multiply |
| `SLASH` | `/` | True division (always returns a float) |
| `SLASH_SLASH` | `//` | Floor division (rounds down) |
| `PERCENT` | `%` | Remainder after division |
| `STAR_STAR` | `**` | Exponentiation (raise to a power) |
| `AMPERSAND` | `&` | Bitwise AND |
| `PIPE` | `\|` | Bitwise OR |
| `CARET` | `^` | Bitwise XOR |
| `TILDE` | `~` | Bitwise NOT |
| `LESS_LESS` | `<<` | Left shift |
| `GREATER_GREATER` | `>>` | Right shift |

### Comparisons -- Asking Questions

These produce `true` or `false` answers:

| Token | Symbol | Question |
|-------|--------|----------|
| `EQUAL_EQUAL` | `==` | Are these the same? |
| `BANG_EQUAL` | `!=` | Are these different? |
| `LESS` | `<` | Is the left smaller? |
| `LESS_EQUAL` | `<=` | Is the left smaller or equal? |
| `GREATER` | `>` | Is the left bigger? |
| `GREATER_EQUAL` | `>=` | Is the left bigger or equal? |

### Delimiters -- The Punctuation

These are the brackets, braces, and commas that organise your code:

| Token | Symbol | Purpose |
|-------|--------|---------|
| `LEFT_PAREN` | `(` | Start a group or function call |
| `RIGHT_PAREN` | `)` | End a group or function call |
| `LEFT_BRACE` | `{` | Start a block of code |
| `RIGHT_BRACE` | `}` | End a block of code |
| `LEFT_BRACKET` | `[` | Start a list or index access |
| `RIGHT_BRACKET` | `]` | End a list or index access |
| `COMMA` | `,` | Separate items in a list |
| `COLON` | `:` | Separate key from value (or annotate a type) |
| `EQUAL` | `=` | Assign a value |
| `ARROW` | `->` | Separate parameters from return type |

### Special Tokens

| Token | What It Means |
|-------|---------------|
| `NEWLINE` | End of a statement (like a full stop) |
| `EOF` | End of the file -- there's nothing left to read |

## A Token Has Three Parts

Every token carries three pieces of information:

1. **Kind** -- What category is it? (`INTEGER`, `PLUS`, `LET`, etc.)
2. **Value** -- What was the original text? (`"42"`, `"+"`, `"let"`)
3. **Location** -- Where in the source file did it appear? (line 3, column 5)

The location is important for error messages. If something goes wrong, the
compiler can point to the exact spot in your code and say "the problem is
*here*".

## Example

Given this Pebble code:

```
let x = 42
```

The lexer produces these tokens:

| Kind | Value | Line | Column |
|------|-------|------|--------|
| `LET` | `let` | 1 | 1 |
| `IDENTIFIER` | `x` | 1 | 5 |
| `EQUAL` | `=` | 1 | 7 |
| `INTEGER` | `42` | 1 | 9 |
| `NEWLINE` | `\n` | 1 | 11 |
| `EOF` | | 1 | 12 |

Notice how the raw text `let x = 42` has been broken into six clearly labelled
pieces. Each one knows exactly what it is and where it came from. The parser
(which we'll meet next) can now work with these tidy, sorted bricks instead of
raw characters.
