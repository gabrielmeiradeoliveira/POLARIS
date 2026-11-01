# GOAL 07.2 — Reproducible Benchmark Release Preparation

## Scope

This preparation creates a draft benchmark manifest and an exact dependency
version lock for the validated local environment. It does not create a commit
or tag, execute a provider benchmark, modify production detection behavior,
or recalculate historical metrics.

## Current release candidate

- Corpus: `evaluations/fixtures/real_world_verified_benchmark.json`
- Corpus SHA-256:
  `17019e5f994b1bfc4ba4afe62992cf69bd829f509db3e075cf68ba9615759096`
- Structural gate: eight independent BEFORE/AFTER fixture round-trips required.
- Offline verification: `281 passed` with an external pytest base temporary
  directory.

The evaluated payload was frozen in commit
`52618449b4db2c07860f711330d3cf510daf463d`. The manifest records that commit
as `evaluated_payload_commit` rather than attempting to store the hash of the
commit that contains the manifest itself. The release tag identifies the latter
without a circular Git hash dependency.

## Consolidation plan

1. Review and commit the cohesive evaluator implementation and its tests.
2. Commit the historical corpus, independent integrity validator, fixture tests,
   audit reports, procedure, manifest, and dependency lock in a bounded release
   documentation commit or an explicitly approved equivalent.
3. Exclude `scratch/`, temporary fixture shards, SQLite usage databases, and
   any artifact containing credentials or raw transport diagnostics.
4. On a clean checkout, install `requirements-lock.txt`, install the checked-out
   project, recompute every manifest hash, run the structural fixture test and
   the full offline suite, and compare the resulting Git commit to the manifest.
5. Only after those checks should an approved annotated tag be created:
   `deicide-historical-introducing-v1.0.0`.

## Reproduction limitation

The lock records exact package versions but not package artifact hashes. A
future hardened release may replace it with a hash-checked lock generated in
an approved dependency-resolution workflow. The historical fixtures remain
minimized excerpts rather than complete executable upstream checkouts.
