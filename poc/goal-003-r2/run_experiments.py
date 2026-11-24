import json
import subprocess
import time
from pathlib import Path

ROOT = Path(__file__).parent.resolve()
VENV_PY = ROOT.parent.parent / ".venv" / "Scripts" / "python.exe"
CS_DLL = ROOT / "csharp_analyzer" / "bin" / "Release" / "net11.0" / "PolarisCSharpAnalyzer.dll"
JV_JAR = ROOT / "java_analyzer" / "target" / "polaris-java-analyzer-0.1.0.jar"


def run_cmd(cmd):
    t0 = time.perf_counter()
    p = subprocess.run(cmd, capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=30)
    dt = time.perf_counter() - t0
    return p.returncode, p.stdout, p.stderr, dt


def eval_lang(name, pos_file, neg_file, expected_rules, runner):
    _, out_pos, err_pos, dt_pos = runner(pos_file)
    _, out_neg, err_neg, dt_neg = runner(neg_file)
    res_pos = json.loads(out_pos)
    res_neg = json.loads(out_neg)
    got_pos = {i["ruleId"] for i in res_pos.get("issues", [])}
    got_neg = {i["ruleId"] for i in res_neg.get("issues", [])}

    tp = len(expected_rules & got_pos)
    fn = len(expected_rules - got_pos)
    fp = len(got_neg)
    prec = tp / (tp + fp) if (tp + fp) else 0.0
    rec = tp / (tp + fn) if (tp + fn) else 0.0
    f1 = 2 * prec * rec / (prec + rec) if (prec + rec) else 0.0
    return {
        "language": name,
        "tp": tp, "fp": fp, "fn": fn,
        "precision": round(prec, 4), "recall": round(rec, 4), "f1": round(f1, 4),
        "time_pos_sec": round(dt_pos, 4), "time_neg_sec": round(dt_neg, 4),
    }


def main():
    corpus = ROOT / "corpus"
    results = [
        eval_lang(
            "Python", corpus / "py_pos.py", corpus / "py_neg.py",
            {"PY-R001", "PY-R002", "PY-R003", "PY-R004", "PY-R005"},
            lambda f: run_cmd([str(VENV_PY), str(ROOT / "python_analyzer" / "analyze.py"), str(f)]),
        ),
        eval_lang(
            "C# (Roslyn)", corpus / "cs_pos.cs", corpus / "cs_neg.cs",
            {"CS-R001", "CS-R002", "CS-R003", "CS-R004", "CS-R005"},
            lambda f: run_cmd(["dotnet", str(CS_DLL), str(f)]),
        ),
        eval_lang(
            "Java (JavaParser)", corpus / "jv_pos.java", corpus / "jv_neg.java",
            {"JV-R001", "JV-R002", "JV-R003", "JV-R004", "JV-R005"},
            lambda f: run_cmd(["java", "-jar", str(JV_JAR), str(f)]),
        ),
        eval_lang(
            "SQL (SQLGlot)", corpus / "sql_pos.sql", corpus / "sql_neg.sql",
            {"SQL-R001", "SQL-R002", "SQL-R003", "SQL-R004", "SQL-R005"},
            lambda f: run_cmd([str(VENV_PY), str(ROOT / "sql_analyzer" / "analyze.py"), str(f), "postgres"]),
        ),
    ]

    # Teste PostgreSQL 17 (transacao + rollback + persistencia)
    pg_sql = (
        "CREATE TABLE IF NOT EXISTS poc_runs (id SERIAL PRIMARY KEY, name TEXT NOT NULL);"
        "BEGIN; INSERT INTO poc_runs(name) VALUES ('rollback_test'); ROLLBACK;"
        "BEGIN; INSERT INTO poc_runs(name) VALUES ('commit_test'); COMMIT;"
        "SELECT COUNT(*) FROM poc_runs WHERE name = 'commit_test';"
    )
    pg_rc, pg_out, pg_err, _ = run_cmd([
        "docker", "exec", "polaris-poc-postgres",
        "psql", "-U", "polaris", "-d", "polaris_poc", "-t", "-A", "-c", pg_sql
    ])

    print(json.dumps({
        "analyzers": results,
        "postgres_rc": pg_rc,
        "postgres_commit_count": pg_out.strip().splitlines()[-1] if pg_out.strip() else "",
    }, indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()
