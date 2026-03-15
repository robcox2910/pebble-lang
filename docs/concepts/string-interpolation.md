# String Interpolation

Sometimes you want to mix text with values in a single string. Instead of
joining pieces together with `+`, Pebble lets you put expressions right
inside the string using curly braces `{…}`.

## How It Works

Wrap any expression in `{` and `}` inside a double-quoted string:

```pebble
let name = "Alice"
print("hello {name}")   # prints: hello Alice
```

Pebble evaluates the expression, converts the result to text, and slots
it into the string at that position.

## Multiple Values

You can have as many `{…}` sections as you like in one string:

```pebble
let a = 3
let b = 4
print("{a} + {b} = {a + b}")   # prints: 3 + 4 = 7
```

## Any Expression Works

The bit inside the braces can be any Pebble expression — a variable, a
number, a calculation, even a function call:

```pebble
fn double(n) { return n * 2 }
print("double of 5 is {double(5)}")   # prints: double of 5 is 10
```

Values are automatically turned into text:

| Type    | Example        | Text     |
|---------|---------------|----------|
| Integer | `{42}`        | `42`     |
| Float   | `{3.14}`      | `3.14`   |
| String  | `{"hi"}`      | `hi`     |
| Boolean | `{true}`      | `true`   |

## Literal Braces

If you actually want a `{` character in your string (not interpolation),
put a backslash before it:

```pebble
print("use \{braces}")   # prints: use {braces}
```

## How It Works Under the Hood

When the **lexer** sees `{` inside a string, it splits the string into
segments:

```
"hello {name} end"
```

becomes the token sequence:

```
STRING_START("hello ")   →   IDENTIFIER(name)   →   STRING_END(" end")
```

The **parser** collects these into a `StringInterpolation` node. The
**compiler** emits code to push each part onto the stack, then a
`BUILD_STRING` instruction that pops them all and joins them into one
string.

Think of it like making a sandwich: each ingredient is stacked up, then
`BUILD_STRING` squashes them all together into one finished sandwich.
