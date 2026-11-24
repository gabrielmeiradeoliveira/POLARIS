# Negativo: codigo valido sem issues
def f(x=None):
    if x is None:
        return 0
    try:
        return 10 / 2
    except ValueError:
        return -1
