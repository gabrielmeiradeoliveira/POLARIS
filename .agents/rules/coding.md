# POLARIS Coding Standards

## 1. Clean Code & Type Safety
- All code must pass type checking with clear type hints.
- Code, docstrings, identifiers, and comments must be in English.
- Avoid God Objects, monolithic functions, and undocumented magic constants.

## 2. Immutability & Contracts
- Use frozen Pydantic models (`ConfigDict(frozen=True, extra="forbid")`) for domain findings and evidence.
- Maintain deterministic ordering for lists and dictionaries when formatting prompts or reports.
- Do not introduce external dependencies without explicit approval.
