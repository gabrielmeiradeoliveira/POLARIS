# GOAL 07.1 — Historical Corpus Structural Unblock

## Scope

This correction addresses only the structural mismatch in
`rw-urllib3-proxy-redirect-origin`. It does not alter the production validator,
prompts, expected finding, category, severity, historical results, or provider
configuration.

## Evidence

The public urllib3 fix commit `01cd60b539f808a65e9c5aa93db1c48292432176`
changes redirect-header handling inside `PoolManager.urlopen()`. The original
method body uses eight spaces of indentation. The fixture deliberately
materializes a reduced top-level `redirect_request()` function, whose body uses
four spaces. Before this correction, the fixture mixed these representations:
the materialized source was normalized, but the hunk retained the original
method indentation and an incorrect `13/8` count.

## Correction

The fixture hunk is now normalized to the materialized function body:

- its header is `@@ -2,9 +2,5 @@`, matching the compact body counts;
- every hunk line is shifted left by one indentation level together, preserving
  the relative nesting of the redirect conditional, loop, nested conditional,
  and header removal;
- the AFTER source, expected finding, evidence, and result artifacts are
  unchanged.

The independent integrity validator reconstructs BEFORE by reversing the hunk,
then reapplies it and requires byte-for-byte equality with the materialized
AFTER source.

## Remaining limitation

This fixture remains a minimized historical excerpt rather than a complete,
executable urllib3 checkout. Structural validity proves that its compact diff
and materialized source correspond; it does not independently reproduce the
complete upstream runtime environment.
