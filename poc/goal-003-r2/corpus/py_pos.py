# Positivo: PY-R001 (eval), PY-R002 (bare except), PY-R003 (default mutavel), PY-R004 (== None), PY-R005 (divisao por zero inferida)
def f(x=[]):
    z = 0
    try:
        if x == None:
            return eval("1")
        return 10 / z
    except:
        return 0
