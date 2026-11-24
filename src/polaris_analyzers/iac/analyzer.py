from __future__ import annotations

import re
from dataclasses import dataclass


@dataclass(frozen=True)
class IacIssue:
    rule_id: str
    severity: str
    file_path: str
    line: int
    message: str


def analyze_dockerfile(file_path: str, content: str) -> list[IacIssue]:
    issues: list[IacIssue] = []
    has_non_root_user = False
    for line_no, raw in enumerate(content.splitlines(), start=1):
        line = raw.strip()
        if not line or line.startswith("#"):
            continue
        upper = line.upper()
        if upper.startswith("FROM ") and (":latest" in line.lower() or ":" not in line.split()[1]):
            issues.append(IacIssue("iac:DOCKER-001", "MAJOR", file_path, line_no, "Evite tag :latest ou ausência de tag fixa em FROM."))
        if upper.startswith("USER ") and line.split()[1].lower() not in ("root", "0"):
            has_non_root_user = True
        if upper.startswith(("ENV ", "ARG ")) and re.search(r"(PASSWORD|SECRET|TOKEN|API_KEY)\s*=", upper):
            issues.append(IacIssue("iac:DOCKER-002", "BLOCKER", file_path, line_no, "Possível segredo exposto em ENV/ARG."))
        if upper.startswith("ADD ") and ("http://" in line.lower() or "https://" in line.lower()):
            issues.append(IacIssue("iac:DOCKER-003", "MINOR", file_path, line_no, "Prefira COPY ou curl/wget verificado em vez de ADD remoto."))
    if not has_non_root_user and content.strip():
        issues.append(IacIssue("iac:DOCKER-004", "MAJOR", file_path, 1, "Container executa como root (adicione USER não-privilegiado)."))
    return issues


def analyze_yaml_iac(file_path: str, content: str) -> list[IacIssue]:
    issues: list[IacIssue] = []
    for line_no, raw in enumerate(content.splitlines(), start=1):
        line = raw.strip().lower()
        if "privileged: true" in line:
            issues.append(IacIssue("iac:YAML-001", "BLOCKER", file_path, line_no, "Container privilegiado (privileged: true) detectado."))
        if "/var/run/docker.sock" in line:
            issues.append(IacIssue("iac:YAML-002", "CRITICAL", file_path, line_no, "Montagem do socket Docker (/var/run/docker.sock) detectada."))
    return issues
