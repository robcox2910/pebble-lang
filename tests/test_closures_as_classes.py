"""Tests showing closures can emulate classes (Phase 4, Item 12).

Demonstrate that private state + methods can be built with closures alone,
and that classes are syntactic sugar that makes the same pattern cleaner.
All tests should pass immediately — no new language features needed.
"""

from tests.conftest import run_source

# -- Named constants ----------------------------------------------------------

COUNT_ZERO = 0
COUNT_ONE = 1
COUNT_TWO = 2
COUNT_THREE = 3


# ===========================================================================
# Example 1: Counter
# ===========================================================================


class TestClosureCounter:
    """Verify a closure-based counter with increment, get, and reset."""

    def test_increment_once(self) -> None:
        """Incrementing once returns 1."""
        source = """\
fn make_counter() {
    let count = 0
    fn increment() {
        count = count + 1
    }
    fn get_count() {
        return count
    }
    fn reset() {
        count = 0
    }
    return increment, get_count, reset
}
let inc, get, rst = make_counter()
inc()
print(get())"""
        assert run_source(source) == "1\n"

    def test_increment_multiple(self) -> None:
        """Incrementing three times returns 3."""
        source = """\
fn make_counter() {
    let count = 0
    fn increment() { count = count + 1 }
    fn get_count() { return count }
    fn reset() { count = 0 }
    return increment, get_count, reset
}
let inc, get, rst = make_counter()
inc()
inc()
inc()
print(get())"""
        assert run_source(source) == "3\n"

    def test_reset(self) -> None:
        """Reset brings the count back to zero."""
        source = """\
fn make_counter() {
    let count = 0
    fn increment() { count = count + 1 }
    fn get_count() { return count }
    fn reset() { count = 0 }
    return increment, get_count, reset
}
let inc, get, rst = make_counter()
inc()
inc()
rst()
print(get())"""
        assert run_source(source) == "0\n"

    def test_independent_instances(self) -> None:
        """Two closure-counters maintain independent state."""
        source = """\
fn make_counter() {
    let count = 0
    fn increment() { count = count + 1 }
    fn get_count() { return count }
    fn reset() { count = 0 }
    return increment, get_count, reset
}
let inc_a, get_a, rst_a = make_counter()
let inc_b, get_b, rst_b = make_counter()
inc_a()
inc_a()
inc_b()
print(get_a())
print(get_b())"""
        assert run_source(source) == "2\n1\n"


class TestClassCounter:
    """Verify a class-based counter with increment, get, and reset."""

    def test_increment_once(self) -> None:
        """Incrementing once returns 1."""
        source = """\
class Counter {
    count,
    fn increment(self) { self.count = self.count + 1 }
    fn get(self) { return self.count }
    fn reset(self) { self.count = 0 }
}
let c = Counter(0)
c.increment()
print(c.get())"""
        assert run_source(source) == "1\n"

    def test_increment_multiple(self) -> None:
        """Incrementing three times returns 3."""
        source = """\
class Counter {
    count,
    fn increment(self) { self.count = self.count + 1 }
    fn get(self) { return self.count }
    fn reset(self) { self.count = 0 }
}
let c = Counter(0)
c.increment()
c.increment()
c.increment()
print(c.get())"""
        assert run_source(source) == "3\n"

    def test_reset(self) -> None:
        """Reset brings the count back to zero."""
        source = """\
class Counter {
    count,
    fn increment(self) { self.count = self.count + 1 }
    fn get(self) { return self.count }
    fn reset(self) { self.count = 0 }
}
let c = Counter(0)
c.increment()
c.increment()
c.reset()
print(c.get())"""
        assert run_source(source) == "0\n"

    def test_independent_instances(self) -> None:
        """Two class instances maintain independent state."""
        source = """\
class Counter {
    count,
    fn increment(self) { self.count = self.count + 1 }
    fn get(self) { return self.count }
    fn reset(self) { self.count = 0 }
}
let a = Counter(0)
let b = Counter(0)
a.increment()
a.increment()
b.increment()
print(a.get())
print(b.get())"""
        assert run_source(source) == "2\n1\n"


# ===========================================================================
# Example 2: Dog
# ===========================================================================


