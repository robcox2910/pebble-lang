# Pattern Matching

## Sorting Values into Boxes

Imagine you have a pile of letters and a row of labelled boxes. You pick
up each letter, read the label, and drop it into the matching box:

- Letter says "Bills" -- goes in the Bills box.
- Letter says "Birthday" -- goes in the Birthday box.
- Letter says anything else -- goes in the "Other" box.

Pattern matching in Pebble works the same way. You give it a value, and
it checks each **case** until it finds one that matches.

## Basic Syntax

```pebble
match value {
    case 1 {
        print("one")
    }
    case 2 {
        print("two")
    }
    case _ {
        print("something else")
    }
}
```

Here's what happens:

1. Pebble evaluates the value after `match`.
2. It checks each `case` from top to bottom.
3. When it finds a match, it runs that case's body and **stops** -- no
   other cases are checked.
4. The last case must be a catch-all (`_` or `let`) so nothing slips
   through.

## Pattern Types

Pebble supports four kinds of patterns.

### Literal Patterns

Match an exact value -- a number, string, or boolean:

```pebble
let day = "Monday"

match day {
    case "Saturday" {
        print("Weekend!")
    }
    case "Sunday" {
        print("Weekend!")
    }
    case _ {
        print("Weekday")
    }
}
```

You can also match negative numbers:

```pebble
match temperature {
    case -1 {
        print("Almost freezing")
    }
    case 0 {
        print("Freezing point")
    }
    case _ {
        print("Something else")
    }
}
```

### Wildcard Pattern

The underscore `_` matches **anything** without saving the value.
Think of it as the "Other" box that catches everything:

```pebble
match colour {
    case "red" {
        print("Stop!")
    }
    case "green" {
        print("Go!")
    }
    case _ {
        print("Unknown colour")
    }
}
```

### Capture Pattern

Like a wildcard, but it **saves** the value into a variable so you
can use it in the case body:

```pebble
match score {
    case 100 {
        print("Perfect!")
    }
    case let s {
        print("You scored: {s}")
    }
}
```

The variable `s` only exists inside that case's braces -- it
disappears once the case body finishes.

### OR Pattern

Match any of several values at once, separated by `|`:

```pebble
match day {
    case "Saturday" | "Sunday" {
        print("Weekend!")
    }
    case _ {
        print("Weekday")
    }
}
```

This is much cleaner than writing the same body twice. OR patterns
only work with literal values.

## Exhaustiveness

Pebble requires every match to be **exhaustive** -- the last case must
be a wildcard (`_`) or a capture (`let x`) that catches anything not
handled above. This catches mistakes at compile time:

```pebble
# This is an ERROR -- what if x is 3?
match x {
    case 1 { print("one") }
    case 2 { print("two") }
}
```

The compiler will tell you:

```
Match must end with a wildcard or capture pattern for exhaustiveness
```

## Match vs If/Else

Pattern matching is like a cleaner version of long `if`/`else` chains.
Compare:

```pebble
// With if/else
if x == 1 {
    print("one")
} else if x == 2 or x == 3 {
    print("two or three")
} else {
    print("other")
}

// With match
match x {
    case 1 {
        print("one")
    }
    case 2 | 3 {
        print("two or three")
    }
    case _ {
        print("other")
    }
}
```

Match is especially nice when you have many values to check -- each
case reads clearly, and the exhaustiveness check makes sure you haven't
forgotten anything.

## Practical Examples

### Classifying Numbers

```pebble
fn classify(n) {
    match n {
        case 0 {
            return "zero"
        }
        case 1 {
            return "one"
        }
        case let x {
            return "other"
        }
    }
}

print(classify(0))
print(classify(1))
print(classify(42))
```

Output:

```
zero
one
other
```

### Match Inside a Loop

```pebble
for i in range(4) {
    match i {
        case 0 { print("start") }
        case 1 | 2 { print("middle") }
        case _ { print("end") }
    }
}
```

Output:

```
start
middle
middle
end
```

## How It Works Under the Hood

The compiler turns a `match` statement into a chain of equality tests
using a hidden temporary variable. No new opcodes are needed -- it
reuses the same instructions as `if`/`else`.

| Step | What happens |
|------|-------------|
| 1. Evaluate | The value expression is computed and stored in a hidden variable (`$match_0`) |
| 2. Test | Each case loads the hidden variable and compares it to the pattern |
| 3. Jump | If the test fails, jump to the next case |
| 4. Execute | If the test passes, run the case body and jump to the end |
| 5. Catch-all | The last case (wildcard/capture) runs if nothing else matched |

For OR patterns, the compiler chains multiple equality tests with `OR`
instructions -- if any alternative matches, the case body runs.

## Summary

| Pattern | Syntax | Matches | Saves value? |
|---------|--------|---------|-------------|
| Literal | `case 42` | Exact value | No |
| Wildcard | `case _` | Anything | No |
| Capture | `case let x` | Anything | Yes -- into `x` |
| OR | `case 1 \| 2 \| 3` | Any of those | No |
