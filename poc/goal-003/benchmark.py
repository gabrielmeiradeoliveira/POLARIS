import tempfile
import time
import tracemalloc
from pathlib import Path

from scanner import scan_directory


def run_benchmark(num_files_per_lang: int = 50):
    with tempfile.TemporaryDirectory() as tmpdir:
        base = Path(tmpdir)
        for i in range(num_files_per_lang):
            (base / f"mod_{i}.py").write_text("def f(x):\n    if x > 0:\n        return eval('1')\n    return 0\n", encoding="utf-8")
            (base / f"Prog_{i}.cs").write_text("class C { void M() { if (true) Console.WriteLine(1); } }\n", encoding="utf-8")
            (base / f"Main_{i}.java").write_text("class J { void m() { if (true) System.out.println(1); } }\n", encoding="utf-8")
            (base / f"q_{i}.sql").write_text("SELECT * FROM t;\n", encoding="utf-8")

        tracemalloc.start()
        t0 = time.perf_counter()
        report = scan_directory(base, project_key="bench")
        elapsed = time.perf_counter() - t0
        _, peak_bytes = tracemalloc.get_traced_memory()
        tracemalloc.stop()

        total_files = len(report["files"])
        total_issues = len(report["issues"])
        print(f"BENCHMARK_FILES={total_files}")
        print(f"BENCHMARK_ISSUES={total_issues}")
        print(f"BENCHMARK_ELAPSED_SEC={elapsed:.4f}")
        print(f"BENCHMARK_FILES_PER_SEC={total_files / elapsed:.2f}")
        print(f"BENCHMARK_PEAK_MEM_KB={peak_bytes / 1024:.2f}")


if __name__ == "__main__":
    run_benchmark()
