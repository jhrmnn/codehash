import pytest

from codehash import CodehashError, hash_function


def test_docstring():
    def f():
        return 1

    def g():
        """Docstring."""
        return 1

    assert hash_function(f) == hash_function(g)


def test_whitespace():
    def f():

        return 1

    def g():
        return 1  # comment

    assert hash_function(f) == hash_function(g)


def test_different():
    def f():
        return 1

    def g():
        return 2

    assert hash_function(f) != hash_function(g)


def test_constant():
    dct = {'a': 1}

    def f():
        1
        return dct

    h1 = hash_function(f)
    dct['a'] = 2

    def f():
        1
        return dct

    h2 = hash_function(f)
    assert h1 != h2


obj = object()


def test_unhashable():
    def f():
        return obj

    with pytest.raises(CodehashError):
        hash_function(f)


def test_module():
    import os

    import codehash
    from codehash import hash_text

    def f():
        os
        codehash
        hash_text('1')

    hash_function(f)


def test_unhashable_class():
    class C:
        pass

    def f():
        C

    with pytest.raises(CodehashError):
        hash_function(f)


def test_composite_func():
    def f():
        return 1

    def g():
        return f()

    h1 = hash_function(g)

    def f():  # noqa F811
        return 2

    def g():
        return f()

    h2 = hash_function(g)
    assert h1 != h2


def test_composite():
    o = [1, 2, (1, 2)]

    def f():
        return o

    h1 = hash_function(f)

    o = [1, 2, (1, 3)]

    def f():
        return o

    h2 = hash_function(f)
    assert h1 != h2


def test_hook():
    class C:
        pass

    c = C()

    def f():
        return c

    hash_function(f, hook=lambda c: '')


def test_magic_hook():
    class C:
        def __codehash__(self):
            return ''

    c = C()

    def f():
        return c

    hash_function(f)


def test_nested():
    def f():
        def g():
            pass

    hash_function(f)


def test_builtin():
    def f():
        int

    hash_function(f)


def test_unbound():
    def f():
        x  # noqa F821

    with pytest.raises(AssertionError):
        hash_function(f)
