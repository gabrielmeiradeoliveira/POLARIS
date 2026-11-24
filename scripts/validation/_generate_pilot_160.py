import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
OUT = ROOT / "tests" / "fixtures" / "pilot_160"


def make_cases(pos: list[str], neg: list[str], edge: list[tuple[bool, str]]) -> list[dict]:
    cases = []
    for i, code in enumerate(pos, 1):
        cases.append({"caseId": f"POS-{i}", "kind": "positive", "expectedPositive": True, "code": code})
    for i, code in enumerate(neg, 1):
        cases.append({"caseId": f"NEG-{i}", "kind": "negative", "expectedPositive": False, "code": code})
    for i, (exp, code) in enumerate(edge, 1):
        cases.append({"caseId": f"EDG-{i}", "kind": "edge", "expectedPositive": exp, "code": code})
    return cases


PILOT = {
    ("python", "PY-SYN-001"): make_cases(
        ["eval('1+1')", "exec('x=1')", "def f():\n    return eval('2')"],
        ["import ast\nast.literal_eval('1')", "def evaluate(x):\n    return x + 1", "x = 1 + 1"],
        [(False, "# eval('1')"), (True, "eval(\n '42'\n)")],
    ),
    ("python", "PY-REL-001"): make_cases(
        ["try:\n x=1\nexcept:\n pass", "def f():\n try:\n  return 1\n except:\n  return 0", "try:\n a=1\nexcept:\n a=2"],
        ["try:\n x=1\nexcept ValueError:\n x=0", "try:\n x=1\nexcept (KeyError, TypeError):\n x=0", "x = 1"],
        [(False, "# except: pass"), (True, "try:\r\n x=1\r\nexcept:\r\n x=2")],
    ),
    ("python", "PY-SEM-001"): make_cases(
        ["def f(x=[]):\n return x", "def g(d={}):\n return d", "def h(s={1}):\n return s"],
        ["def f(x=None):\n return x", "def g(x=1):\n return x", "def h():\n return []"],
        [(False, "# def f(x=[]):"), (True, "def f(a, b=[]):\n return b")],
    ),
    ("python", "PY-SEC-001"): make_cases(
        ["password = \"secret123\"", "api_key = \"key_abc_123\"", "secret = \"tok_xyz\""],
        ["password = None", "name = \"alice\"", "x = 1"],
        [(False, "# password = \"secret123\""), (True, "def f():\n password = \"s3cr3t\"")],
    ),
    ("python", "PY-MNT-001"): make_cases(
        ["def f():\n global x\n x = 1", "def g():\n global a, b\n a = 2", "def h():\n global cfg\n return cfg"],
        ["def f(x):\n return x + 1", "x = 1", "def g():\n y = 2\n return y"],
        [(False, "# global x"), (True, "def f():\n    global x\n    x = 1")],
    ),
    ("csharp", "CS-SYN-001"): make_cases(
        ["class C { void M() { try { } catch { } } }", "class C { void M() { try { int x=1; } catch (System.Exception) { } } }", "class C { void M() { try { } catch (System.Exception ex) { } } }"],
        ["class C { void M() { try { } catch { System.Console.WriteLine(1); } } }", "class C { void M() { int x = 1; } }", "class C { }"],
        [(False, "// catch { }"), (True, "class C { void M() { try {} catch\n{} } }")],
    ),
    ("csharp", "CS-SEM-001"): make_cases(
        ["class C { string M() { return null; } }", "class C { object M() { return null; } }", "class C { string M(int x) { if (x > 0) return \"a\"; return null; } }"],
        ["class C { string M() { return \"ok\"; } }", "class C { int M() { return 1; } }", "class C { }"],
        [(False, "// return null;"), (True, "class C { string M() {\n return null;\n} }")],
    ),
    ("csharp", "CS-REL-001"): make_cases(
        ["class C { void M() { throw new System.Exception(); } }", "class C { void M() { throw new System.Exception(\"err\"); } }", "using System;\nclass C { void M() { throw new Exception(); } }"],
        ["class C { void M() { throw new System.InvalidOperationException(); } }", "class C { void M() { int x = 1; } }", "class C { }"],
        [(False, "// throw new Exception();"), (True, "class C { void M() => throw new System.Exception(); }")],
    ),
    ("csharp", "CS-SEC-001"): make_cases(
        ["class C { string p = \"hardcoded123\"; }", "class C { string password = \"secret\"; }", "class C { string apiKey = \"abc123\"; }"],
        ["class C { string p = null; }", "class C { string name = \"john\"; }", "class C { }"],
        [(False, "// password = \"secret\""), (True, "class C { private const string password = \"s3cr3t\"; }")],
    ),
    ("csharp", "CS-MNT-001"): make_cases(
        ["// TODO: fix\nclass C { }", "class C { /* FIXME */ }", "// TODO refactor\nclass C { }"],
        ["class C { }", "class C { int x = 1; }", "// normal comment\nclass C { }"],
        [(False, "class C { string s = \"TODO\"; }"), (True, "class C { // TODO: edge\n}")],
    ),
    ("java", "JV-SYN-001"): make_cases(
        ["class C { void m() { try {} catch (Exception e) {} } }", "class C { void m() { try { int x=1; } catch (RuntimeException e) {} } }", "class C { void m() { try {} catch (Throwable t) {} } }"],
        ["class C { void m() { try {} catch (Exception e) { e.printStackTrace(); } } }", "class C { void m() { int x = 1; } }", "class C {}"],
        [(False, "// catch (Exception e) {}"), (True, "class C { void m() { try {} catch (Exception e)\n{} } }")],
    ),
    ("java", "JV-SEM-001"): make_cases(
        ["class C { void m() { System.out.println(1); } }", "class C { void m() { System.err.println(1); } }", "class C { void m() { System.out.println(\"a\"); } }"],
        ["class C { void m() { int x = 1; } }", "class C { void println() {} void m() { println(); } }", "class C {}"],
        [(False, "// System.out.println(1);"), (True, "class C { void m() { System.out.println(\n1\n); } }")],
    ),
    ("java", "JV-REL-001"): make_cases(
        ["class C { void m() throws Exception { throw new Exception(); } }", "class C { void m() throws Throwable { throw new Throwable(); } }", "class C { void m() throws Exception { throw new Exception(\"x\"); } }"],
        ["class C { void m() { throw new IllegalArgumentException(); } }", "class C { void m() { int x = 1; } }", "class C {}"],
        [(False, "// throw new Exception();"), (True, "class C { void m() throws Exception { throw new Exception(\"\"); } }")],
    ),
    ("java", "JV-SEC-001"): make_cases(
        ["class C { String password = \"secret\"; }", "class C { String apiKey = \"key123\"; }", "class C { String secret = \"tok\"; }"],
        ["class C { String password = null; }", "class C { String name = \"alice\"; }", "class C {}"],
        [(False, "// password = \"secret\""), (True, "class C { private static final String password = \"abc\"; }")],
    ),
    ("java", "JV-MNT-001"): make_cases(
        ["// TODO: fix\nclass C {}", "class C { /* FIXME */ }", "// TODO\nclass C {}"],
        ["class C {}", "class C { int x = 1; }", "// normal\nclass C {}"],
        [(False, "class C { String s = \"TODO\"; }"), (True, "class C { // TODO: edge\n}")],
    ),
    ("sql", "SQL-SYN-001"): make_cases(
        ["SELECT * FROM users;", "SELECT * FROM orders WHERE id = 1;", "SELECT u.* FROM users u;"],
        ["SELECT id, name FROM users;", "SELECT COUNT(*) FROM users;", "INSERT INTO users (id) VALUES (1);"],
        [(False, "-- SELECT * FROM users;"), (True, "SELECT\n *\nFROM users;")],
    ),
    ("sql", "SQL-CTX-001"): make_cases(
        ["DELETE FROM users;", "DELETE FROM orders;", "DELETE FROM logs;"],
        ["DELETE FROM users WHERE id = 1;", "SELECT id FROM users;", "INSERT INTO users (id) VALUES (1);"],
        [(False, "-- DELETE FROM users;"), (True, "DELETE\nFROM users;")],
    ),
    ("sql", "SQL-CTX-002"): make_cases(
        ["UPDATE users SET active = 0;", "UPDATE orders SET status = 'x';", "UPDATE logs SET ok = 1;"],
        ["UPDATE users SET active = 0 WHERE id = 1;", "SELECT id FROM users;", "INSERT INTO users (id) VALUES (1);"],
        [(False, "-- UPDATE users SET active = 0;"), (True, "UPDATE users\nSET active = 0;")],
    ),
    ("sql", "SQL-SYN-002"): make_cases(
        ["SELECT a FROM t WHERE b = NULL;", "SELECT a FROM t WHERE b != NULL;", "SELECT a FROM t WHERE b <> NULL;"],
        ["SELECT a FROM t WHERE b IS NULL;", "SELECT a FROM t WHERE b IS NOT NULL;", "SELECT a FROM t;"],
        [(False, "-- WHERE b = NULL"), (True, "SELECT a FROM t WHERE\nb = NULL;")],
    ),
    ("sql", "SQL-SYN-003"): make_cases(
        ["SELECT DISTINCT a FROM t GROUP BY a;", "SELECT DISTINCT a, b FROM t GROUP BY a, b;", "SELECT DISTINCT u.id FROM users u GROUP BY u.id;"],
        ["SELECT DISTINCT a FROM t;", "SELECT a FROM t GROUP BY a;", "SELECT a, COUNT(*) FROM t GROUP BY a;"],
        [(False, "-- SELECT DISTINCT a FROM t GROUP BY a;"), (True, "SELECT DISTINCT\n a\nFROM t GROUP BY a;")],
    ),
}

for (lang, rid), cases in PILOT.items():
    p = OUT / lang / f"{rid}.json"
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(json.dumps({"ruleId": rid, "language": lang, "cases": cases}, indent=2), encoding="utf-8")

print(f"WROTE_FILES={len(PILOT)} TOTAL_CASES={sum(len(v) for v in PILOT.values())}")
