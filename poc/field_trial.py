from __future__ import annotations

import json
import sys
import tempfile
import time
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT))
sys.path.insert(0, str(REPO_ROOT / "src"))
sys.path.insert(0, str(REPO_ROOT / "analyzers" / "legacy"))
sys.path.insert(0, str(REPO_ROOT / "analyzers" / "terraform"))
sys.path.insert(0, str(REPO_ROOT / "analyzers" / "html"))
sys.path.insert(0, str(REPO_ROOT / "analyzers" / "php"))
sys.path.insert(0, str(REPO_ROOT / "analyzers" / "shell"))
sys.path.insert(0, str(REPO_ROOT / "analyzers" / "kotlin"))
sys.path.insert(0, str(REPO_ROOT / "analyzers" / "rust"))
sys.path.insert(0, str(REPO_ROOT / "analyzers" / "cpp"))

from polaris_scanner.cache import is_binary_bytes, is_minified_asset
from polaris_scanner.safe_reader import classify_file_scope, read_text_safe
from polaris_legacy_analyzer import analyze_legacy_content
from polaris_tf_analyzer import analyze_tf_content
from polaris_html_analyzer import analyze_frontend_content
from polaris_php_analyzer import analyze_php_content
from polaris_shell_analyzer import analyze_shell_content
from polaris_kotlin_analyzer import analyze_kotlin_content
from polaris_rust_analyzer import analyze_rust_content
from polaris_cpp_analyzer import analyze_cpp_content
from poc.torture_corpus_generator import generate_hostile_corpus


def run_field_trial(report_md: Path, audit_json: Path) -> dict:
    t0 = time.perf_counter()
    with tempfile.TemporaryDirectory() as tmp:
        corpus_dir = Path(tmp) / "hostile"
        files = generate_hostile_corpus(corpus_dir)

        issues: list[dict] = []
        skipped: list[dict] = []
        file_errors: list[dict] = []
        parsed_fallback = 0

        for p in files:
            rel = p.relative_to(corpus_dir).as_posix()
            raw = p.read_bytes()
            if is_binary_bytes(raw):
                skipped.append({"file": rel, "reason": "binary"})
                continue
            if is_minified_asset(p, raw):
                skipped.append({"file": rel, "reason": "minified_asset"})
                continue
            text, err = read_text_safe(p)
            if err or text is None:
                file_errors.append({"file": rel, "error": err})
                continue
            scope = classify_file_scope(rel)
            ext = p.suffix.lower()
            found: list[dict] = []
            if ext == ".tf":
                found = analyze_tf_content(text, rel)
            elif ext in (".tsx", ".jsx", ".html", ".htm"):
                found = analyze_frontend_content(text, rel)
            elif ext == ".php":
                found = analyze_php_content(text, rel)
            elif ext in (".sh", ".bash"):
                found = analyze_shell_content(text, rel)
            elif ext in (".kt", ".kts"):
                found = analyze_kotlin_content(text, rel)
            elif ext == ".rs":
                found = analyze_rust_content(text, rel)
            elif ext in (".c", ".cpp", ".h", ".hpp"):
                found = analyze_cpp_content(text, rel)
            else:
                parsed_fallback += 1
                found = analyze_legacy_content(text, rel)

            for item in found:
                item["scope"] = scope
                issues.append(item)

    elapsed_ms = round((time.perf_counter() - t0) * 1000.0, 2)
    summary = {
        "elapsed_ms": elapsed_ms,
        "files_discovered": len(files),
        "files_parsed_fallback": parsed_fallback,
        "files_skipped": len(skipped),
        "file_errors": len(file_errors),
        "total_issues": len(issues),
        "prod_issues": sum(1 for i in issues if i.get("scope") == "prod"),
        "test_issues": sum(1 for i in issues if i.get("scope") == "test"),
    }
    audit_json.write_text(json.dumps(summary, indent=2) + "\n", encoding="utf-8")
    report_md.write_text(
        f"# PoC Field Trial Report\n\n"
        f"- **Elapsed:** `{elapsed_ms} ms`\n"
        f"- **Files Discovered:** `{summary['files_discovered']}`\n"
        f"- **Files Skipped (binary/minified):** `{summary['files_skipped']}`\n"
        f"- **File Errors:** `{summary['file_errors']}`\n"
        f"- **Total Issues:** `{summary['total_issues']}` (prod: `{summary['prod_issues']}`, test: `{summary['test_issues']}`)\n",
        encoding="utf-8",
    )
    return summary


if __name__ == "__main__":
    poc_dir = Path(__file__).resolve().parent
    res = run_field_trial(poc_dir / "BASELINE_REPORT.md", poc_dir / "baseline_audit.json")
    print(json.dumps(res))
