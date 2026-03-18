# Bytecode Debugger

## What Is a Debugger?

Imagine you're following a recipe but something tastes wrong. You could cook
the whole thing again from scratch — or you could go through it step by step,
tasting after each ingredient, to find exactly where the problem is.

A **debugger** does the same thing for code. Instead of running your whole
program at once, it lets you pause at each step, look around at what values
your variables hold, and decide when to move forward.

## Starting the Debugger

Add the `--debug` flag when running a Pebble file:

```
$ pebble --debug examples/hello.pbl
  1: let name = "World"
(pdb)
```

The program pauses at the very first line and shows you the `(pdb)` prompt.
That's where you type debugger commands.

## Commands

| Command      | Short | What it does                        |
|-------------|-------|-------------------------------------|
| `step`      | `s`   | Go to the next source line          |
| `istep`     | `n`   | Go to the next bytecode instruction |
| `continue`  | `c`   | Run until the next breakpoint       |
| `break 5`   | `b 5` | Set a breakpoint at line 5          |
| `clear 5`   |       | Remove the breakpoint at line 5     |
| `print x`   | `p x` | Show the value of variable `x`      |
| `locals`    |       | Show all local variables            |
| `stack`     |       | Show the operand stack              |
| `backtrace` | `bt`  | Show the call stack with line numbers|
| `list`      | `l`   | Show source code around current line|
| `help`      | `h`   | Show all commands                   |
| `quit`      | `q`   | Stop the program                    |

## Step-by-Step Example

Say you have this program saved as `add.pbl`:

```
let x = 3
let y = 7
print(x + y)
```

Here's what a debugging session looks like:

```
$ pebble --debug add.pbl
  1: let x = 3
(pdb) s
  2: let y = 7
(pdb) print x
x = 3
(pdb) s
  3: print(x + y)
(pdb) print y
y = 7
(pdb) locals
  x = 3
  y = 7
(pdb) s
10
```

Each `s` (step) command moves to the next source line. Between steps you can
inspect variables with `print` or see everything with `locals`.

## Source-Line vs Instruction Stepping

Pebble compiles your code into **bytecode instructions** — small operations
like "push the number 3 onto the stack" or "store a value in variable x". A
single line of source code often produces several instructions.

- **`step`** (or `s`) pauses once per **source line**. It skips over the
  individual bytecode instructions that make up one line.
- **`istep`** (or `n`) pauses before **every single instruction**. This is
  useful when you want to see exactly what the VM is doing under the hood.

```
$ pebble --debug add.pbl
  1: let x = 3
(pdb) n
  1: let x = 3
       STORE_NAME x
(pdb) n
       HALT
```

In instruction mode you see the opcode name (like `STORE_NAME x`) below the
source line.

## Breakpoints

Sometimes you don't want to step through every line — you just want to jump
straight to the interesting part. That's what **breakpoints** are for.

```
(pdb) break 3
Breakpoint set at line 3.
(pdb) continue
  3: print(x + y)
(pdb)
```

`break 3` tells the debugger "pause when you reach line 3". Then `continue`
lets the program run freely until it hits that line.

Use `clear 3` to remove a breakpoint, or `break` (no number) to see which
breakpoints are currently set.

## How It Works Under the Hood

The debugger uses a **hook pattern** — it plugs into the VM without changing
how the VM actually runs your code.

### The Hook Protocol

The VM defines a `DebugHook` protocol with one method:

```
on_instruction(instruction, ip, code, stack, frames) -> DebugAction
```

Before every instruction, the VM calls this method (if a hook is attached).
The hook can return:

- **`CONTINUE`** — keep running
- **`QUIT`** — stop the program

### What Happens Each Step

```
VM fetches instruction
  ↓
Hook fires: on_instruction(...)
  ↓
Hook checks: should I stop here?
  ├── Yes → show source line, wait for command
  └── No  → return CONTINUE immediately
  ↓
VM executes the instruction normally
```

The beauty of this design is that the VM barely changes — just four extra lines
of code. All the debugger logic lives in a separate module that the VM knows
nothing about.

### DebugAction

`DebugAction` is a simple enum:

```
DebugAction.CONTINUE  →  keep going
DebugAction.QUIT      →  stop now
```

The debugger returns `CONTINUE` after each `step` or `continue` command, and
`QUIT` when the user types `quit`.

## Summary

- A debugger lets you **pause** your program and **look around**
- Use `step` to go line by line, `istep` to see every bytecode instruction
- Set **breakpoints** to jump straight to the interesting parts
- The debugger hooks into the VM's execution loop without changing it
- The hook pattern keeps the debugger code completely separate from the VM code
