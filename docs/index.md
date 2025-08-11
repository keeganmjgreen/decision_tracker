# DecisionTracker

DecisionTracker is a Python library for writing explainable, traceable, and auditable Python programs.

Using monadic patterns, the library provides a *DecisionTracker syntax* for writing logic and math operations and control flow. Through this syntax, it allows one or more trees of expressions to be built up under the hood. A tree represents some code paths, math, and logic of the program. Each tree can be evaluated to a final value, equivalent to obtaining one of the outputs of the program if it had been written using vanilla Python syntax instead of DecisionTracker syntax.

In addition, the tree can be simplified to represent only the logic and math of the code path taken to arrive at the tree's final value. This simplified tree can be flattened to a list of Evaluated Expressions, which can be stored in a dedicated relational database table. This allows program executions and outputs to be explained, traced, and audited at a level of thoroughness and ease which traditional logging cannot provide.

Furthermore, the library offers the [DecisionTracker Grafana panel](https://github.com/keeganmjgreen/keegangreen-decisiontracker-panel), allowing the simplified tree to be reconstructed from the Evaluated Expressions stored in the database, and then viewed interactively.

![](high_level_diagram.drawio.svg)

## DecisionTracker syntax

DecisionTracker syntax is a re-implementation of a subset of Python syntax, in Python syntax, in order to support DecisionTracker's features. The subset of Python syntax that is supported represents the kind of code expressions that can be stored in a database and for which DecisionTracker offers explainability and traceability.

### Numeric expressions

In DecisionTracker syntax, numeric expressions are based on the `Numeric` class:

<div class="grid" markdown>

```python title="Regular Python syntax"
a, b, c, d, e = 0, 1, 2, 3, 4
(a + b - c) * d / e
```

```python title="DecisionTracker Python syntax"
Numeric(a=0).plus(b=1).minus(c=2).times(d=3).divided_by(e=4)
```

</div>

!!! Note

    Just as in regular Python, use of `int`s and `float`s are interchangeable in the `Numeric` class. Performing a binary operation (e.g., addition) between two `int`s returns an `int`, performing a binary operation between two `float`s returns a `float`, and performing a binary operation between an `int` and a `float` returns a `float`. Division is the exception, which always returns a `float`.

DecisionTracker syntax is evaluated from left to right. If we wanted to change the order of operations, we would instead write:

<div class="grid" markdown>

```python title="Regular Python syntax"
a, b, c, d, e = 0, 1, 2, 3, 4
a + b - c * d / e
```

```python title="DecisionTracker Python syntax"
Int(Int(a=0).plus(b=1).minus(c=2)).times(d=3).divided_by(e=4)
```

</div>

A numeric expression can be converted to Evaluated Expressions, which can be seen in its string representation:

```python
>>> Int(Int(a=0).plus(b=1).minus(c=2)).times(d=3).divided_by(e=4)
-0.75 because ((((a := 0) + (b := 1)) - (c := 2)) * (d := 3)) / (e := 4)
```

!!! Note

    Nested addition operations, or nested multiplication operations, will be flattened, while maintaining the order of the operands and the final value.

### Comparisons

Comparisons of numeric expressions can be written as follows. Comparisons return `Bool`s.

<div class="grid" markdown>

```python title="Regular Python syntax"
a == b
a != b
a > b
a >= b
a < b
a <= b
```

```python title="DecisionTracker Python syntax"
Numeric(a).eq(b)
Numeric(a).neq(b)
Numeric(a).gt(b)
Numeric(a).gte(b)
Numeric(a).lt(b)
Numeric(a).lte(b)
```

</div>

For example:

```python
>>> Numeric(a=4).gt(b=2)
True because (a := 4) > (b := 2)
```

However, when a comparison evaluates to `False`, the comparison gets flipped. For example:

```python
>>> Numeric(a=2).gt(b=4)
False because (a := 2) <= (b := 4)
```

### Bool expressions

In DecisionTracker syntax, bool expressions are based on the `Bool` class:

<div class="grid" markdown>

```python title="Regular Python syntax"
x, y, z = True, True, False
(x or y) and not z
```

```python title="DecisionTracker Python syntax"
Bool(x=True).or_(y=True).and_(Not(z=False))

```

</div>

Again, DecisionTracker syntax is evaluated from left to right. If we wanted to change the order of operations, we would instead write:

<div class="grid" markdown>

```python title="Regular Python syntax"
x, y, z = True, True, False
x or y and not z
```

```python title="DecisionTracker Python syntax"
Bool(x=True).or_(Bool(y=True).and(Not(z=False)))
```

</div>

Just like a numeric expression, a bool expression can be converted to Evaluated Expressions, which can be seen in its string representation:

```python
>>> Bool(x=True).or_(y=True).or_(z=True))
True because (x := True) or (y := True) or (z := True)
```

```python
>>> Bool(x=True).and_(y=True).and_(z=True)
True because (x := True) and (y := True) and (z := True)
```

!!! Note

    Nested "or" operations, or nested "and" operations, will be flattened, while maintaining the order of the operands and the final value.

However, when the following get converted to Evaluated Expressions, things look a bit different. Click on the :material-plus-circle: icons to understand each case. These are examples of how Evaluated Expressions are not designed to represent the entire program, but to explain *why* it output certain values.

- <div></div>
    ```python
    >>> Bool(x=False).or_(y=True).or_(z=True)
    True because (y := True) or (z := True) # (1)!
    ```

    1. Why does this Evaluated Expression omit `x`? <br> Because `x` did not contribute to the final value being `True`.

- <div></div>
    ```python
    >>> Bool(x=False).or_(y=False).or_(z=False)
    False because (x := False) and (y := False) and (z := False) # (1)!
    ```

    1. Why has "or" been replaced with "and"? <br> Because the final value could be `False` only if *all* the inputs were `False`.

- <div></div>
    ```python
    >>> Bool(x=True).and_(y=False).and_(z=False)
    False because (y := False) or (z := False) # (1)!
    ```

    1. Why does this Evaluated Expression omit `x`? <br> Because `x` did not contribute to the final value being `False`. <p> Why has "and" been replaced with "or"? <br> Because the final value could be `False` if *any* of the inputs were `False`.

- <div></div>
    ```python
    >>> str(Not(x=True))
    False because (x := True) # (1)!
    >>> str(Not(x=False))
    True because (x := False) # (2)!
    ```

    1. Why do these Evaluated Expressions not include the "not" operator? <br> Because, just like above, the operator is not considered to be *causing* the final value.
    2. Why do these Evaluated Expressions not include the "not" operator? <br> Because, just like above, the operator is not considered to be *causing* the final value.

DecisionTracker supports alternate syntaxes for convenience or to suit user preferences:

- `Bool(x).and_(y).and_(z))` can alternately be written as `Bool(x).and_(y, z)`.
- `Bool(x).or_(Bool(y).and_(z))` can alternately be written as `Bool(x).or_(y, z)`.

### If-elif-else blocks

<div class="grid" markdown>

```python title="Regular Python syntax"
if a:
    return a1
elif b
    return b1
else:
    return c1
```

```python title="DecisionTracker Python syntax"
return If(a).then(
    a1
).elif_(b).then(
    b1
).else_(
    c1
)
```

</div>

Obviously, you can have as many `.elif_(...).then(...)` cases as you wish (including none). However, unlike in regular Python syntax, a final `.else_(...)` is always required.

### Ternary operators

Ternary operator expressions can be written as follows:

<div class="grid" markdown>

```python title="Regular Python syntax"
a if b else c
```

```python title="DecisionTracker Python syntax"
Int(a).if_(b).else_(c)
```

</div>

Ternary operator expressions can be chained, but like this:

<div class="grid" markdown>

```python
a if b else c if d else e
```

```python
Int(a).if_(b).else_(c.if_(d).else_(e))
```

</div>

Not like the following (which checks `d` *before* `b` and is likely not what is intended); simply keep in mind that DecisionTracker syntax is evaluated from left to right.

<div class="grid" markdown>

```python
(a if b else c) if d else e
```

```python
Int(a).if_(b).else_(c).if_(d).else_(e)
```

</div>

### Dict lookups

Dictionary lookups can be written as follows:

=== "Without a default"

    <div class="grid" markdown>

    ```python title="Regular Python syntax"
    {
        "a": a,
        "b": b,
    }[x]
    ```

    ```python title="DecisionTracker Python syntax"
    Lookup(
        {
            "a": a,
            "b": b,
        },
        x,
    )
    ```

    </div>

=== "With a default"

    <div class="grid" markdown>

    ```python title="Regular Python syntax"
    {
        "a": a,
        "b": b,
    }.get(x, c)
    ```

    ```python title="DecisionTracker Python syntax"
    UncertainLookup(
        {
            "a": a,
            "b": b,
        },
        x,
        c,
    )
    ```

    </div>

=== "With a `None` default"

    <div class="grid" markdown>

    ```python title="Regular Python syntax"
    {
        "a": a,
        "b": b,
    }.get(x)
    ```

    ```python title="DecisionTracker Python syntax"
    val = UncertainLookup(
        {
            "a": a,
            "b": b,
        },
        x,
    )
    ```

    </div>

    The return value of `.get(x)` should be checked to not be `None` before being used. Similarly, `IsNotNull(val)` should be checked before using `val` --- that is, using `Numeric(val)` if its possible values are numeric, `Bool(val)` if boolean, and so on.

## Migrating existing programs

TODO

## Storing Evaluated Expressions in a database

TODO

## Interactive viewing using the Grafana panel

TODO
