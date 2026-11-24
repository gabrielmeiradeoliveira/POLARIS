import ast
import json
import sys
from pathlib import Path
import libcst as cst
import astroid

ANALYZER_ID = "polaris-python"
ANALYZER_VERSION = "0.1.0"


def analyze_file(file_path: Path) -> dict:
    content = file_path.read_text(encoding="utf-8", errors="replace")
    try:
        cst.parse_module(content)
        ast.parse(content, filename=str(file_path))
        astroid.parse(content)
    except Exception as exc:
        return {
            "analyzer": {"id": ANALYZER_ID, "version": ANALYZER_VERSION},
            "file": str(file_path),
            "state": "PARSE_ERROR",
            "error": str(exc),
            "issues": [],
        }
    return {
        "analyzer": {"id": ANALYZER_ID, "version": ANALYZER_VERSION},
        "file": str(file_path),
        "state": "ANALYZED_SUCCESS",
        "issues": [],
    }


if __name__ == "__main__":
    print(json.dumps(analyze_file(Path(sys.argv[1])), ensure_ascii=False))
