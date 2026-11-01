# GOAL 10.2 — Control and Data Flow

## Control flow

The engine creates a bounded CFG per function with entry, statement,
condition, loop, exception, finally, and exit nodes. It represents sequential
flow, `if` branches, loop back-edges, early `return`, `raise`, and
`try`/`except`/`finally`. It does not claim interprocedural reachability.
Statements following a terminal local path are emitted as potentially
unreachable source lines; this is evidence for context selection, not a finding.

## Data flow

Definitions from parameters, assignments, annotated assignments, augmented
assignments, loop targets, and exception bindings are tracked locally. Uses in
assignments, conditions, returns, raises, loops, and expressions are linked to
a known local definition as `proven`, or represented as `possible` when no
local definition is available. Dynamic behavior is not inferred.

When a name has a later lexical local assignment but no reaching definition at
the use, the fact is explicitly labeled `possible_use_before_assignment`.
This is context evidence only, not an automatic finding.

## Validation

`tests/test_static_analysis.py` covers structural facts, CFG branches/loops,
exceptions/finally, def-use evidence, complexity limits, and invalid syntax.
