from __future__ import annotations

import platform
import statistics
import sys
import tempfile
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "src"))

from polaris_scanner.discovery import discover_files
from polaris_scanner.executor import run_analyzer_subprocess
from polaris_scanner.registry import AnalyzerRegistry


def create_corpus(root: Path, total_files: int) -> None:
    per_lang = total_files // 4
    for i in range(per_lang):
        (root / f"mod_{i}.py").write_text(f"def fn_{i}(x=[]):\n    return eval('1')\n", encoding="utf-8")
        (root / f"Cls_{i}.cs").write_text(f"class Cls{i} {{ string F() {{ try {{ return \"a\"; }} catch {{ }} return null; }} }}\n", encoding="utf-8")
        (root / f"Cls_{i}.java").write_text(f"class Cls{i} {{ void f() {{ try {{ System.out.println(1); }} catch (Exception e) {{}} }} }}\n", encoding="utf-8")
        (root / f"q_{i}.sql").write_text("SELECT * FROM users; DELETE FROM users;\n", encoding="utf-8")


def run_scenario(repo_root: Path, total_files: int, repeats: int = 5) -> dict:
    registry = AnalyzerRegistry()
    times_total: list[float] = []
    times_discovery: list[float] = []

    with tempfile.TemporaryDirectory() as tmp:
        corpus_root = Path(tmp)
        create_corpus(corpus_root, total_files)

        for _ in range(repeats):
            t0 = time.perf_counter()
            disc = discover_files(corpus_root)
            t1 = time.perf_counter()

            by_lang: dict[str, list[str]] = {}
            for f in disc.files:
                by_lang.setdefault(f.language, []).append(str(f.absolute_path))

            for lang, paths in by_lang.items():
                spec = registry.get_by_language(lang)
                if spec is None:
                    continue
                res = run_analyzer_subprocess(
                    [*spec.command, "--project", "bench", "--root", str(corpus_root), *paths],
                    cwd=repo_root,
                    timeout_seconds=120,
                )
                if res.status != "OK":
                    raise RuntimeError(f"Benchmark analyzer failed for {lang}: {res.error_message}")

            t2 = time.perf_counter()
            times_discovery.append(t1 - t0)
            times_total.append(t2 - t0)

    median_total = statistics.median(times_total)
    stdev_total = statistics.stdev(times_total) if len(times_total) > 1 else 0.0
    return {
        "files": total_files,
        "repeats": repeats,
        "median_discovery_s": round(statistics.median(times_discovery), 4),
        "median_total_s": round(median_total, 4),
        "stdev_total_s": round(stdev_total, 4),
        "throughput_files_per_s": round(total_files / median_total, 2) if median_total > 0 else 0.0,
    }


def main() -> int:
    repo_root = Path(__file__).resolve().parents[2]
    print(f"OS={platform.system()} {platform.release()} CPU={platform.processor()}")
    for count in (40, 200):
        stats = run_scenario(repo_root, count, repeats=5)
        print(f"BENCHMARK_{count}={stats}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
