# Enums

## A Menu of Fixed Choices

Imagine you walk into an ice-cream shop. The menu says: Chocolate,
Vanilla, or Strawberry. You can't order "Purple" -- the shop only
has the three flavors on the menu.

An **enum** (short for "enumeration") works the same way. It defines a
**fixed list of named values** -- and nothing else. If you try to use a
name that isn't on the list, Pebble catches the mistake before the
program ever runs.

Enums are perfect for things that have a small, known set of
possibilities: compass directions, traffic-light colors, days of the
week, game states, and so on.

## Defining an Enum

Use the `enum` keyword followed by a name and a list of **variants**
inside curly braces:

```pebble
enum Color { Red, Green, Blue }
```

This says: "I'm defining a new type called `Color` that has exactly
three possible values: `Red`, `Green`, and `Blue`."

Like structs and classes, the name should start with a capital letter
-- that tells readers at a glance that it's a type, not a variable.

## Using Variants

To get one of the values, write the enum name, a dot, and the variant
name:

```pebble
let c = Color.Red
```

You can't use a variant that doesn't exist:

```pebble
let c = Color.Yellow   # Error: Enum 'Color' has no variant 'Yellow'
```

## Printing and Type

Printing an enum variant shows both the enum name and the variant name,
connected by a dot:

```pebble
print(Color.Red)         # prints: Color.Red
print(type(Color.Red))   # prints: Color
```

The `type()` function returns the enum's name as a string -- just like
`type()` returns `"Point"` for a struct instance.

## Comparing Enum Values

Two enum variants are **equal** if they have the same enum name *and*
the same variant name:

```pebble
let c = Color.Red
print(c == Color.Red)     # prints: true
print(c == Color.Green)   # prints: false
print(c != Color.Green)   # prints: true
```

You can use `==` and `!=` in `if` conditions too:

```pebble
if c == Color.Red {
    print("it's red!")
}
```

## Match/Case with Enums

Enums shine brightest with `match/case`. Instead of writing a chain of
`if/else if/else`, you list each variant as a case:

```pebble
enum Direction { Up, Down, Left, Right }

let d = Direction.Left

match d {
    case Direction.Up    { print("going up") }
    case Direction.Down  { print("going down") }
    case Direction.Left  { print("going left") }
    case Direction.Right { print("going right") }
    case _ { print("unknown") }
}
# prints: going left
```

The `case _` wildcard at the end is required -- Pebble needs to know
that every possible value is handled.

## Enums as Values

Enum variants are first-class values. You can store them in variables,
pass them to functions, put them in lists and dicts, and use them in
string interpolation:

```pebble
enum Color { Red, Green, Blue }

# In a list
let palette = [Color.Red, Color.Green, Color.Blue]
print(palette[0])   # prints: Color.Red

# In a dict
let favorites = {"sky": Color.Blue, "grass": Color.Green}
print(favorites["sky"])   # prints: Color.Blue

# In string interpolation
let c = Color.Red
print("my color is {c}")   # prints: my color is Color.Red
```

## You Can't Call an Enum

Enums are **not** constructors -- they don't take arguments. Writing
`Color()` is an error:

```pebble
Color()   # Error: 'Color' is an enum, not a function
```

To get a value, always use dot syntax: `Color.Red`.

## Practical Examples

### Traffic Light

```pebble
enum Light { Red, Yellow, Green }

fn describe(light) {
    match light {
        case Light.Red    { return "stop" }
        case Light.Yellow { return "caution" }
        case Light.Green  { return "go" }
        case _ { return "unknown" }
    }
}

print(describe(Light.Red))      # prints: stop
print(describe(Light.Green))    # prints: go
```

### Game State

```pebble
enum State { Menu, Playing, Paused, GameOver }

let current = State.Menu
print(current)   # prints: State.Menu

current = State.Playing
print(current)   # prints: State.Playing
```

## How It Works Under the Hood

### Defining an Enum

Like structs, `enum Color { Red, Green, Blue }` emits **no bytecode**.
The compiler stores metadata -- the enum name and its variant list --
and passes it along to the VM.

### Accessing a Variant

`Color.Red` compiles to a single instruction:

1. `LOAD_ENUM_VARIANT` -- constructs an `EnumVariant` value with the
   enum name `"Color"` and variant name `"Red"`, and pushes it onto
   the stack.

Because the compiler knows `Color` is an enum (not a struct or
variable), it intercepts `Color.Red` at compile time and emits
`LOAD_ENUM_VARIANT` instead of the usual `LOAD_NAME` + `GET_FIELD`
pair.

### Equality

`EnumVariant` is a frozen dataclass, so Python gives it `==` and
`hash` for free. Two variants are equal when both the enum name and
variant name match -- the VM's regular `EQUAL` opcode handles this
automatically.

### Match/Case

In a match pattern like `case Color.Red`, the compiler emits:

1. `LOAD_NAME "$match_0"` -- push the value being matched.
2. `LOAD_ENUM_VARIANT` -- push `Color.Red`.
3. `EQUAL` -- compare them.
4. `JUMP_IF_FALSE` -- skip to the next case if they don't match.

This is the same strategy used for literal patterns, just with enum
variants instead of numbers or strings.

## Summary

| Syntax                        | What it does                                |
| ----------------------------- | ------------------------------------------- |
| `enum Name { A, B, C }`      | Define a new enum with three variants       |
| `Name.A`                      | Access variant `A` of enum `Name`           |
| `print(Name.A)`               | Prints `Name.A`                             |
| `type(Name.A)`                | Returns `"Name"` (the enum's name)          |
| `a == b`                      | True if same enum and same variant          |
| `case Name.A { ... }`        | Match an enum variant in match/case         |
| `LOAD_ENUM_VARIANT`           | VM instruction: push an enum variant value  |
