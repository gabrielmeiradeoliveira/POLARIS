from __future__ import annotations

import sys
from dataclasses import dataclass
from typing import Mapping


@dataclass(frozen=True)
class AnalyzerSpec:
    """Metadata and invocation specification for a trusted POLARIS analyzer."""

    id: str
    version: str
    language: str
    extensions: tuple[str, ...]
    contract_version: str
    command: tuple[str, ...]
    capabilities: tuple[str, ...]


class AnalyzerRegistry:
    """Registry of trusted analyzers supported by POLARIS."""

    def __init__(self, specs: tuple[AnalyzerSpec, ...] | None = None) -> None:
        if specs is None:
            specs = default_analyzer_specs()
        self._by_id: dict[str, AnalyzerSpec] = {}
        self._by_language: dict[str, AnalyzerSpec] = {}
        for spec in specs:
            if spec.id in self._by_id:
                raise ValueError(f"Duplicate analyzer id: {spec.id}")
            self._by_id[spec.id] = spec
            self._by_language[spec.language] = spec

    def get_by_id(self, analyzer_id: str) -> AnalyzerSpec | None:
        return self._by_id.get(analyzer_id)

    def get_by_language(self, language: str) -> AnalyzerSpec | None:
        return self._by_language.get(language.lower())

    def list_all(self) -> tuple[AnalyzerSpec, ...]:
        return tuple(self._by_id.values())

    def as_mapping(self) -> Mapping[str, AnalyzerSpec]:
        return dict(self._by_id)


def default_analyzer_specs() -> tuple[AnalyzerSpec, ...]:
    """Return the default trusted analyzer specifications for POLARIS 2.x."""
    python_exe = sys.executable or "python"
    return (
        AnalyzerSpec(
            id="polaris-python-analyzer",
            version="2.0.0",
            language="python",
            extensions=(".py",),
            contract_version="1.0.0",
            command=(python_exe, "analyzers/python/polaris_python_analyzer.py"),
            capabilities=("ast", "libcst", "astroid"),
        ),
        AnalyzerSpec(
            id="polaris-csharp-analyzer",
            version="2.0.0",
            language="csharp",
            extensions=(".cs",),
            contract_version="1.0.0",
            command=("dotnet", "analyzers/csharp/bin/Release/net10.0/PolarisCSharpAnalyzer.dll"),
            capabilities=("roslyn", "syntax-tree", "semantic-model"),
        ),
        AnalyzerSpec(
            id="polaris-java-analyzer",
            version="2.0.0",
            language="java",
            extensions=(".java",),
            contract_version="1.0.0",
            command=("java", "-jar", "analyzers/java/target/polaris-java-analyzer.jar"),
            capabilities=("javaparser", "symbol-solver"),
        ),
        AnalyzerSpec(
            id="polaris-sql-analyzer",
            version="2.0.0",
            language="sql",
            extensions=(".sql",),
            contract_version="1.0.0",
            command=(python_exe, "analyzers/sql/polaris_sql_analyzer.py"),
            capabilities=("sqlglot", "multi-dialect"),
        ),
        AnalyzerSpec(
            id="polaris-terraform-analyzer",
            version="3.0.0",
            language="terraform",
            extensions=(".tf", ".tfvars"),
            contract_version="1.0.0",
            command=(python_exe, "analyzers/terraform/polaris_tf_analyzer.py"),
            capabilities=("hcl", "iac-security"),
        ),
        AnalyzerSpec(
            id="polaris-typescript-analyzer",
            version="3.0.0",
            language="typescript",
            extensions=(".ts", ".tsx", ".js", ".jsx"),
            contract_version="1.0.0",
            command=(python_exe, "analyzers/html/polaris_html_analyzer.py"),
            capabilities=("react", "ts-security"),
        ),
        AnalyzerSpec(
            id="polaris-html-analyzer",
            version="3.0.0",
            language="html",
            extensions=(".html", ".htm"),
            contract_version="1.0.0",
            command=(python_exe, "analyzers/html/polaris_html_analyzer.py"),
            capabilities=("html-security",),
        ),
        AnalyzerSpec(
            id="polaris-php-analyzer",
            version="3.0.0",
            language="php",
            extensions=(".php",),
            contract_version="1.0.0",
            command=(python_exe, "analyzers/php/polaris_php_analyzer.py"),
            capabilities=("php-security",),
        ),
        AnalyzerSpec(
            id="polaris-shell-analyzer",
            version="3.0.0",
            language="shell",
            extensions=(".sh", ".bash"),
            contract_version="1.0.0",
            command=(python_exe, "analyzers/shell/polaris_shell_analyzer.py"),
            capabilities=("shell-security",),
        ),
        AnalyzerSpec(
            id="polaris-kotlin-analyzer",
            version="3.0.0",
            language="kotlin",
            extensions=(".kt", ".kts"),
            contract_version="1.0.0",
            command=(python_exe, "analyzers/kotlin/polaris_kotlin_analyzer.py"),
            capabilities=("kotlin-security",),
        ),
        AnalyzerSpec(
            id="polaris-rust-analyzer",
            version="3.0.0",
            language="rust",
            extensions=(".rs",),
            contract_version="1.0.0",
            command=(python_exe, "analyzers/rust/polaris_rust_analyzer.py"),
            capabilities=("rust-security",),
        ),
        AnalyzerSpec(
            id="polaris-cpp-analyzer",
            version="3.0.0",
            language="cpp",
            extensions=(".c", ".h", ".cpp", ".hpp", ".cc"),
            contract_version="1.0.0",
            command=(python_exe, "analyzers/cpp/polaris_cpp_analyzer.py"),
            capabilities=("cpp-security",),
        ),
    )
