# GOAL 13 — Cross-File Intelligence

## State

The repository already contains the conservative cross-file vertical slice in `context/project_index.py`, `import_resolver.py`, `dependency_graph.py`, and `pipeline.py`. It indexes bounded Python files, resolves local and relative imports, tracks direct calls/references, reports resolution status and confidence, detects cycles, and supplies ranked supplementary snippets.

## Safety and compatibility

Repository file access uses safe-root checks; symlinks, traversal, malformed imports, unreadable/oversized sources, syntax failures, cycles, and dynamic calls fall back conservatively. The index has explicit file/byte limits. Cross-file selection remains opt-in through `--static-relevance-selection`; defaults are unchanged.

## Verification and limitations

`tests/test_context_dependency_graph.py`, context-pipeline tests, and full offline pytest cover local imports, relative imports, aliases, calls, cycles, malformed code, path safety, and limits. Python dynamic dispatch, wildcard imports, reflection, and runtime imports are deliberately not asserted as resolved dependencies.

No additional graph feature was enabled in this mission because the existing implementation already matches the requested conservative scope and the offline A/B/C path cannot demonstrate an LLM-quality gain.