class TestClosureDog:
    """Verify a closure-based Dog with bark, rename, and get_name."""

    def test_bark(self) -> None:
        """Bark returns a greeting with the dog's name."""
        source = """\
fn make_dog(name) {
    let the_name = name
    fn bark() {
        return "Woof! I'm " + the_name
    }
    fn rename(new_name) {
        the_name = new_name
    }
    fn get_name() {
        return the_name
    }
    return bark, rename, get_name
}
let bark, rename, get_name = make_dog("Rex")
print(bark())"""
        assert run_source(source) == "Woof! I'm Rex\n"

    def test_rename(self) -> None:
        """Rename changes the name used by bark."""
        source = """\
fn make_dog(name) {
    let the_name = name
    fn bark() { return "Woof! I'm " + the_name }
    fn rename(new_name) { the_name = new_name }
    fn get_name() { return the_name }
    return bark, rename, get_name
}
let bark, rename, get_name = make_dog("Rex")
rename("Buddy")
print(bark())
print(get_name())"""
        assert run_source(source) == "Woof! I'm Buddy\nBuddy\n"


class TestClassDog:
    """Verify a class-based Dog with bark and rename."""

    def test_bark(self) -> None:
        """Bark returns a greeting with the dog's name."""
        source = """\
class Dog {
    name,
    fn bark(self) {
        return "Woof! I'm " + self.name
    }
    fn rename(self, new_name) {
        self.name = new_name
    }
}
let d = Dog("Rex")
print(d.bark())"""
        assert run_source(source) == "Woof! I'm Rex\n"

    def test_rename(self) -> None:
        """Rename changes the name used by bark."""
        source = """\
class Dog {
    name,
    fn bark(self) { return "Woof! I'm " + self.name }
    fn rename(self, new_name) { self.name = new_name }
}
let d = Dog("Rex")
d.rename("Buddy")
print(d.bark())
print(d.name)"""
        assert run_source(source) == "Woof! I'm Buddy\nBuddy\n"


# ===========================================================================
# Example 3: Stack
# ===========================================================================


class TestClosureStack:
    """Verify a closure-based stack with push, pop, peek, is_empty."""

    def test_push_and_peek(self) -> None:
        """Pushing a value makes it visible via peek."""
        source = """\
fn make_stack() {
    let items = []
    fn stack_push(val) { push(items, val) }
    fn stack_pop() { return pop(items) }
    fn peek() { return items[len(items) - 1] }
    fn is_empty() { return len(items) == 0 }
    return stack_push, stack_pop, peek, is_empty
}
let push_fn, pop_fn, peek_fn, empty_fn = make_stack()
push_fn(42)
print(peek_fn())"""
        assert run_source(source) == "42\n"

    def test_pop_lifo(self) -> None:
        """Pop returns items in last-in-first-out order."""
        source = """\
fn make_stack() {
    let items = []
    fn stack_push(val) { push(items, val) }
    fn stack_pop() { return pop(items) }
    fn peek() { return items[len(items) - 1] }
    fn is_empty() { return len(items) == 0 }
    return stack_push, stack_pop, peek, is_empty
}
let push_fn, pop_fn, peek_fn, empty_fn = make_stack()
push_fn(1)
push_fn(2)
push_fn(3)
print(pop_fn())
print(pop_fn())"""
        assert run_source(source) == "3\n2\n"

    def test_is_empty(self) -> None:
        """is_empty returns true on a fresh stack, false after push."""
        source = """\
fn make_stack() {
    let items = []
    fn stack_push(val) { push(items, val) }
    fn stack_pop() { return pop(items) }
    fn peek() { return items[len(items) - 1] }
    fn is_empty() { return len(items) == 0 }
    return stack_push, stack_pop, peek, is_empty
}
let push_fn, pop_fn, peek_fn, empty_fn = make_stack()
print(empty_fn())
push_fn(1)
print(empty_fn())"""
        assert run_source(source) == "true\nfalse\n"


