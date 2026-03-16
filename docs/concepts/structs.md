# Structs

## The Custom Blueprint

Imagine you're building with LEGO. You've been using single bricks
(numbers, strings, booleans) and bags of bricks (lists). But what if
you want to build something more specific -- like a little LEGO car
with a **color**, a **speed**, and a **name**? You'd want a blueprint
that says: "every car I build has these three labeled compartments."

A **struct** is exactly that -- a blueprint for a custom box with
labeled compartments (called **fields**). You define the blueprint
once, then create as many boxes as you want from it.

## Defining a Struct

Use the `struct` keyword followed by a name and a list of field names
inside curly braces:

```pebble
struct Point { x, y }
```

This says: "I'm defining a new type called `Point` that has two fields,
`x` and `y`."

The name should start with a capital letter (like `Point`, `Color`,
`Student`) -- that's how Pebble programmers tell struct types apart
from regular variables at a glance.

## Creating Instances

Once you have a blueprint, you create a concrete value by calling the
struct name like a function, passing one value for each field:

```pebble
struct Point { x, y }

let p = Point(10, 20)
```

The arguments are **positional** -- the first value goes to the first
field, the second to the second, and so on. If you pass the wrong
number of arguments, Pebble reports an error before the program even
runs.

## Reading Fields

Use a dot (`.`) to read a field:

```pebble
print(p.x)   # prints: 10
print(p.y)   # prints: 20
```

Think of the dot as opening a specific compartment by its label.

## Changing Fields

Use dot-equals to write a new value into a field:

```pebble
p.x = 30
print(p.x)   # prints: 30
```

Fields are always changeable -- even if the variable holding the
struct is declared with `const`. That's the same rule Pebble uses for
lists: `const` means you can't point the name at a different value,
but you *can* still change what's inside.

```pebble
const origin = Point(0, 0)
origin.x = 5   # this is fine -- modifying the contents, not the binding
```

## Printing Structs

`print()` knows how to display a struct with all its fields:

```pebble
let p = Point(10, 20)
print(p)   # prints: Point(x=10, y=20)
```

## Checking the Type

The `type()` function returns the struct's name as a string:

```pebble
print(type(p))   # prints: Point
```

## Structs as Values

Struct instances are values just like numbers or strings. You can:

**Pass them to functions:**

```pebble
fn distance_from_origin(point) {
    return (point.x ** 2 + point.y ** 2) ** 0.5
}
print(distance_from_origin(Point(3, 4)))   # prints: 5.0
```

**Return them from functions:**

```pebble
fn origin() {
    return Point(0, 0)
}
```

**Store them in lists:**

```pebble
let points = [Point(1, 2), Point(3, 4), Point(5, 6)]
print(points[0].x)   # prints: 1
```

**Store them in dictionaries:**

```pebble
let locations = {"home": Point(0, 0), "school": Point(10, 5)}
print(locations["school"].y)   # prints: 5
```

**Nest them inside other structs:**

```pebble
struct Line { start, end }

let line = Line(Point(0, 0), Point(10, 10))
print(line.start.x)   # prints: 0
print(line.end.y)      # prints: 10
```

## Comparing Structs

Two struct instances are **equal** if they have the same type name
*and* the same field values:

```pebble
let a = Point(10, 20)
let b = Point(10, 20)
print(a == b)   # prints: true

let c = Point(10, 30)
print(a == c)   # prints: false
```

Different struct types are never equal, even if they have the same
field values:

```pebble
struct Vec { x, y }
let p = Point(10, 20)
let v = Vec(10, 20)
print(p == v)   # prints: false
```

## Error Cases

Pebble catches mistakes early:

```pebble
# Wrong number of arguments
let p = Point(1)          # Error: expects 2 arguments, got 1

# Accessing a field that doesn't exist
print(p.z)                # Error: has no field 'z'

# Setting a field that doesn't exist
p.z = 5                   # Error: has no field 'z'

# Using dot on a non-struct
let x = 42
print(x.y)                # Error: not a struct

# Duplicate field name
struct Bad { x, x }       # Error: Duplicate field 'x'
```

## Practical Examples

### RGB Color

```pebble
struct Color { r, g, b }

let red = Color(255, 0, 0)
let blue = Color(0, 0, 255)
print(red)    # prints: Color(r=255, g=0, b=0)
print(blue)   # prints: Color(r=0, g=0, b=255)
```

### Student Record

```pebble
struct Student { name, age, grade }

let alice = Student("Alice", 12, "A")
print(alice.name)    # prints: Alice
print(alice.grade)   # prints: A

alice.grade = "A+"
print(alice)   # prints: Student(name=Alice, age=12, grade=A+)
```

### Linked List Node

```pebble
struct Node { value, next }

let list = Node(1, Node(2, Node(3, 0)))
print(list.value)              # prints: 1
print(list.next.value)         # prints: 2
print(list.next.next.value)    # prints: 3
```

## How It Works Under the Hood

### Defining a Struct

When the compiler sees `struct Point { x, y }`, it **does not** emit
any bytecode. Instead, it stores metadata: the struct name and its
ordered field list. This metadata travels with the compiled program to
the VM.

### Constructing an Instance

When the VM encounters `CALL "Point"`, it checks its struct registry.
If the name matches, it:

1. Pops the right number of values from the stack (one per field).
2. Builds a `StructInstance` with those values.
3. Pushes the instance onto the stack.

No special opcode needed -- the existing `CALL` opcode handles it.

### Reading a Field

`p.x` compiles to:

1. `LOAD_NAME "p"` -- push the struct instance onto the stack.
2. `GET_FIELD "x"` -- pop the instance, look up field `"x"`, push its
   value.

### Writing a Field

`p.x = 30` compiles to:

1. `LOAD_NAME "p"` -- push the struct instance.
2. `LOAD_CONST 30` -- push the new value.
3. `SET_FIELD "x"` -- pop both, update the field in place.

## Structs, Classes, and Enums

Pebble has three ways to define custom types:

- **Struct** -- a container for related data fields (this chapter).
- **Class** -- a struct that can also have methods.
  See [Classes](classes.md).
- **Enum** -- a fixed set of named values (not a data container).
  See [Enums](enums.md).

If you just need to group data, use a struct. If your data needs to
*do things*, use a class. If you have a small, known set of options
(like colours or directions), use an enum.

## Summary

| Syntax                  | What it does                                |
| ----------------------- | ------------------------------------------- |
| `struct Name { a, b }`  | Define a new struct type with fields a, b   |
| `Name(1, 2)`            | Create an instance (like a function call)   |
| `inst.field`            | Read a field value                          |
| `inst.field = expr`     | Write a new value to a field                |
| `type(inst)`            | Returns the struct's type name as a string  |
| `print(inst)`           | Displays `Name(field=value, ...)`           |
| `a == b`                | True if same type and all fields match      |
| `GET_FIELD "name"`      | VM instruction: pop instance, push field    |
| `SET_FIELD "name"`      | VM instruction: pop value + instance, write |
