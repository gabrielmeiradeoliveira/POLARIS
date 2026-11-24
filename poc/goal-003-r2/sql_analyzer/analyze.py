import json
import sys
from pathlib import Path
import sqlglot
from sqlglot import exp


def analyze_sql_file(file_path: Path, dialect: str = "postgres") -> dict:
    content = file_path.read_text(encoding="utf-8", errors="replace")
    issues = []
    try:
        statements = sqlglot.parse(content, read=dialect)
    except sqlglot.errors.ParseError as exc:
        return {"file": str(file_path), "dialect": dialect, "state": "PARSE_ERROR", "error": str(exc), "issues": []}

    for stmt in statements:
        if stmt is None:
            continue
        # SQL-R001: SELECT *
        for sel in stmt.find_all(exp.Select):
            for proj in sel.expressions:
                if isinstance(proj, exp.Star):
                    issues.append({"ruleId": "SQL-R001", "message": "Evite SELECT * em consultas."})
        # SQL-R002: DELETE sem WHERE
        for d in stmt.find_all(exp.Delete):
            if d.args.get("where") is None:
                issues.append({"ruleId": "SQL-R002", "message": "DELETE sem cláusula WHERE."})
        # SQL-R003: UPDATE sem WHERE
        for u in stmt.find_all(exp.Update):
            if u.args.get("where") is None:
                issues.append({"ruleId": "SQL-R003", "message": "UPDATE sem cláusula WHERE."})
        # SQL-R004: DROP TABLE sem IF EXISTS
        for dr in stmt.find_all(exp.Drop):
            if not dr.args.get("exists"):
                issues.append({"ruleId": "SQL-R004", "message": "DROP sem IF EXISTS."})
        # SQL-R005: LIKE começando com '%'
        for lk in stmt.find_all(exp.Like):
            pat = lk.expression
            if isinstance(pat, exp.Literal) and pat.is_string and pat.this.startswith("%"):
                issues.append({"ruleId": "SQL-R005", "message": "LIKE com wildcard inicial impede uso de índice."})

    return {"file": str(file_path), "dialect": dialect, "state": "ANALYZED_SUCCESS", "issues": issues}


if __name__ == "__main__":
    target = Path(sys.argv[1])
    dialect = sys.argv[2] if len(sys.argv) > 2 else "postgres"
    print(json.dumps(analyze_sql_file(target, dialect), indent=2, ensure_ascii=False))
