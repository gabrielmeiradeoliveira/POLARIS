"""Infrastructure as Code (IaC) Security Scanner (GOAL 53 - Fase 9).

Performs deterministic static analysis on Docker Compose and Kubernetes manifests
using structured YAML parsing to detect privilege escalation, host namespace sharing,
and insecure configurations.
"""

from __future__ import annotations

import logging
from typing import Any

import yaml

from polaris.security.contracts import ScannerMetadata, SecurityDomain, SecurityScannerV2
from polaris.security.models import CanonicalSecurityFindingV2

logger = logging.getLogger(__name__)


class IaCSecurityScanner(SecurityScannerV2):
    """Static security analyzer for Docker Compose and Kubernetes configurations."""

    @property
    def metadata(self) -> ScannerMetadata:
        return ScannerMetadata(
            scanner_id="iac_security",
            name="Polaris Infrastructure as Code Security Scanner",
            version="2.0.0",
            domain=SecurityDomain.IAC,
            supported_file_patterns=["*compose*.yml", "*compose*.yaml", "*.k8s.yaml", "*.k8s.yml", "deployment.yaml"],
            description="Evaluates Docker Compose and Kubernetes declarations for security risks.",
            external_dependencies=["yaml"],
            is_optional=False,
        )

    def is_available(self) -> bool:
        return True

    def scan_file(self, file_path: str, content: str) -> list[CanonicalSecurityFindingV2]:
        norm_path = file_path.replace("\\", "/").lower()
        fname = norm_path.split("/")[-1]

        if not (fname.endswith((".yml", ".yaml"))):
            return []

        # Check if file resembles Docker Compose or Kubernetes
        try:
            docs = list(yaml.safe_load_all(content))
        except Exception:
            # Not valid yaml or parsing error - return empty and avoid crashing
            return []

        findings: list[CanonicalSecurityFindingV2] = []
        for doc in docs:
            if not isinstance(doc, dict):
                continue
            # Docker compose check: has "services" dict
            if "services" in doc and isinstance(doc["services"], dict):
                findings.extend(self._audit_compose_doc(file_path, doc))
            # Kubernetes check: has "apiVersion" and "kind"
            elif "apiVersion" in doc and "kind" in doc:
                findings.extend(self._audit_kubernetes_doc(file_path, doc))

        return findings

    def _audit_compose_doc(self, file_path: str, doc: dict[str, Any]) -> list[CanonicalSecurityFindingV2]:
        results: list[CanonicalSecurityFindingV2] = []
        services = doc.get("services", {})
        for svc_name, svc_cfg in services.items():
            if not isinstance(svc_cfg, dict):
                continue

            # 1. Privileged mode
            if svc_cfg.get("privileged") is True:
                results.append(
                    CanonicalSecurityFindingV2.create(
                        scanner_id=self.metadata.scanner_id,
                        domain=SecurityDomain.IAC,
                        rule_or_cve="IAC_COMPOSE_PRIVILEGED",
                        title=f"Docker Compose service '{svc_name}' runs in privileged mode",
                        file_path=file_path,
                        line=1,
                        severity="CRITICAL",
                        confidence="HIGH",
                        evidence_text=f"services.{svc_name}.privileged: true",
                        remediation_hint="Remove privileged: true and grant only granular required Linux capabilities.",
                        risk_score=90.0,
                    )
                )

            # 2. Host network or host PID
            if str(svc_cfg.get("network_mode", "")).lower() == "host":
                results.append(
                    CanonicalSecurityFindingV2.create(
                        scanner_id=self.metadata.scanner_id,
                        domain=SecurityDomain.IAC,
                        rule_or_cve="IAC_COMPOSE_HOST_NETWORK",
                        title=f"Docker Compose service '{svc_name}' uses host network namespace",
                        file_path=file_path,
                        line=1,
                        severity="HIGH",
                        confidence="HIGH",
                        evidence_text=f"services.{svc_name}.network_mode: host",
                        remediation_hint="Use bridge or overlay networks instead of sharing host network stack.",
                        risk_score=75.0,
                    )
                )

            if str(svc_cfg.get("pid", "")).lower() == "host":
                results.append(
                    CanonicalSecurityFindingV2.create(
                        scanner_id=self.metadata.scanner_id,
                        domain=SecurityDomain.IAC,
                        rule_or_cve="IAC_COMPOSE_HOST_PID",
                        title=f"Docker Compose service '{svc_name}' shares host PID namespace",
                        file_path=file_path,
                        line=1,
                        severity="HIGH",
                        confidence="HIGH",
                        evidence_text=f"services.{svc_name}.pid: host",
                        remediation_hint="Isolate container process tree from host PID namespace.",
                        risk_score=80.0,
                    )
                )

            # 3. Docker socket mount
            volumes = svc_cfg.get("volumes", [])
            if isinstance(volumes, list):
                for vol in volumes:
                    vol_str = str(vol)
                    if "/var/run/docker.sock" in vol_str:
                        results.append(
                            CanonicalSecurityFindingV2.create(
                                scanner_id=self.metadata.scanner_id,
                                domain=SecurityDomain.IAC,
                                rule_or_cve="IAC_COMPOSE_DOCKER_SOCKET",
                                title=f"Docker Compose service '{svc_name}' mounts host Docker socket",
                                file_path=file_path,
                                line=1,
                                severity="CRITICAL",
                                confidence="HIGH",
                                evidence_text=f"services.{svc_name}.volumes: {vol_str}",
                                remediation_hint="Mounting docker.sock gives container root access to host. Avoid in application containers.",
                                risk_score=95.0,
                            )
                        )
        return results

    def _audit_kubernetes_doc(self, file_path: str, doc: dict[str, Any]) -> list[CanonicalSecurityFindingV2]:
        results: list[CanonicalSecurityFindingV2] = []
        kind = doc.get("kind", "")
        # Inspect Pod, Deployment, DaemonSet, StatefulSet
        spec = doc.get("spec", {})
        pod_spec = spec.get("template", {}).get("spec", spec) if isinstance(spec, dict) else {}

        if not isinstance(pod_spec, dict):
            return results

        # 1. Host network / PID
        if pod_spec.get("hostNetwork") is True:
            results.append(
                CanonicalSecurityFindingV2.create(
                    scanner_id=self.metadata.scanner_id,
                    domain=SecurityDomain.IAC,
                    rule_or_cve="IAC_K8S_HOST_NETWORK",
                    title=f"Kubernetes {kind} shares host network namespace",
                    file_path=file_path,
                    line=1,
                    severity="HIGH",
                    confidence="HIGH",
                    evidence_text="spec.hostNetwork: true",
                    remediation_hint="Disable hostNetwork to prevent pod from sniffing or binding to host interfaces.",
                    risk_score=80.0,
                )
            )

        if pod_spec.get("hostPID") is True:
            results.append(
                CanonicalSecurityFindingV2.create(
                    scanner_id=self.metadata.scanner_id,
                    domain=SecurityDomain.IAC,
                    rule_or_cve="IAC_K8S_HOST_PID",
                    title=f"Kubernetes {kind} shares host PID namespace",
                    file_path=file_path,
                    line=1,
                    severity="HIGH",
                    confidence="HIGH",
                    evidence_text="spec.hostPID: true",
                    remediation_hint="Disable hostPID to keep container processes isolated from node host.",
                    risk_score=85.0,
                )
            )

        # 2. Containers privileged or runAsUser: 0
        containers = pod_spec.get("containers", [])
        if isinstance(containers, list):
            for c in containers:
                if not isinstance(c, dict):
                    continue
                c_name = c.get("name", "unknown")
                sec_ctx = c.get("securityContext", {})
                if isinstance(sec_ctx, dict):
                    if sec_ctx.get("privileged") is True:
                        results.append(
                            CanonicalSecurityFindingV2.create(
                                scanner_id=self.metadata.scanner_id,
                                domain=SecurityDomain.IAC,
                                rule_or_cve="IAC_K8S_PRIVILEGED_CONTAINER",
                                title=f"Kubernetes container '{c_name}' in {kind} is privileged",
                                file_path=file_path,
                                line=1,
                                severity="CRITICAL",
                                confidence="HIGH",
                                evidence_text=f"container {c_name} securityContext.privileged: true",
                                remediation_hint="Do not run pods in privileged mode. Use specific capabilities and SELinux/AppArmor.",
                                risk_score=90.0,
                            )
                        )
                    if sec_ctx.get("runAsUser") == 0:
                        results.append(
                            CanonicalSecurityFindingV2.create(
                                scanner_id=self.metadata.scanner_id,
                                domain=SecurityDomain.IAC,
                                rule_or_cve="IAC_K8S_ROOT_USER",
                                title=f"Kubernetes container '{c_name}' in {kind} configured with runAsUser: 0",
                                file_path=file_path,
                                line=1,
                                severity="MEDIUM",
                                confidence="HIGH",
                                evidence_text=f"container {c_name} securityContext.runAsUser: 0",
                                remediation_hint="Set runAsNonRoot: true and define a non-zero runAsUser uid.",
                                risk_score=60.0,
                            )
                        )
        return results
