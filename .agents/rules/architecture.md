# POLARIS Architectural Rules

## 1. Clean Architecture Boundaries
- **Domain:** Pure business models and entities (`Finding`, `LineRange`, `Severity`, `Confidence`). Zero dependencies on infrastructure, web frameworks, or CLI parsers.
- **Application:** Use cases and orchestration (`run_review`, `run_deep_review`, `AnalysisOrchestrator`). Coordinates domain models and ports.
- **Ports:** Abstract contracts (`AnalysisModule`, `BaseScanner`, `LLMProvider`).
- **Adapters:** Concrete implementations (AST analyzers, Git analyzers, scanners, providers, formatters, SARIF).

## 2. Modularity & Single Responsibility
- High cohesion and low coupling across modules.
- Prefer deterministic analysis over probabilistic LLM generation when sufficient.
- Avoid duplicate numbered engines (e.g., `*3.py`); maintain canonical implementations with backwards-compatibility shims where needed.