class TestClassStack:
    """Verify a class-based stack with push, pop, peek, is_empty."""

    def test_push_and_peek(self) -> None:
        """Pushing a value makes it visible via peek."""
        source = """\
class Stack {
    items,
    fn stack_push(self, val) { push(self.items, val) }
    fn stack_pop(self) { return pop(self.items) }
    fn peek(self) { return self.items[len(self.items) - 1] }
    fn is_empty(self) { return len(self.items) == 0 }
}
let s = Stack([])
s.stack_push(42)
print(s.peek())"""
        assert run_source(source) == "42\n"

    def test_pop_lifo(self) -> None:
        """Pop returns items in last-in-first-out order."""
        source = """\
class Stack {
    items,
    fn stack_push(self, val) { push(self.items, val) }
    fn stack_pop(self) { return pop(self.items) }
    fn peek(self) { return self.items[len(self.items) - 1] }
    fn is_empty(self) { return len(self.items) == 0 }
}
let s = Stack([])
s.stack_push(1)
s.stack_push(2)
s.stack_push(3)
print(s.stack_pop())
print(s.stack_pop())"""
        assert run_source(source) == "3\n2\n"

    def test_is_empty(self) -> None:
        """is_empty returns true on a fresh stack, false after push."""
        source = """\
class Stack {
    items,
    fn stack_push(self, val) { push(self.items, val) }
    fn stack_pop(self) { return pop(self.items) }
    fn peek(self) { return self.items[len(self.items) - 1] }
    fn is_empty(self) { return len(self.items) == 0 }
}
let s = Stack([])
print(s.is_empty())
s.stack_push(1)
print(s.is_empty())"""
        assert run_source(source) == "true\nfalse\n"


# ===========================================================================
# Equivalence — same behaviour from both approaches
# ===========================================================================


class TestEquivalence:
    """Verify closure-based and class-based versions produce identical output."""

    def test_counter_equivalence(self) -> None:
        """Closure counter and class counter produce the same output."""
        closure_source = """\
fn make_counter() {
    let count = 0
    fn increment() { count = count + 1 }
    fn get_count() { return count }
    fn reset() { count = 0 }
    return increment, get_count, reset
}
let inc, get, rst = make_counter()
inc()
inc()
inc()
print(get())
rst()
print(get())"""

        class_source = """\
class Counter {
    count,
    fn increment(self) { self.count = self.count + 1 }
    fn get(self) { return self.count }
    fn reset(self) { self.count = 0 }
}
let c = Counter(0)
c.increment()
c.increment()
c.increment()
print(c.get())
c.reset()
print(c.get())"""

        assert run_source(closure_source) == run_source(class_source)

    def test_dog_equivalence(self) -> None:
        """Closure dog and class dog produce the same output."""
        closure_source = """\
fn make_dog(name) {
    let the_name = name
    fn bark() { return "Woof! I'm " + the_name }
    fn rename(new_name) { the_name = new_name }
    fn get_name() { return the_name }
    return bark, rename, get_name
}
let bark, rename, get_name = make_dog("Rex")
print(bark())
rename("Buddy")
print(bark())"""

        class_source = """\
class Dog {
    name,
    fn bark(self) { return "Woof! I'm " + self.name }
    fn rename(self, new_name) { self.name = new_name }
}
let d = Dog("Rex")
print(d.bark())
d.rename("Buddy")
print(d.bark())"""

        assert run_source(closure_source) == run_source(class_source)

    def test_stack_equivalence(self) -> None:
        """Closure stack and class stack produce the same output."""
        closure_source = """\
fn make_stack() {
    let items = []
    fn stack_push(val) { push(items, val) }
    fn stack_pop() { return pop(items) }
    fn peek() { return items[len(items) - 1] }
    fn is_empty() { return len(items) == 0 }
    return stack_push, stack_pop, peek, is_empty
}
let push_fn, pop_fn, peek_fn, empty_fn = make_stack()
print(empty_fn())
push_fn(10)
push_fn(20)
push_fn(30)
print(peek_fn())
print(pop_fn())
print(pop_fn())
print(empty_fn())"""

        class_source = """\
class Stack {
    items,
    fn stack_push(self, val) { push(self.items, val) }
    fn stack_pop(self) { return pop(self.items) }
    fn peek(self) { return self.items[len(self.items) - 1] }
    fn is_empty(self) { return len(self.items) == 0 }
}
let s = Stack([])
print(s.is_empty())
s.stack_push(10)
s.stack_push(20)
s.stack_push(30)
print(s.peek())
print(s.stack_pop())
print(s.stack_pop())
print(s.is_empty())"""

        assert run_source(closure_source) == run_source(class_source)
