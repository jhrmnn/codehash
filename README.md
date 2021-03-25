# Codehash

## Installing

Install and update using [Pip](https://pip.pypa.io/en/stable/quickstart/).

```
pip install -U codehash
```

## A simple example

```python
from codehash import hash_function

dct = {'a': 1}

def f(x):
    return 1 + dct["param"]

h1 = hash_function(f)

def f(x):
    """Docstring."""
    return 1 + dct["param"]  # comment

h2 = hash_function(f)

dct = {'a': 2}

def f(x):
    return 1 + dct["param"]

h3 = hash_function(f)

assert h1 == h2
assert h1 != h3
```
