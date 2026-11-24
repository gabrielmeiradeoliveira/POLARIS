from __future__ import annotations

from typing import Any

_SARIF_LEVEL_MAP = {
    "BLOCKER": "error",
    "CRITICAL": "error",
    "MAJOR": "warning",
    "MINOR": "note",
    "INFO": "note",
}


def export_sarif_2_1_0(report: dict[str, Any]) -> dict[str, Any]:
    """Convert a POLARIS AnalysisReportV1 dict into a SARIF 2.1.0 payload."""
    rules_seen: dict[str, dict[str, Any]] = {}
    results: list[dict[str, Any]] = []

    for issue in report.get("issues", []):
        rule_id = str(issue.get("ruleId", "polaris:unknown"))
        if rule_id not in rules_seen:
            rules_seen[rule_id] = {
                "id": rule_id,
                "shortDescription": {"text": rule_id},
            }
        loc = issue.get("location", {})
        results.append(
            {
                "ruleId": rule_id,
                "level": _SARIF_LEVEL_MAP.get(str(issue.get("severity", "MAJOR")), "warning"),
                "message": {"text": str(issue.get("message", ""))},
                "locations": [
                    {
                        "physicalLocation": {
                            "artifactLocation": {"uri": str(loc.get("file", ""))},
                            "region": {"startLine": int(loc.get("startLine", 1))},
                        }
                    }
                ],
                "properties": {
                    "confidence": issue.get("confidence", "HIGH"),
                },
            }
        )

    analyzer = report.get("analyzer", {})
    return {
        "$schema": "https://raw.githubusercontent.com/oasis-tcs/sarif-spec/master/Schemata/sarif-schema-2.1.0.json",
        "version": "2.1.0",
        "runs": [
            {
                "tool": {
                    "driver": {
                        "name": str(analyzer.get("id", "polaris-scanner")),
                        "version": str(analyzer.get("version", "2.7.0")),
                        "rules": list(rules_seen.values()),
                    }
                },
                "results": results,
            }
        ],
    }
