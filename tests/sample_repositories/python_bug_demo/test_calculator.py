from calculator import divide


def test_normal_division():
    assert divide(10, 2) == 5


def test_division_by_zero():
    try:
        divide(10, 0)
    except ZeroDivisionError:
        assert False, "Division by zero should be handled safely"