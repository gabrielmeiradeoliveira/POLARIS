# GOAL 24 Security Audit

No external provider or GitHub operation was performed. The audited review prompt marks repository content as untrusted, and provider output is parsed into strict `CandidateFinding` schemas before downstream validation.

RC1 correction: explicitly controlled local providers can opt in to preserve locally generated deterministic candidates after a provider-stage exception and emit `PROVIDER_STAGE_FAILED_STATIC_PRESERVED`. Ordinary provider failures still surface as failures for evaluation and operational diagnostics. The warning contains only an exception class name, not prompt content or credentials. Residual work: a dedicated synthetic secret-minimization corpus and controlled malformed-provider matrix remain required before an offline RC1 approval.

Added local regression coverage confirms malformed JSON and a hostile schema-invalid payload (unknown category, external path, command-like text) create no candidate findings and only structured rejection warnings. No payload content is executed.
