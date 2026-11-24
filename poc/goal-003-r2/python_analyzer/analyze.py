import ast
import json
import sys
from pathlib import Path
import libcst as cst
import astroid


def analyze_python_file(file_path: Path) -> dict:
    content = file_path.read_text(encoding="utf-8", errors="replace")
    issues = []

    # 1. Validação sintática via LibCST
    try:
        cst.parse_module(content)
    except cst.ParserSyntaxError as exc:
        return {"file": str(file_path), "state": "PARSE_ERROR", "error": str(exc), "issues": []}

    # 2. Análise AST + Astroid (resolução semântica / inferência)
    try:
        tree = ast.parse(content, filename=str(file_path))
        mod = astroid.parse(content)
    except Exception as exc:
        return {"file": str(file_path), "state": "ANALYZER_FAILURE", "error": str(exc), "issues": []}

    for node in ast.walk(tree):
        # PY-R001: Uso de eval/exec
        if isinstance(node, ast.Call) and isinstance(node.func, ast.Name) and node.func.id in ("eval", "exec"):
            issues.append({"ruleId": "PY-R001", "line": node.lineno, "message": f"Uso inseguro de {node.func.id}()."})
        # PY-R002: except nu (bare except)
        elif isinstance(node, ast.ExceptHandler) and node.type is None:
            issues.append({"ruleId": "PY-R002", "line": node.lineno, "message": "Evite except genérico sem tipo."})
        # PY-R003: Argumento padrão mutável (list/dict/set)
        elif isinstance(node, ast.FunctionDef):
            for default in node.args.defaults:
                if isinstance(default, (ast.List, ast.Dict, ast.Set)):
                    issues.append({"ruleId": "PY-R003", "line": node.lineno, "message": "Argumento padrão mutável."})
        # PY-R004: Comparação com None usando == ou !=
        elif isinstance(node, ast.Compare):
            for op, comp in zip(node.ops, node.comparators):
                if isinstance(op, (ast.Eq, ast.NotEq)) and isinstance(comp, ast.Constant) and comp.value is None:
                    issues.append({"ruleId": "PY-R004", "line": node.lineno, "message": "Use 'is None' ou 'is not None'."})

    # PY-R005 (Semântica via Astroid): Detectar divisão por zero literal ou inferida
    for binop in mod.nodes_of_class(astroid.BinOp):
        if binop.op in ("/", "//", "%"):
            try:
                for inferred in binop.right.infer():
                    if isinstance(inferred, astroid.Const) and inferred.value == 0:
                        issues.append({"ruleId": "PY-R005", "line": binop.lineno, "message": "Divisão por zero inferida semanticamente."})
                        break
            except astroid.InferenceError:
                pass

    return {"file": str(file_path), "state": "ANALYZED_SUCCESS", "issues": issues}


if __name__ == "__main__":
    target = Path(sys.argv[1])
    print(json.dumps(analyze_python_file(target), indent=2, ensure_ascii=False))
