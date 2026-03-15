# Error Handling

## When Things Go Wrong at Runtime

Imagine you're playing a video game and your character tries to open a door
that doesn't exist. The game has two choices:

1. **Crash** -- the screen goes black, game over.
2. **Handle it** -- show a message like "That door is locked" and let you
   keep playing.

Error handling is how your program does option 2. Instead of crashing when
something unexpected happens, you *catch* the problem and decide what to do
about it.

## Try / Catch

Pebble uses `try` and `catch` blocks to handle errors:

```pebble
try {
  let result = 10 / 0
} catch e {
  print("Something went wrong: {e}")
}
```

Here's what happens:

1. Pebble runs the code inside `try { }`.
2. If something goes wrong (like dividing by zero), Pebble **stops** the
   try block immediately.
3. It jumps to the `catch` block and puts the error message into the
   variable `e`.
4. Your program keeps running after the catch block -- no crash!

If nothing goes wrong, the catch block is skipped entirely.

### Catching Without a Variable

If you don't care *what* the error was, you can leave out the variable:

```pebble
try {
  let x = risky_function()
} catch {
  print("Something went wrong, but that's OK")
}
```

## Throw

You can create your own errors with `throw`:

```pebble
fn check_age(age) {
  if age < 0 {
    throw "Age cannot be negative"
  }
  return age
}

try {
  check_age(-5)
} catch e {
  print(e)
}
```

Output: `Age cannot be negative`

You can throw any value -- strings, numbers, even arrays:

```pebble
throw "something broke"
throw 42
throw [1, 2, 3]
```

If a `throw` happens and there's no `try/catch` around it, your program
crashes with an error -- just like dividing by zero would.

## Finally

Sometimes you need code that runs *no matter what* -- whether the try
block succeeded or an error was caught. That's what `finally` is for:

```pebble
try {
  print("Trying something risky...")
  throw "oops"
} catch e {
  print("Caught: {e}")
} finally {
  print("This always runs!")
}
```

Output:

```
Trying something risky...
Caught: oops
This always runs!
```

The `finally` block runs after the try block finishes normally, **and**
after a catch block handles an error. It's great for cleanup tasks.

## Catching Built-in Errors

Pebble's built-in errors (like dividing by zero or accessing an array
index that doesn't exist) can all be caught with `try/catch`:

```pebble
let xs = [10, 20, 30]

try {
  let value = xs[99]
} catch e {
  print("Oops: {e}")
}
```

Output: `Oops: Index 99 out of bounds for list of length 3`

## Errors Bubble Up

If a function throws an error (or triggers a built-in error), and that
function doesn't have its own `try/catch`, the error *bubbles up* to
whoever called it:

```pebble
fn step_one() {
  throw "broken"
}

fn step_two() {
  step_one()
}

try {
  step_two()
} catch e {
  print(e)
}
```

Output: `broken`

The error passed through `step_two` and `step_one` until it found a
`try/catch` that could handle it. Think of it like a ball bouncing up
through layers until someone catches it.

## Practical Patterns

### Safe Division

```pebble
fn safe_div(a, b) {
  try {
    return a / b
  } catch e {
    return 0
  }
}

print(safe_div(10, 2))
print(safe_div(10, 0))
```

Output:

```
5.0
0
```

### Safe Array Access

```pebble
fn get_or_default(xs, index, fallback) {
  try {
    return xs[index]
  } catch e {
    return fallback
  }
}

let colours = ["red", "green", "blue"]
print(get_or_default(colours, 1, "unknown"))
print(get_or_default(colours, 99, "unknown"))
```

Output:

```
green
unknown
```

## How It Works Under the Hood

When the compiler sees a `try` block, it emits three special bytecode
instructions:

| Opcode | What It Does |
|--------|-------------|
| `SETUP_TRY` | Push a handler onto the exception stack -- "if something goes wrong, jump here" |
| `POP_TRY` | Remove the handler -- the try block finished normally |
| `THROW` | Pop a value from the stack and trigger an exception |

When an exception happens (either from `throw` or a built-in error like
division by zero), the VM:

1. Looks at the **exception handler stack** for the nearest handler.
2. Unwinds the call stack and value stack back to where the handler was
   set up.
3. Pushes the error value onto the stack (so `catch e` can bind it).
4. Jumps to the catch block's first instruction.

If there's no handler on the stack, the exception becomes a runtime error
and the program stops.

## Summary

| Feature | Syntax | Purpose |
|---------|--------|---------|
| Try | `try { ... }` | Run code that might fail |
| Catch | `catch e { ... }` | Handle the error (variable is optional) |
| Finally | `finally { ... }` | Run cleanup code no matter what |
| Throw | `throw value` | Create your own error |
