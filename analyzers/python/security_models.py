"""Security Model Registry for sources, sinks, sanitizers, and propagators across languages."""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict, List, Optional


@dataclass(frozen=True)
class SourceSpec:
    language: str
    symbol: str
    category: str = "user_input"
    cwe_hints: List[str] = field(default_factory=list)


@dataclass(frozen=True)
class SinkSpec:
    language: str
    symbol: str
    cwe: str
    vulnerable_arg_indices: List[int] = field(default_factory=lambda: [0])
    description: str = ""


@dataclass(frozen=True)
class SanitizerSpec:
    language: str
    symbol: str
    cwe_mitigated: List[str] = field(default_factory=list)
    description: str = ""


@dataclass(frozen=True)
class PropagatorSpec:
    language: str
    symbol: str
    from_arg: int = 0
    to_return: bool = True


class SecurityModelRegistry:
    """Central registry for taint sources, sinks, sanitizers, and propagators."""

    def __init__(self) -> None:
        self.sources: Dict[str, List[SourceSpec]] = {}
        self.sinks: Dict[str, List[SinkSpec]] = {}
        self.sanitizers: Dict[str, List[SanitizerSpec]] = {}
        self.propagators: Dict[str, List[PropagatorSpec]] = {}

    def register_source(self, spec: SourceSpec) -> None:
        self.sources.setdefault(spec.language.lower(), []).append(spec)

    def register_sink(self, spec: SinkSpec) -> None:
        self.sinks.setdefault(spec.language.lower(), []).append(spec)

    def register_sanitizer(self, spec: SanitizerSpec) -> None:
        self.sanitizers.setdefault(spec.language.lower(), []).append(spec)

    def register_propagator(self, spec: PropagatorSpec) -> None:
        self.propagators.setdefault(spec.language.lower(), []).append(spec)

    def get_sources(self, language: str) -> List[SourceSpec]:
        return list(self.sources.get(language.lower(), []))

    def get_sinks(self, language: str, cwe: Optional[str] = None) -> List[SinkSpec]:
        items = self.sinks.get(language.lower(), [])
        if cwe is None:
            return list(items)
        return [s for s in items if s.cwe == cwe]

    def get_sanitizers(self, language: str, cwe: Optional[str] = None) -> List[SanitizerSpec]:
        items = self.sanitizers.get(language.lower(), [])
        if cwe is None:
            return list(items)
        return [s for s in items if not s.cwe_mitigated or cwe in s.cwe_mitigated]

    def get_propagators(self, language: str) -> List[PropagatorSpec]:
        return list(self.propagators.get(language.lower(), []))

    def is_sink(self, language: str, symbol: str) -> Optional[SinkSpec]:
        for spec in self.sinks.get(language.lower(), []):
            if spec.symbol == symbol or symbol.endswith("." + spec.symbol):
                return spec
        return None

    def is_sanitizer(self, language: str, symbol: str, cwe: Optional[str] = None) -> bool:
        for spec in self.get_sanitizers(language, cwe):
            if spec.symbol == symbol or symbol.endswith("." + spec.symbol):
                return True
        return False

    def load_json(self, path: Path) -> None:
        data = json.loads(path.read_text(encoding="utf-8"))
        for item in data.get("sources", []):
            self.register_source(SourceSpec(**item))
        for item in data.get("sinks", []):
            self.register_sink(SinkSpec(**item))
        for item in data.get("sanitizers", []):
            self.register_sanitizer(SanitizerSpec(**item))
        for item in data.get("propagators", []):
            self.register_propagator(PropagatorSpec(**item))

    @classmethod
    def default_registry(cls) -> "SecurityModelRegistry":
        reg = cls()
        # Python
        reg.register_source(SourceSpec("python", "flask.request.args.get", "http_param"))
        reg.register_source(SourceSpec("python", "input", "cli_input"))
        reg.register_sink(SinkSpec("python", "sqlite3.Cursor.execute", "CWE-89", [0], "SQL execution"))
        reg.register_sink(SinkSpec("python", "subprocess.run", "CWE-78", [0], "OS command execution"))
        reg.register_sink(SinkSpec("python", "os.system", "CWE-78", [0], "OS command execution"))
        reg.register_sanitizer(SanitizerSpec("python", "shlex.quote", ["CWE-78"], "Shell escaping"))
        reg.register_sanitizer(SanitizerSpec("python", "html.escape", ["CWE-79"], "HTML escaping"))
        # C#
        reg.register_source(SourceSpec("csharp", "HttpRequest.Query", "http_param"))
        reg.register_sink(SinkSpec("csharp", "SqlCommand", "CWE-89", [0], "SQL command"))
        reg.register_sink(SinkSpec("csharp", "System.Diagnostics.Process.Start", "CWE-78", [0], "Process start"))
        reg.register_sanitizer(SanitizerSpec("csharp", "SqlParameter", ["CWE-89"], "Parameterized query"))
        # Java
        reg.register_source(SourceSpec("java", "HttpServletRequest.getParameter", "http_param"))
        reg.register_sink(SinkSpec("java", "Statement.executeQuery", "CWE-89", [0], "JDBC Statement"))
        reg.register_sink(SinkSpec("java", "Runtime.exec", "CWE-78", [0], "OS command"))
        reg.register_sanitizer(SanitizerSpec("java", "PreparedStatement.setString", ["CWE-89"], "Prepared statement"))
        return reg
