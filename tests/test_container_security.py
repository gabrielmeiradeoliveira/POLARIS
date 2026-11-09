"""Tests for Container Security Scanner (GOAL 32)."""

from polaris.container.scanner import ContainerSecurityScanner, DockerfileDefectType


def test_dockerfile_analysis_detects_anti_patterns():
    """Verify detection of unpinned image, curl pipe bash, and root execution."""
    dockerfile = """
FROM python:latest
RUN apt-get update && curl -sSL https://install.example.com | bash
ENV API_KEY="secret_key_123456789"
CMD ["python", "app.py"]
"""
    findings = ContainerSecurityScanner.analyze_dockerfile(dockerfile)
    types = {f.defect_type for f in findings}

    assert DockerfileDefectType.UNPINNED_LATEST_TAG in types
    assert DockerfileDefectType.INSECURE_CURL_BASH in types
    assert DockerfileDefectType.HARDCODED_SECRET in types
    assert DockerfileDefectType.ROOT_USER_EXECUTION in types


def test_dockerfile_clean_negative_control():
    """Verify that hardened Dockerfiles produce no false alarms."""
    hardened = """
FROM python:3.12-slim@sha256:112233445566778899aabbccddeeff00112233445566778899aabbccddeeff00
RUN useradd -u 10001 appuser
USER appuser
CMD ["python", "app.py"]
"""
    findings = ContainerSecurityScanner.analyze_dockerfile(hardened)
    assert len(findings) == 0
