# Java Fundamentals

## How the JVM Works

Java source code is compiled by `javac` into bytecode — `.class` files. The JVM
(Java Virtual Machine) loads and executes bytecode. This means Java is
"write once, run anywhere": the same `.class` file runs on any OS that has a JVM.

The JVM uses a JIT (Just-In-Time) compiler to convert hot bytecode paths into
native machine code at runtime. First execution is interpreted; repeated calls
get compiled to native for speed.

Memory is divided into the stack (local variables, method calls) and the heap
(objects). When you write `int x = 5`, x lives on the stack. When you write
`new Object()`, that object lives on the heap.

## Primitive vs Reference Types

Java has 8 primitive types: `int`, `long`, `double`, `float`, `boolean`,
`char`, `byte`, `short`. Primitives live on the stack and hold values directly.

Reference types (everything else) are objects. A variable of a reference type
holds a memory address — a pointer to where the object lives on the heap. The
variable is not the object; it points to the object.

## Pass-by-Value

Java is strictly pass-by-value. When you pass a variable to a method, Java
copies the value of that variable into the parameter. For primitives, this is
the actual number. For reference types, this is the memory address.

This means: reassigning a parameter inside a method does NOT affect the
caller's variable. But mutating the object via the reference (e.g., calling
`list.add()`) DOES affect the caller, because both the original and the copy
point to the same heap object.

## String Equality

Strings in Java are objects. The `==` operator compares references (memory
addresses), not content. Two String variables can hold the same text but be
different objects, so `==` returns `false`.

Use `.equals()` to compare String content:

```java
String a = new String("hello");
String b = new String("hello");
a == b        // false — different objects
a.equals(b)   // true — same content
```

String literals are interned: `"hello" == "hello"` may return `true` due to
the string pool. Do not rely on this. Always use `.equals()`.

## The final Keyword

`final` on a variable means the variable cannot be reassigned. It does NOT
make the object immutable.

```java
final List<String> names = new ArrayList<>();
names = new ArrayList<>();   // compile error — reassignment blocked
names.add("Alice");          // fine — mutation allowed
```

`final` on a method prevents overriding. `final` on a class prevents subclassing.

## Checked vs Unchecked Exceptions

Checked exceptions extend `Exception` directly. The compiler forces you to
either catch them or declare them in the method signature with `throws`.
Example: `IOException`, `SQLException`.

Unchecked exceptions extend `RuntimeException`. The compiler does not require
handling. Example: `NullPointerException`, `IllegalArgumentException`.

The rule: use checked exceptions for recoverable conditions the caller should
handle. Use unchecked for programming errors that should not occur.
