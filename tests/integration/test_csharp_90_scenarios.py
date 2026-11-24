import json
import subprocess
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
CSHARP_DLL = ROOT / "analyzers" / "csharp" / "bin" / "Release" / "net10.0" / "PolarisCSharpAnalyzer.dll"


def run_csharp_analyzer(files: dict[str, str]) -> list[dict]:
    with tempfile.TemporaryDirectory() as tmp:
        tmp_path = Path(tmp)
        paths = []
        for rel, content in files.items():
            p = tmp_path / rel
            p.parent.mkdir(parents=True, exist_ok=True)
            p.write_text(content, encoding="utf-8")
            paths.append(str(p))
        proc = subprocess.run(
            ["dotnet", str(CSHARP_DLL), "--root", str(tmp_path), *paths],
            capture_output=True,
            text=True,
            check=True,
        )
        return json.loads(proc.stdout)["issues"]


class TestCSharp90Scenarios(unittest.TestCase):
    def test_90_csharp_scenarios(self) -> None:
        scenarios = []
        # 30 SQLi: 15 positive, 15 negative
        for i in range(15):
            scenarios.append((
                f"sqli_pos_{i}",
                {
                    "Controller.cs": f"public class UserController {{ public void Get{i}(string id) => new UserService().Find{i}(id); }}",
                    "Service.cs": f"public class UserService {{ public void Find{i}(string id) => new UserRepo().Run{i}(id); }}",
                    "Repo.cs": f"public class SqlCommand {{ public SqlCommand(string q) {{}} public void ExecuteReader() {{}} }}\npublic class UserRepo {{ public void Run{i}(string id) {{ var cmd = new SqlCommand(\"SELECT * FROM t WHERE id=\" + id); cmd.ExecuteReader(); }} }}",
                },
                "CWE-89",
                True,
            ))
            scenarios.append((
                f"sqli_neg_{i}",
                {
                    "Controller.cs": f"public class UserController {{ public string Get{i}(string id) => \"SELECT * FROM t WHERE id=@id\"; }}",
                },
                "CWE-89",
                False,
            ))

        # 30 Command Injection: 15 positive, 15 negative
        for i in range(15):
            scenarios.append((
                f"cmdi_pos_{i}",
                {
                    "CmdController.cs": f"public class CmdController {{ public void Run{i}(string arg) => new CmdService().Exec{i}(arg); }}",
                    "CmdService.cs": f"using System.Diagnostics;\npublic class CmdService {{ public void Exec{i}(string arg) {{ Process.Start(\"cmd.exe\", \"/c \" + arg); }} }}",
                },
                "CWE-78",
                True,
            ))
            scenarios.append((
                f"cmdi_neg_{i}",
                {
                    "CmdController.cs": f"public class CmdController {{ public string Run{i}(string arg) => arg.Trim(); }}",
                },
                "CWE-78",
                False,
            ))

        # 30 Path Traversal: 15 positive, 15 negative
        for i in range(15):
            scenarios.append((
                f"path_pos_{i}",
                {
                    "FileController.cs": f"public class FileController {{ public void Read{i}(string name) => new FileService().Load{i}(name); }}",
                    "FileService.cs": f"using System.IO;\npublic class FileService {{ public void Load{i}(string name) {{ File.ReadAllText(\"/var/data/\" + name); }} }}",
                },
                "CWE-22",
                True,
            ))
            scenarios.append((
                f"path_neg_{i}",
                {
                    "FileController.cs": f"public class FileController {{ public string Read{i}(string name) => \"fixed.txt\"; }}",
                },
                "CWE-22",
                False,
            ))

        self.assertEqual(len(scenarios), 90)
        for name, files, expected_cwe, expected_hit in scenarios:
            with self.subTest(scenario=name):
                issues = run_csharp_analyzer(files)
                hits = [it for it in issues if it.get("cwe") == expected_cwe]
                if expected_hit:
                    self.assertTrue(len(hits) >= 1, f"Expected {expected_cwe} in {name}, got {issues}")
                else:
                    self.assertEqual(len(hits), 0, f"Unexpected {expected_cwe} in {name}: {hits}")


if __name__ == "__main__":
    unittest.main()
