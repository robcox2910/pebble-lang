# String Methods

Strings aren't just blobs of text — they come with a toolbox of **methods**
you can call using dot notation. A method is like a function that belongs to
a value: you write the value, a dot, the method name, and parentheses.

```pebble
let greeting = "  Hello, World!  "
print(greeting.strip())   # prints: Hello, World!
```

Think of it like giving instructions to the string itself: *"Hey string,
strip off your extra spaces!"*

!!! note
    Dot-notation methods work the same way on every type that supports them.
    Strings and [arrays](arrays.md) both use the `value.method()` pattern.

---

## Escape Sequences

Sometimes you need characters that you can't just type into a string —
like a newline (to start a new line) or a tab (to indent). Escape
sequences are **secret codes** that start with a backslash (`\`). The
backslash tells Pebble: *"the next character is special — don't treat
it as a normal letter."*

```pebble
print("line one\nline two")
# prints:
# line one
# line two
```

Here are all the escape sequences Pebble supports:

| Escape | What it produces           | Example output       |
| ------ | -------------------------- | -------------------- |
| `\n`   | Newline (start a new line) | `"a\nb"` → two lines |
| `\t`   | Tab (horizontal indent)    | `"a\tb"` → `a    b`  |
| `\\`   | A literal backslash        | `"a\\b"` → `a\b`     |
| `\"`   | A literal double quote     | `"say \"hi\""` → `say "hi"` |
| `\{`   | A literal brace (no interpolation) | `"\{x}"` → `{x}` |
| `\0`   | Null character             | (rarely used)        |

The `\{` escape is handy when you want a `{` in your string without
triggering [string interpolation](string-interpolation.md). See the
interpolation docs for more on that.

If you use an unknown escape like `\z`, Pebble will give you an error
right away — this catches typos early:

```pebble
print("hello\z")   # Error: Unknown escape sequence: \z
```

Escapes work inside interpolated strings too:

```pebble
let name = "Alice"
print("hello\t{name}\n")
# prints:  hello	Alice
# (followed by a blank line)
```

---

## Changing Case

### upper()

Convert every letter to UPPERCASE:

```pebble
print("hello".upper())   # prints: HELLO
```

### lower()

Convert every letter to lowercase:

```pebble
print("HELLO".lower())   # prints: hello
```

You can **chain** methods — the result of one feeds into the next:

```pebble
print("  HELLO  ".strip().lower())   # prints: hello
```

---

## Trimming Whitespace

### strip()

Remove spaces (and tabs, newlines) from both ends:

```pebble
print("   hi   ".strip())   # prints: hi
```

The characters *inside* the string are untouched — only the edges get trimmed.

---

## Splitting and Joining

### split()

Break a string into a list of pieces. With no argument it splits on
whitespace:

```pebble
let words = "one two three".split()
print(words)   # prints: [one, two, three]
```

Pass a separator to split on something specific:

```pebble
let parts = "a,b,c".split(",")
print(parts)   # prints: [a, b, c]
```

### join()

The opposite of `split` — glue a list of strings together using the target
string as the separator:

```pebble
let words = ["red", "green", "blue"]
print(", ".join(words))   # prints: red, green, blue
```

Split and join are **inverses** — splitting then joining with the same
separator gives you the original string back:

```pebble
let s = "a-b-c"
let parts = s.split("-")
print("-".join(parts))   # prints: a-b-c
```

---

## Searching

### contains()

Check if a substring exists anywhere inside the string:

```pebble
print("hello world".contains("world"))   # prints: true
print("hello world".contains("xyz"))     # prints: false
```

### starts_with()

Check if the string begins with a prefix:

```pebble
print("hello".starts_with("hel"))   # prints: true
```

### ends_with()

Check if the string ends with a suffix:

```pebble
print("hello".ends_with("llo"))   # prints: true
```

### find()

Return the index where a substring first appears, or `-1` if it's not found:

```pebble
print("banana".find("nan"))   # prints: 2
print("banana".find("xyz"))   # prints: -1
```

### count()

Count how many times a substring appears (non-overlapping):

```pebble
print("banana".count("a"))   # prints: 3
print("hello".count("ll"))   # prints: 1
```

---

## Replacing

### replace()

Replace every occurrence of one substring with another:

```pebble
print("aabbcc".replace("b", "x"))   # prints: aaxxcc
```

If the old substring isn't found, the original string is returned unchanged.

---

## Repeating

### repeat()

Repeat the string a given number of times:

```pebble
print("ha".repeat(3))   # prints: hahaha
print("=".repeat(10))   # prints: ==========
```

Passing `0` gives an empty string. Negative numbers are an error.

---

## Using Methods with Other Features

### In string interpolation

```pebble
let name = "alice"
print("Hello, {name.upper()}!")   # prints: Hello, ALICE!
```

### In conditions

```pebble
let filename = "photo.png"
if filename.ends_with(".png") {
    print("It is an image")
}
```

### In loops

```pebble
let csv = "10,20,30"
let parts = csv.split(",")
for i in range(len(parts)) {
    print(parts[i])
}
```

---

## Quick Reference

| Method             | Args     | Returns | Description                        |
| ------------------ | -------- | ------- | ---------------------------------- |
| `upper()`          | 0        | str     | Uppercase version                  |
| `lower()`          | 0        | str     | Lowercase version                  |
| `strip()`          | 0        | str     | Trimmed version                    |
| `split()`          | 0 or 1   | list    | Split into parts                   |
| `replace(old,new)` | 2        | str     | Replace all occurrences            |
| `contains(sub)`    | 1        | bool    | Is `sub` inside?                   |
| `starts_with(pre)` | 1        | bool    | Starts with `pre`?                 |
| `ends_with(suf)`   | 1        | bool    | Ends with `suf`?                   |
| `find(sub)`        | 1        | int     | Index of `sub`, or -1              |
| `count(sub)`       | 1        | int     | Occurrences of `sub`               |
| `join(list)`       | 1        | str     | Glue list items with this string   |
| `repeat(n)`        | 1        | str     | Repeat `n` times                   |

---

## How It Works Under the Hood

When you write `s.upper()`, here's the journey:

1. **Lexer** — sees the `.` and produces a `DOT` token between the
   identifier and the method name.
2. **Parser** — recognises the dot-method-parentheses pattern and builds a
   `MethodCall` AST node (target = `s`, method = `"upper"`, args = `[]`).
3. **Analyzer** — checks that `"upper"` is a known method and that you passed
   the right number of arguments.
4. **Compiler** — pushes the target onto the stack, pads any missing optional
   arguments with a sentinel value, then emits `CALL_METHOD "upper"`.
5. **VM** — pops the arguments and target, looks at the target's type to pick
   the right handler, calls it, and pushes the result back.

Think of `CALL_METHOD` like a waiter at a restaurant: you hand over your
order (the method name) and your plate (the target), and the waiter delivers
the result back to your table (the stack).
