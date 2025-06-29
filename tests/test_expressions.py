from expressions import And, Expression, Not


def test_not_expression():
    # Test when condition is True:
    y = Not(x=True)
    assert y.value is False
    assert str(y) == "!(x := True)"
    assert str(y.with_name("y")) == "y := False because y := !(x := True)"

    # Test when condition is False:
    y = Not(x=False)
    assert y.value is True
    assert str(y) == "!(x := False)"
    assert str(y.with_name("y")) == "y := True because y := !(x := False)"


def test_and_expression():
    y = And(a=True, b=True)
    assert y.value is True
    assert str(y) == "(a := True) and (b := True)"
    assert str(y.with_name("y")) == "y := True because y := (a := True) and (b := True)"

    y = And(a=True, b=False)
    assert y.value is False
    assert str(y) == "(!(a := True)) or (!(b := False))"
    assert (
        str(y.with_name("y"))
        == "y := False because y := (!(a := True)) or (!(b := False))"
    )


def test_if_else():
    # Test when condition is True:
    y = Expression(1).if_(x=True).else_(2)
    assert y.value == 1
    assert str(y) == "1 because x := True"
    assert str(y.with_name("y")) == "y := 1 because x := True"

    # Test when condition is False:
    y = Expression(1).if_(x=False).else_(2)
    assert y.value == 2
    assert str(y) == "2 because !(x := True)"
    assert str(y.with_name("y")) == "y := 2 because !(x := True)"

    # Test when result_if_true and/or result_if_false are named:
    y = Expression(a=1).if_(x=True).else_(b=2)
    assert y.value == 1
