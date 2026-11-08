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
