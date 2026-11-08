"""Developer Experience and Formatters (GOAL 38).

Provides SARIF v2.1.0 generation and developer-facing markdown/terminal formats.
"""

from __future__ import annotations

from typing import Any

from polaris.evidence.platform import CanonicalSecurityFinding


class SarifReportFormatter:
    """Generates standard SARIF v2.1.0 output for GitHub Security tab integration."""

    @classmethod
    def to_sarif(cls, findings: list[CanonicalSecurityFinding]) -> dict[str, Any]:
        """Convert canonical security findings into SARIF schema."""
        rules = []
        results = []
        rule_ids = set()

        for f in findings:
            if f.rule_or_cve not in rule_ids:
                rule_ids.add(f.rule_or_cve)
                rules.append({
                    "id": f.rule_or_cve,
                    "name": f.rule_or_cve,
                    "shortDescription": {"text": f.title},
                    "defaultConfiguration": {
                        "level": "error" if f.severity in ("CRITICAL", "HIGH") else "warning",
                    },
                })

            results.append({
                "ruleId": f.rule_or_cve,
                "message": {"text": f.title},
                "locations": [
                    {
                        "physicalLocation": {
                            "artifactLocation": {"uri": f.file_path},
                            "region": {
                                "startLine": f.line,
                            },
                        }
                    }
                ],
            })

        return {
            "$schema": "https://raw.githubusercontent.com/oasis-tcs/sarif-spec/master/Schemata/sarif-schema-2.1.0.json",
            "version": "2.1.0",
            "runs": [
                {
                    "tool": {
                        "driver": {
                            "name": "POLARIS",
                            "semanticVersion": "3.0.0",
                            "rules": rules,
                        }
                    },
                    "results": results,
                }
            ],
        }
