from __future__ import annotations

import json
import subprocess
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
DLL = ROOT / "analyzers" / "csharp" / "bin" / "Release" / "net10.0" / "PolarisCSharpAnalyzer.dll"


class TestCSharpTaintE2E(unittest.TestCase):
    def _run_analyzer(self, root_dir: Path, files: list[Path]) -> dict:
        cmd = ["dotnet", "exec", str(DLL), "--root", str(root_dir), *[str(f) for f in files]]
        res = subprocess.run(cmd, capture_output=True, text=True, timeout=30)
        self.assertEqual(res.returncode, 0, msg=res.stderr)
        return json.loads(res.stdout)

    def test_cross_file_sqli_detected_and_parameterized_safe(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            tdir = Path(td)
            ctrl = tdir / "UserController.cs"
            svc = tdir / "UserService.cs"
            repo = tdir / "UserRepository.cs"

            ctrl.write_text(
                "public class UserController {\n"
                "  private readonly UserService _svc = new();\n"
                "  public string Get(string userId) => _svc.Find(userId);\n"
                "}\n",
                encoding="utf-8",
            )
            svc.write_text(
                "public class UserService {\n"
                "  private readonly UserRepository _repo = new();\n"
                "  public string Find(string id) => _repo.QueryUser(id);\n"
                "}\n",
                encoding="utf-8",
            )
            repo.write_text(
                "public class UserRepository {\n"
                "  public string QueryUser(string id) { ExecuteSqlRaw(\"SELECT * FROM Users WHERE Id=\" + id); return \"ok\"; }\n"
                "  private void ExecuteSqlRaw(string sql) {}\n"
                "}\n",
                encoding="utf-8",
            )

            out_vuln = self._run_analyzer(tdir, [ctrl, svc, repo])
            taint_issues = [i for i in out_vuln["issues"] if i["ruleId"] == "CS-TAINT-001"]
            self.assertEqual(len(taint_issues), 1)
            self.assertEqual(taint_issues[0]["cwe"], "CWE-89")
            files_in_flow = {s["file"] for s in taint_issues[0]["flowSteps"]}
            self.assertEqual(files_in_flow, {"UserController.cs", "UserService.cs", "UserRepository.cs"})

            # Safe parameterized variant
            repo.write_text(
                "public class UserRepository {\n"
                "  public string QueryUser(string id) { ExecuteSqlRaw(\"SELECT * FROM Users WHERE Id=@id\", new SqlParameter(\"@id\", id)); return \"ok\"; }\n"
                "  private void ExecuteSqlRaw(string sql, object p) {}\n"
                "}\n",
                encoding="utf-8",
            )
            out_safe = self._run_analyzer(tdir, [ctrl, svc, repo])
            taint_safe = [i for i in out_safe["issues"] if i["ruleId"] == "CS-TAINT-001"]
            self.assertEqual(len(taint_safe), 0)


if __name__ == "__main__":
    unittest.main()
