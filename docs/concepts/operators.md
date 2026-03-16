# Operators

An **operator** is a symbol that tells Pebble to do something with one or
two values. You already know `+` for adding and `*` for multiplying --
Pebble has many more. Think of operators like the buttons on a calculator:
each one performs a specific action.

## Arithmetic Operators

These work on numbers (`int` and `float`). When you mix an `int` with a
`float`, the result is always a `float`.

| Operator | Name             | Example           | Result  |
|----------|------------------|-------------------|---------|
| `+`      | Addition         | `3 + 2`           | `5`     |
| `-`      | Subtraction      | `5 - 2`           | `3`     |
| `*`      | Multiplication   | `4 * 3`           | `12`    |
| `/`      | Division         | `7 / 2`           | `3.5`   |
| `//`     | Floor division   | `7 // 2`          | `3`     |
| `%`      | Modulo           | `7 % 3`           | `1`     |
| `**`     | Exponentiation   | `2 ** 3`          | `8`     |

### Division: `/` vs `//`

The `/` operator is **true division** -- it always gives you a `float`,
even when the numbers divide evenly:

```pebble
print(6 / 2)    # prints: 3.0   (always a float)
print(7 / 2)    # prints: 3.5
```

The `//` operator is **floor division** -- it rounds down to the nearest
whole number. If both inputs are `int`, the result is an `int`. If either
input is a `float`, the result is a `float`:

```pebble
print(7 // 2)     # prints: 3     (both int → int result)
print(7.0 // 2)   # prints: 3.0   (float involved → float result)
```

### Exponentiation: `**`

The `**` operator raises a number to a power. Think of `2 ** 3` as
"2 times itself 3 times" (2 × 2 × 2 = 8):

```pebble
print(2 ** 3)     # prints: 8
print(5 ** 0)     # prints: 1     (anything to the power of 0 is 1)
print(4.0 ** 0.5) # prints: 2.0   (square root!)
```

#### Right-Associativity

When you chain `**` operators, they group from **right to left**. This is
different from `+` and `*`, which group from left to right:

```pebble
# 2 ** 2 ** 3  means  2 ** (2 ** 3)  =  2 ** 8  =  256
print(2 ** 2 ** 3)    # prints: 256

# Use parentheses to change grouping:
print((2 ** 2) ** 3)  # prints: 64
```

#### Negative Exponents

A negative exponent produces a `float`:

```pebble
print(2 ** -1)   # prints: 0.5   (same as 1 / 2)
```

## Unary Operators

Unary operators work on a **single** value (unlike `+` and `*` which need
two values).

| Operator | Name        | Example   | Result  |
|----------|-------------|-----------|---------|
| `-`      | Negate      | `-5`      | `-5`    |
| `not`    | Logical NOT | `not true`| `false` |
| `~`      | Bitwise NOT | `~5`      | `-6`    |

The `-` sign binds **less tightly** than `**`, so `-2 ** 2` means
`-(2 ** 2)` = `-4`, not `(-2) ** 2` = `4`. Use parentheses if you mean
something different:

```pebble
print(-2 ** 2)     # prints: -4   (power first, then negate)
print((-2) ** 2)   # prints: 4    (negate first, then power)
```

## Comparison Operators

These compare two values and return `true` or `false`. You can compare
`int` with `float` -- Pebble handles the conversion for you:

| Operator | Name                  | Example     | Result  |
|----------|-----------------------|-------------|---------|
| `==`     | Equal to              | `3 == 3`    | `true`  |
| `!=`     | Not equal to          | `3 != 4`    | `true`  |
| `<`      | Less than             | `3 < 5`     | `true`  |
| `<=`     | Less than or equal    | `3 <= 3`    | `true`  |
| `>`      | Greater than          | `5 > 3`     | `true`  |
| `>=`     | Greater than or equal | `5 >= 5`    | `true`  |

```pebble
print(3 < 3.5)    # prints: true   (int vs float works fine)
print(3.0 == 3)   # prints: true   (same value, different types)
```

## Chained Comparisons

Sometimes you want to check whether a number falls between two values --
a **range check**. Instead of writing two comparisons joined with `and`,
Pebble lets you chain them together:

```pebble
let x = 5
print(1 < x < 10)    # prints: true   (x is between 1 and 10)
```

Under the hood, Pebble rewrites `1 < x < 10` as `(1 < x) and (x < 10)`.
Both comparisons must be true for the whole expression to be true.

### How It Works

Think of it like a sentence: "1 is less than x, which is less than 10."
If any link in the chain breaks, the whole thing is false:

```pebble
let x = 0
print(1 < x < 10)    # prints: false   (1 < 0 is false)

let x = 15
print(1 < x < 10)    # prints: false   (15 < 10 is false)
```

### Inclusive Boundaries

Use `<=` to include the boundary values:

```pebble
let x = 1
print(1 <= x <= 10)   # prints: true   (x equals the lower bound)
print(1 < x < 10)     # prints: false  (1 is not strictly less than 1)
```

### Mixing Operators

You can mix any comparison operators in a chain:

```pebble
let x = 5
print(1 <= x < 10)    # prints: true   (at least 1, but less than 10)
print(10 > x > 1)     # prints: true   (descending range check)
```

### Longer Chains

Chains can have more than two comparisons. Each pair of neighbours is
checked:

```pebble
let a = 2
let b = 5
print(1 < a < b < 10)   # prints: true   (1<2 and 2<5 and 5<10)
```

