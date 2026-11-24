import json
from pathlib import Path

PILOT = {
    ("python", "PY-SYN-001"): [
        ("POS-1", "positive", True, "eval('1+1')"),
        ("POS-2", "positive", True, "exec('x=1')"),
        ("POS-3", "positive", True, "def f():\n    return eval('2')"),
        ("NEG-1", "negative", False, "import ast\nast.literal_eval('1')"),
        ("NEG-2", "negative", False, "def evaluate(x):\n    return x + 1"),
        ("NEG-3", "negative", False, "x = 1 + 1"),
        ("EDG-1", "edge", False, "# eval('1') in comment"),
        ("EDG-2", "edge", True, "eval(\n    '42'\n)"),
    ],
    ("python", "PY-REL-001"): [
        ("POS-1", "positive", True, "try:\n    x = 1\nexcept:\n    pass"),
        ("POS-2", "positive", True, "def f():\n    try:\n        return 1\n    except:\n        return 0"),
        ("POS-3", "positive", True, "try:\n    a = 1\nexcept:\n    a = 2"),
        ("NEG-1", "negative", False, "try:\n    x = 1\nexcept ValueError:\n    x = 0"),
        ("NEG-2", "negative", False, "try:\n    x = 1\nexcept (KeyError, TypeError):\n    x = 0"),
        ("NEG-3", "negative", False, "x = 1"),
        ("EDG-1", "edge", False, "# except: pass"),
        ("EDG-2", "edge", True, "try:\r\n    x=1\r\nexcept:\r\n    x=2"),
    ],
    ("sql", "SQL-SYN-001"): [
        ("POS-1", "positive", True, "SELECT * FROM users;"),
        ("POS-2", "positive", True, "SELECT * FROM orders WHERE id = 1;"),
        ("POS-3", "positive", True, "SELECT u.* FROM users u;"),
        ("NEG-1", "negative", False, "SELECT id, name FROM users;"),
        ("NEG-2", "negative", False, "SELECT COUNT(*) FROM users;"),
        ("NEG-3", "negative", False, "DELETE FROM users WHERE id = 1;"),
        ("EDG-1", "edge", False, "-- SELECT * FROM users;"),
        ("EDG-2", "edge", True, "SELECT\n  *\nFROM\n  users;"),
    ],
    ("sql", "SQL-CTX-001"): [
        ("POS-1", "positive", True, "DELETE FROM users;"),
        ("POS-2", "positive", True, "UPDATE users SET active = 0;"),
        ("POS-3", "positive", True, "DELETE FROM logs;"),
        ("NEG-1", "negative", False, "DELETE FROM users WHERE id = 1;"),
        ("NEG-2", "negative", False, "UPDATE users SET active = 0 WHERE id = 1;"),
        ("NEG-3", "negative", False, "SELECT id FROM users;"),
        ("EDG-1", "edge", False, "-- DELETE FROM users;"),
        ("EDG-2", "edge", True, "UPDATE\r\n  users\r\nSET\r\n  a = 1;"),
    ],
}

base = Path("tests/fixtures/rules")
for (lang, rid), items in PILOT.items():
    p = base / lang / f"{rid}.json"
    cases = [{"caseId": f"{rid}-{cid}", "kind": kind, "expectedPositive": exp, "code": code} for cid, kind, exp, code in items]
    p.write_text(json.dumps({"ruleId": rid, "language": lang, "cases": cases}, indent=2), encoding="utf-8")
print("PILOT_WRITTEN:", len(PILOT))
