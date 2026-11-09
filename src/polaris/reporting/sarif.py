"""Developer Experience and Formatters (GOAL 38).

Provides SARIF v2.1.0 generation and developer-facing markdown/terminal formats.
"""

from __future__ import annotations

from typing import Any

from polaris.evidence.platform import CanonicalSecurityFinding


class SarifReportFormatter:
    """Generates standard SARIF v2.1.0 output for GitHub Security tab integration."""

    @classmethod
    def to_sarif(
        cls,
        findings: list[CanonicalSecurityFinding],
        *,
        baseline_states: dict[str, str] | None = None,
    ) -> dict[str, Any]:
        """Convert canonical security findings into SARIF schema with optional baselineState."""
        rules = []
        results = []
        rule_ids = set()
        states = baseline_states or {}

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

            result_item: dict[str, Any] = {
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
            }

            b_state = states.get(f.finding_id)
            if b_state in ("new", "existing", "unchanged", "updated", "absent"):
                result_item["baselineState"] = b_state

            results.append(result_item)

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