This works with all six comparison operators: `<`, `<=`, `>`, `>=`,
`==`, and `!=`.

> **Note:** The middle values in a chain are evaluated twice at runtime.
> This is fine for variables and simple expressions, which is the typical
> use case.

## Logical Operators

Logical operators combine `true` / `false` values. They're like the words
"and", "or", and "not" in English:

| Operator | Meaning                          | Example             | Result  |
|----------|----------------------------------|---------------------|---------|
| `and`    | Both must be true                | `true and false`    | `false` |
| `or`     | At least one must be true        | `true or false`     | `true`  |
| `not`    | Flip true to false (and back)    | `not true`          | `false` |

## Bitwise Operators

Bitwise operators work on the **individual bits** (the 1s and 0s) inside an
integer. They only work on `int` values -- using them on `float` or `bool`
gives an error.

Imagine each number as a row of light switches (bits). Bitwise operators
flip, combine, or shift those switches:

| Operator | Name          | Example      | Result | What it does           |
|----------|---------------|--------------|--------|------------------------|
| `&`      | Bitwise AND   | `5 & 3`      | `1`    | Both bits must be on   |
| `\|`     | Bitwise OR    | `5 \| 3`     | `7`    | Either bit can be on   |
| `^`      | Bitwise XOR   | `5 ^ 3`      | `6`    | Exactly one bit is on  |
| `~`      | Bitwise NOT   | `~5`         | `-6`   | Flip all the bits      |
| `<<`     | Left shift    | `1 << 3`     | `8`    | Slide bits left        |
| `>>`     | Right shift   | `16 >> 2`    | `4`    | Slide bits right       |

### How Bitwise AND Works (Example)

Let's see `5 & 3` step by step. First, write each number in binary:

```
5 in binary:  1 0 1
3 in binary:  0 1 1
```

AND keeps a bit only if **both** numbers have it on:

```
  1 0 1   (5)
& 0 1 1   (3)
-------
  0 0 1   (1)
```

So `5 & 3 = 1`.

### Shifting

Left shift (`<<`) slides all the bits to the left, filling empty spots with
zeros. Each shift left **doubles** the number:

```pebble
print(1 << 3)    # prints: 8    (1 → 2 → 4 → 8)
print(3 << 1)    # prints: 6    (11 in binary → 110 = 6)
```

Right shift (`>>`) does the opposite -- slides bits to the right. Each shift
right **halves** the number (rounding down):

```pebble
print(16 >> 2)   # prints: 4    (16 → 8 → 4)
```

You cannot shift by a negative amount -- that gives an error.

## Operator Precedence

When you write `2 + 3 * 4`, does Pebble compute `(2 + 3) * 4 = 20` or
`2 + (3 * 4) = 14`? **Precedence** rules decide the order, just like
the "PEMDAS" rule you might know from maths class.

Higher numbers in this table mean "do this first":

| Level | Operators            | Name             | Associativity |
|-------|----------------------|------------------|---------------|
| 12    | `-` `not` `~`        | Prefix unary     | --            |
| 11    | `**`                 | Exponentiation   | right         |
| 10    | `*` `/` `//` `%`     | Multiplicative   | left          |
| 9     | `+` `-`              | Additive         | left          |
| 8     | `<<` `>>`            | Shifts           | left          |
| 7     | `&`                  | Bitwise AND      | left          |
| 6     | `^`                  | Bitwise XOR      | left          |
| 5     | `\|`                 | Bitwise OR       | left          |
| 4     | `<` `<=` `>` `>=`    | Comparison       | left          |
| 3     | `==` `!=`            | Equality         | left          |
| 2     | `and`                | Logical AND      | left          |
| 1     | `or`                 | Logical OR       | left          |

### Examples

```pebble
# Multiplication before addition (level 10 > level 9)
print(2 + 3 * 4)         # prints: 14     (not 20)

# Power before multiplication (level 11 > level 10)
print(2 ** 3 * 2)         # prints: 16     (8 * 2, not 2 ** 6)

# Bitwise AND before bitwise OR (level 7 > level 5)
print(1 | 2 & 3)          # prints: 3      (1 | (2 & 3) = 1 | 2)

# Shifts before bitwise AND (level 8 > level 7)
print(1 & 3 << 1)         # prints: 0      (1 & (3 << 1) = 1 & 6)

# Use parentheses when in doubt!
print((2 + 3) * 4)        # prints: 20
```

### Associativity

When operators have the **same** precedence, **associativity** decides
the order. Most operators are **left-associative** (group left to right):

```pebble
# Left-associative: 10 - 3 - 2  =  (10 - 3) - 2  =  5
print(10 - 3 - 2)   # prints: 5
```

The `**` operator is the exception -- it's **right-associative** (group
right to left):

```pebble
# Right-associative: 2 ** 2 ** 3  =  2 ** (2 ** 3)  =  256
print(2 ** 2 ** 3)   # prints: 256
```

## Summary

| Concept | Analogy |
|---------|---------|
| Operator | A button on a calculator |
| `/` vs `//` | Exact sharing vs whole-piece sharing |
| `**` | "Times itself" repeated multiplication |
| Bitwise ops | Flipping individual light switches |
| `<<` / `>>` | Sliding a row of switches left or right |
| Chained comparisons | Checking if a number is between two values |
| Precedence | The order-of-operations rule from maths |
| Parentheses | "Do this part first!" |
