"""Frozen RC1 benchmark catalog integrity checks."""

from __future__ import annotations

import builtins

import pytest
from evaluations.fixtures.goal24_rc1.catalog import CATALOG


def test_goal24_catalog_is_balanced_and_has_required_difficulty_distribution() -> None:
    assert len(CATALOG) == 60
    assert len({case.id for case in CATALOG}) == 60
    assert sum(case.kind == "positive" for case in CATALOG) == 30
    assert sum(case.kind == "negative" for case in CATALOG) == 30
    assert {case.difficulty for case in CATALOG} == {"N1", "N2", "N3"}
    assert sum(case.difficulty == "N1" for case in CATALOG) == 12
    assert sum(case.difficulty == "N2" for case in CATALOG) == 24
    assert sum(case.difficulty == "N3" for case in CATALOG) == 24
    assert all(len(case.files) > 1 for case in CATALOG if case.difficulty != "N1")


def _contract(source: str):
    scope = {"__builtins__": dict(vars(builtins))}
    exec(compile(source, "<goal24-catalog>", "exec"), scope)  # noqa: S102 -- static local benchmark corpus only.
    return scope["contract"]


def test_goal24_each_case_has_a_causal_behavioral_oracle() -> None:
    for case in CATALOG:
        before = _contract(case.before)
        after = _contract(case.after)
        with pytest.raises(ValueError, match="invalid"):
            before(case.oracle_input)
        if case.kind == "positive":
            assert after(case.oracle_input) == case.oracle_input
        else:
            with pytest.raises(ValueError, match="invalid"):
                after(case.oracle_input)


def test_goal24_metamorphic_forms_preserve_contract_behavior() -> None:
    sample = CATALOG[1]
    source = sample.after
    formatted = "# harmless review comment\n\n" + source.replace("if value < 0:", "if (value < 0):")
    helper_form = (
        "def _invalid(value):\n"
        "    return value < 0\n\n"
        "def contract(value):\n"
        "    if _invalid(value): raise ValueError('invalid')\n"
        "    return int(value)\n"
    )
    for variant in (formatted, helper_form):
        contract = _contract(variant)
        with pytest.raises(ValueError, match="invalid"):
            contract(-1)
        assert contract(2) == 2
