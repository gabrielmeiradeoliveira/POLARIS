from __future__ import annotations

from dataclasses import dataclass

POLARIS_MARKER = "<!-- polaris-pr-summary -->"


@dataclass(frozen=True)
class PrSummary:
    project_key: str
    pr_key: str
    gate_status: str
    new_bugs: int
    new_vulnerabilities: int
    new_code_smells: int
    new_coverage: float
    new_duplication: float


def render_pr_summary_markdown(summary: PrSummary) -> str:
    return "\n".join(
        [
            POLARIS_MARKER,
            f"### POLARIS Quality Gate: **{summary.gate_status}** (`{summary.project_key}` / `{summary.pr_key}`)",
            "",
            "| Métrica (Código Novo) | Valor |",
            "| :--- | :--- |",
            f"| Bugs | {summary.new_bugs} |",
            f"| Vulnerabilities | {summary.new_vulnerabilities} |",
            f"| Code Smells | {summary.new_code_smells} |",
            f"| Coverage | {summary.new_coverage:.2f}% |",
            f"| Duplication | {summary.new_duplication:.2f}% |",
        ]
    )
