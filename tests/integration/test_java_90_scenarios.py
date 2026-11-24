import json
import subprocess
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
JAVA_JAR = ROOT / "analyzers" / "java" / "target" / "polaris-java-analyzer.jar"


def run_java_analyzer(files: dict[str, str]) -> list[dict]:
    with tempfile.TemporaryDirectory() as tmp:
        tmp_path = Path(tmp)
        paths = []
        for rel, content in files.items():
            p = tmp_path / rel
            p.parent.mkdir(parents=True, exist_ok=True)
            p.write_text(content, encoding="utf-8")
            paths.append(str(p))
        proc = subprocess.run(
            ["java", "-jar", str(JAVA_JAR), "--root", str(tmp_path), *paths],
            capture_output=True,
            text=True,
            check=True,
        )
        return json.loads(proc.stdout)["issues"]


class TestJava90Scenarios(unittest.TestCase):
    def test_90_java_scenarios(self) -> None:
        scenarios = []
        # 30 SQLi: 15 positive (incl. pre-concatenated prepareStatement), 15 negative (literal prepareStatement)
        for i in range(15):
            scenarios.append((
                f"sqli_pos_{i}",
                {
                    "UserController.java": f"public class UserController {{ public void handle{i}(String id) {{ new UserService().find{i}(id); }} }}",
                    "UserService.java": f"public class UserService {{ public void find{i}(String id) {{ new UserRepo().run{i}(id); }} }}",
                    "UserRepo.java": (
                        f"import java.sql.*; public class UserRepo {{ public void run{i}(String id) throws Exception {{ "
                        + (f"Connection c = null; c.prepareStatement(\"SELECT * FROM t WHERE id=\" + id);" if i % 2 == 0 else f"Statement s = null; s.executeQuery(\"SELECT * FROM t WHERE id=\" + id);")
                        + " } }"
                    ),
                },
                "CWE-89",
                True,
            ))
            scenarios.append((
                f"sqli_neg_{i}",
                {
                    "UserController.java": f"public class UserController {{ public void handle{i}(String id) {{ new UserService().find{i}(id); }} }}",
                    "UserService.java": f"public class UserService {{ public void find{i}(String id) {{ new UserRepo().run{i}(id); }} }}",
                    "UserRepo.java": f"import java.sql.*; public class UserRepo {{ public void run{i}(String id) throws Exception {{ PreparedStatement ps = null; ps.prepareStatement(\"SELECT * FROM t WHERE id=?\"); ps.executeQuery(); }} }}",
                },
                "CWE-89",
                False,
            ))

        # 30 Command Injection: 15 positive, 15 negative
        for i in range(15):
            scenarios.append((
                f"cmdi_pos_{i}",
                {
                    "CmdController.java": f"public class CmdController {{ public void run{i}(String arg) {{ new CmdService().exec{i}(arg); }} }}",
                    "CmdService.java": f"public class CmdService {{ public void exec{i}(String arg) throws Exception {{ Runtime.getRuntime().exec(\"ls \" + arg); }} }}",
                },
                "CWE-78",
                True,
            ))
            scenarios.append((
                f"cmdi_neg_{i}",
                {
                    "CmdController.java": f"public class CmdController {{ public String run{i}(String arg) {{ return arg.trim(); }} }}",
                },
                "CWE-78",
                False,
            ))

        # 30 Path Traversal: 15 positive, 15 negative
        for i in range(15):
            scenarios.append((
                f"path_pos_{i}",
                {
                    "FileController.java": f"public class FileController {{ public void read{i}(String name) {{ new FileService().load{i}(name); }} }}",
                    "FileService.java": f"import java.nio.file.*; public class FileService {{ public void load{i}(String name) throws Exception {{ Files.readString(Path.of(\"/var/data/\" + name)); }} }}",
                },
                "CWE-22",
                True,
            ))
            scenarios.append((
                f"path_neg_{i}",
                {
                    "FileController.java": f"public class FileController {{ public String read{i}(String name) {{ return \"fixed.txt\"; }} }}",
                },
                "CWE-22",
                False,
            ))

        self.assertEqual(len(scenarios), 90)
        for name, files, expected_cwe, expected_hit in scenarios:
            with self.subTest(scenario=name):
                issues = run_java_analyzer(files)
                hits = [it for it in issues if it.get("cwe") == expected_cwe]
                if expected_hit:
                    self.assertTrue(len(hits) >= 1, f"Expected {expected_cwe} in {name}, got {issues}")
                    self.assertTrue(len(hits[0].get("flowSteps", [])) >= 2)
                else:
                    self.assertEqual(len(hits), 0, f"Unexpected {expected_cwe} in {name}: {hits}")


if __name__ == "__main__":
    unittest.main()
