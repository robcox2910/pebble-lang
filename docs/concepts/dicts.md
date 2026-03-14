# Dictionaries

A **dictionary** (or **dict**) is a collection that stores **key-value pairs**.
Think of a phonebook: you look up a person's **name** (the key) and find their
**phone number** (the value). Unlike a list, where you use a numbered position,
a dict lets you use a descriptive name.

## Creating a Dict

Put key-value pairs between curly braces `{}`, with a colon `:` between each
key and value:

```pebble
let person = {"name": "Alice", "age": 12}
print(person)   # prints: {name: Alice, age: 12}
```

An empty dict has nothing between the braces:

```pebble
let empty = {}
print(empty)   # prints: {}
```

Keys must be **strings**. Values can be any type — numbers, strings, booleans,
lists, or even other dicts:

```pebble
let record = {"scores": [90, 85, 100], "passed": true}
```

## Reading a Value

Use square brackets with the **key** (a string) to look up a value:

```pebble
let d = {"name": "Alice", "age": 12}
print(d["name"])   # prints: Alice
print(d["age"])    # prints: 12
```

If you use a key that doesn't exist, Pebble stops with an error:

```pebble
print(d["email"])   # Error: Key 'email' not found in dict
```

## Changing or Adding Values

Assign to a key to change its value, or create a new key if it doesn't exist
yet:

```pebble
let d = {"name": "Alice"}
d["name"] = "Bob"      # change existing key
d["age"] = 13           # add a new key
print(d)                # prints: {name: Bob, age: 13}
```

This is called an **upsert** — it **up**dates if the key exists, or
**insert**s if it doesn't.

## Finding the Size

The built-in `len()` function tells you how many key-value pairs a dict has:

```pebble
let d = {"a": 1, "b": 2, "c": 3}
print(len(d))   # prints: 3
print(len({}))  # prints: 0
```

## Getting Keys and Values

Two built-in functions let you pull out just the keys or just the values:

```pebble
let d = {"name": "Alice", "age": 12}
print(keys(d))     # prints: [name, age]
print(values(d))   # prints: [Alice, 12]
```

Both return a **list**, so you can use them with `len()`, indexing, or loops:

```pebble
let d = {"x": 10, "y": 20, "z": 30}
let k = keys(d)
for i in range(len(k)) {
    print("{k[i]}: {d[k[i]]}")
}
```

## Checking the Type

```pebble
print(type({}))          # prints: dict
print(type({"a": 1}))   # prints: dict
```

## Dicts with Other Features

### String Interpolation

You can use dict values inside `{...}` strings:

```pebble
let person = {"name": "Alice"}
print("hello {person["name"]}")   # prints: hello Alice
```

### Functions

Dicts can be passed to and returned from functions:

```pebble
fn greet(person) {
    return "Hi, {person["name"]}!"
}
print(greet({"name": "Bob"}))   # prints: Hi, Bob!
```

### Nested Dicts

A dict value can itself be a dict:

```pebble
let data = {"user": {"name": "Alice", "age": 12}}
print(data["user"]["name"])   # prints: Alice
```

## How It Works Under the Hood

When the **compiler** sees `{"a": 1, "b": 2}`, it pushes each key and value
onto the stack in order, then emits a `BUILD_DICT 2` instruction (where 2 is
the number of key-value pairs). The **VM** pops `2 * 2 = 4` values off the
stack, pairs them up, and creates a dictionary.

For `d["name"]`, the compiler pushes the dict and the key string, then emits
`INDEX_GET`. The VM checks whether the target is a list or a dict and handles
it accordingly — for a dict it looks up the key and pushes the value.

For `d["name"] = "Bob"`, the compiler pushes the dict, key, and value, then
emits `INDEX_SET`. For a dict, the VM performs an upsert — it creates the key
if it's missing, or updates it if it already exists.

Think of `BUILD_DICT` like filling in a phonebook — you hand over names and
numbers in pairs, and get a finished phonebook back. `INDEX_GET` is looking up
a name in the phonebook, and `INDEX_SET` is writing a new entry or updating an
existing one.

### The Full Journey

Here's how `let d = {"a": 1}` travels through the pipeline:

1. **Lexer** — produces tokens: `LET`, `IDENTIFIER("d")`, `EQUAL`,
   `LEFT_BRACE`, `STRING("a")`, `COLON`, `INTEGER(1)`, `RIGHT_BRACE`
2. **Parser** — builds an `Assignment` node whose value is a `DictLiteral`
   containing one key-value pair
3. **Analyzer** — checks that all variables in keys and values are declared
4. **Compiler** — emits `LOAD_CONST 0` ("a"), `LOAD_CONST 1` (1),
   `BUILD_DICT 1`, `STORE_NAME "d"`
5. **VM** — pushes "a" and 1, packs them into a dict `{"a": 1}`, stores it
   as `d`
