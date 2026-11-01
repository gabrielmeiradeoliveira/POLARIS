# GOAL 10.1 — Structural Analysis

## Scope

`deicide.context.static_analysis.PythonStaticAnalyzer` is a deterministic,
standard-library-AST-only intraprocedural evidence engine. It extracts classes,
inheritance expressions, functions, async functions, imports, assignments,
calls, returns, raises, exception handlers, decorators (through the existing
AST extractor), and source spans.

The engine never executes source code or resolves dynamic dispatch. Syntax
errors produce `syntax_error`; oversized procedures produce
`complexity_limit`; neither is promoted to a proven relationship.

## Changed-symbol linkage

The existing `identify_changed_symbols` mapping remains the authority for
Git-diff-line-to-symbol linkage. Static relevance consults the parsed procedure
containing that changed symbol and leaves legacy selection untouched if parsing,
scope mapping, or signal linkage is uncertain.

## Limits

Each procedure is capped at 200 CFG nodes by default. Resolution is
intraprocedural only. Imports and direct consumers continue to use the existing
dependency graph, which marks only resolved graph edges as proven.
