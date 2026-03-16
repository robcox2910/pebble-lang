# Higher-Order Functions

A **higher-order function** is a function that takes another function as an
argument. Pebble has three built-in higher-order functions: `map`, `filter`,
and `reduce`.

Think of them like machines on an assembly line:

- **map** — a machine that transforms every item on the belt
- **filter** — a quality inspector that removes items that don't pass a test
- **reduce** — a machine that combines all the items into one final product

## First-Class Functions

Before we can pass functions around, we need to understand that in Pebble,
**all functions are values** — just like numbers and strings. You can store a
function in a variable, put it in a list, or pass it to another function:

```pebble
fn double(x) { return x * 2 }

let f = double
print(f(5))         # prints: 10
print(type(double))  # prints: fn
```

You can also write **anonymous functions** — functions with no name — directly
where you need them:

```pebble
let triple = fn(x) { return x * 3 }
print(triple(4))   # prints: 12
```

Anonymous functions are handy when you need a quick throwaway function,
especially with `map`, `filter`, and `reduce`.

## map(fn, list)

Apply a function to **every** element of a list and collect the results:

```pebble
let result = map(fn(x) { return x * 2 }, [1, 2, 3])
print(result)   # prints: [2, 4, 6]
```

Think of `map` like a cookie cutter. You have a tray of dough pieces (the
input list) and a cutter (the function). The cutter stamps each piece into a
new shape, and you get a new tray of shaped cookies (the output list).

You can use a named function too:

```pebble
fn square(x) { return x * x }
print(map(square, [1, 2, 3, 4]))   # prints: [1, 4, 9, 16]
```

If the list is empty, you get an empty list back:

```pebble
print(map(fn(x) { return x }, []))   # prints: []
```

## filter(fn, list)

Keep only the elements where the function returns `true`:

```pebble
let result = filter(fn(x) { return x > 2 }, [1, 2, 3, 4, 5])
print(result)   # prints: [3, 4, 5]
```

Think of `filter` like a sieve. You pour a mixture through it, and only the
pieces that fit through the holes (pass the test) come out the other side.

```pebble
fn is_even(x) { return x % 2 == 0 }
print(filter(is_even, [1, 2, 3, 4, 5, 6]))   # prints: [2, 4, 6]
```

If nothing passes the test, you get an empty list:

```pebble
print(filter(fn(x) { return x > 100 }, [1, 2, 3]))   # prints: []
```

## reduce(fn, list, initial)

Combine all elements of a list into a single value by repeatedly applying a
function. The function takes two arguments: an **accumulator** (a running
total that builds up the answer as you go through the list -- think of it like
a snowball rolling downhill, getting bigger with each step) and the current
element.

```pebble
let sum = reduce(fn(acc, x) { return acc + x }, [1, 2, 3, 4], 0)
print(sum)   # prints: 10
```

Here's what happens step by step:

1. Start with `acc = 0` (the initial value)
2. `acc = 0 + 1` = `1`
3. `acc = 1 + 2` = `3`
4. `acc = 3 + 3` = `6`
5. `acc = 6 + 4` = `10`

Think of `reduce` like a snowball rolling down a hill. It starts small (the
initial value), and each element it rolls over gets packed into the ball,
making it bigger.

You can compute anything with `reduce` — sums, products, even build strings:

```pebble
fn multiply(a, b) { return a * b }
print(reduce(multiply, [2, 3, 4], 1))   # prints: 24
```

If the list is empty, you just get the initial value back:

```pebble
print(reduce(fn(a, b) { return a + b }, [], 42))   # prints: 42
```

## Chaining Together

The real power comes when you combine these functions. Since each one returns
a value, you can feed the result of one directly into another:

```pebble
fn double(x) { return x * 2 }
fn is_even(x) { return x % 2 == 0 }
fn add(a, b) { return a + b }

# First filter the evens, then double them, then sum them up
let nums = [1, 2, 3, 4, 5, 6]
let result = reduce(add, map(double, filter(is_even, nums)), 0)
print(result)   # prints: 24
```

Reading from the inside out:

1. `filter(is_even, nums)` keeps `[2, 4, 6]`
2. `map(double, [2, 4, 6])` transforms to `[4, 8, 12]`
3. `reduce(add, [4, 8, 12], 0)` sums to `24`

## Using Closures

Higher-order functions work beautifully with closures that capture variables:

```pebble
fn make_multiplier(factor) {
    fn multiply(x) { return x * factor }
    return multiply
}

let times3 = make_multiplier(3)
print(map(times3, [1, 2, 3, 4]))   # prints: [3, 6, 9, 12]
```

The closure `times3` remembers `factor = 3` from when it was created.

## Error Handling

All three functions check their arguments at runtime:

- The first argument must be a function (a closure). Passing a number or
  string gives an error.
- The second argument must be a list. Passing anything else gives an error.

```pebble
map(42, [1, 2])         # Error: map() expects a function
filter(fn(x) { return true }, "abc")  # Error: filter() expects a list
```

## How It Works Under the Hood

Unlike simple builtins like `len()` or `push()`, the higher-order functions
need to **call back into user code** for each element. This means they can't
be plain Python functions — they need access to the VM's execution machinery.

Here's how it works:

1. **VM-level builtins** — `map`, `filter`, and `reduce` are implemented as
   methods on the `VirtualMachine` class itself, not as standalone handler
   functions. This gives them access to the VM's stack and frame management.

2. **`_call_callable` helper** — A method that takes a closure and some
   arguments, sets up a new call frame, runs the VM's execution loop until
   that frame completes, and returns the result.

3. **Nested execution** — The `_execute` method accepts a `min_depth`
   parameter. Normally it runs until the call stack is empty. For callbacks,
   it runs until the stack depth drops back to where it was before the
   callback was pushed — like a mini VM session inside the main one.

```
Main execution loop
  ├─ ... instructions ...
  ├─ CALL map
  │   ├─ _call_callable(fn, [1])  ← mini execution
  │   │   ├─ push frame
  │   │   ├─ _execute(min_depth=2)
  │   │   ├─ RETURN → pop frame
  │   │   └─ return result
  │   ├─ _call_callable(fn, [2])  ← mini execution
  │   └─ push result list
  └─ ... continue ...
```

This design means any closure — including ones that capture variables from
outer scopes — works correctly as a callback.
