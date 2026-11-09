"""Container Security Intelligence (GOAL 32).

Analyzes Dockerfiles for configuration defects (root user, latest tag, unpinned base,
embedded secrets, permissive flags) and ingests container SBOM / local scanner fixtures.
"""

from __future__ import annotations

import re
from enum import StrEnum

from pydantic import BaseModel, ConfigDict


class DockerfileDefectType(StrEnum):
    """Types of Dockerfile configuration vulnerabilities and anti-patterns."""

    UNPINNED_LATEST_TAG = "UNPINNED_LATEST_TAG"
    ROOT_USER_EXECUTION = "ROOT_USER_EXECUTION"
    HARDCODED_SECRET = "HARDCODED_SECRET"  # noqa: S105
    INSECURE_CURL_BASH = "INSECURE_CURL_BASH"
    MISSING_HEALTHCHECK = "MISSING_HEALTHCHECK"
    INSECURE_CHMOD_777 = "INSECURE_CHMOD_777"
    ADD_INSTEAD_OF_COPY = "ADD_INSTEAD_OF_COPY"
    INSECURE_PACKAGE_UPGRADE = "INSECURE_PACKAGE_UPGRADE"


class DockerfileFinding(BaseModel):
    """Security finding detected in Dockerfile."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    defect_type: DockerfileDefectType
    line: int
    instruction: str
    severity: str
    remediation: str


class ContainerSecurityScanner:
    """Deterministic offline container & Dockerfile analyzer."""

    @classmethod
    def analyze_dockerfile(cls, content: str, file_path: str = "Dockerfile") -> list[DockerfileFinding]:
        """Inspect Dockerfile instructions for known security anti-patterns."""
        findings: list[DockerfileFinding] = []
        lines = content.splitlines()

        has_user_instruction = False

        for idx, raw_line in enumerate(lines, start=1):
            line = raw_line.strip()
            if not line or line.startswith("#"):
                continue

            # 1. Base Image with latest or unpinned tag
            if line.upper().startswith("FROM "):
                image = line.split()[1]
                if ":" not in image or image.endswith(":latest"):
                    findings.append(
                        DockerfileFinding(
                            defect_type=DockerfileDefectType.UNPINNED_LATEST_TAG,
                            line=idx,
                            instruction=line,
                            severity="HIGH",
                            remediation="Pin base image to specific version tag or immutable SHA-256 digest (e.g., python:3.12-slim@sha256:...).",
                        )
                    )

            # 2. Insecure curl | bash pipe
            if re.search(r"curl\s+-[^\n|]*\|\s*(?:ba|z)?sh", line, re.IGNORECASE):
                findings.append(
                    DockerfileFinding(
                        defect_type=DockerfileDefectType.INSECURE_CURL_BASH,
                        line=idx,
                        instruction=line,
                        severity="CRITICAL",
                        remediation="Do not pipe remote scripts directly into shell. Download, verify checksum/signature, and execute with restricted privileges.",
                    )
                )

            # 3. Hardcoded secret / token assignments in ENV or RUN
            if re.search(r"(?:api[_-]?key|secret|token|password)\s*=\s*['\"][a-zA-Z0-9_\-\.]{8,}['\"]", line, re.IGNORECASE):
                findings.append(
                    DockerfileFinding(
                        defect_type=DockerfileDefectType.HARDCODED_SECRET,
                        line=idx,
                        instruction="[REDACTED SECRET INSTRUCTION]",
                        severity="CRITICAL",
                        remediation="Remove embedded credentials from Dockerfile. Inject secrets at runtime via container secret managers or environment variables.",
                    )
                )

            # 4. Insecure chmod 777 / overly permissive file rights
            if re.search(r"chmod\s+(?:-R\s+)?(?:777|a\+rwx)\b", line, re.IGNORECASE):
                findings.append(
                    DockerfileFinding(
                        defect_type=DockerfileDefectType.INSECURE_CHMOD_777,
                        line=idx,
                        instruction=line,
                        severity="HIGH",
                        remediation="Avoid chmod 777. Grant minimal necessary read/execute permissions (e.g. 755 or 644).",
                    )
                )

            # 5. Use of ADD instead of COPY for local files
            if line.upper().startswith("ADD ") and not re.search(r"https?://|\.tar(?:\.gz|\.bz2|\.xz)?\b", line, re.IGNORECASE):
                findings.append(
                    DockerfileFinding(
                        defect_type=DockerfileDefectType.ADD_INSTEAD_OF_COPY,
                        line=idx,
                        instruction=line,
                        severity="LOW",
                        remediation="Prefer COPY over ADD for copying local files; ADD can unintentionally unpack archives or trigger unexpected behavior.",
                    )
                )

            # 6. Insecure package upgrade / unpinned cache updates
            if re.search(r"\bapt-get\s+(?:dist-)?upgrade\b|\byum\s+update\b", line, re.IGNORECASE):
                findings.append(
                    DockerfileFinding(
                        defect_type=DockerfileDefectType.INSECURE_PACKAGE_UPGRADE,
                        line=idx,
                        instruction=line,
                        severity="MEDIUM",
                        remediation="Avoid apt-get upgrade or yum update in Dockerfiles; pinning base images and explicit package versions ensures reproducibility.",
                    )
                )

            # Check if USER is set
            if line.upper().startswith("USER "):
                has_user_instruction = True

        # Check for root execution default
        if not has_user_instruction:
            findings.append(
                DockerfileFinding(
                    defect_type=DockerfileDefectType.ROOT_USER_EXECUTION,
                    line=len(lines) if lines else 1,
                    instruction="<missing USER directive>",
                    severity="HIGH",
                    remediation="Specify a non-root user (e.g., USER appuser or USER 10001) to drop privileges before executing container payloads.",
                )
            )

        return findings
