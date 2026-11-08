# POLARIS Testing & Regression Rules

## 1. Test Verification Standard
- Never claim tests passed without running them and inspecting exit codes.
- Distinguish verified test results from environment limitations (e.g. host socket policies).
- Maintain characterization tests for legacy contracts and regression prevention.

## 2. Frozen Evaluation Artifacts
- Never modify or execute historical frozen benchmark datasets (e.g. GOAL 27 fixtures, model selection manifests, and frozen SHA-256 artifacts).
