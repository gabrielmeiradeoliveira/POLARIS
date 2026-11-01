# GOAL 17 NVIDIA Provider Security Review

## Transmitted material

The NVIDIA adapter sends only the selected model, system prompt, user prompt,
temperature, and output cap to HTTPS `.../v1/chat/completions`. Credentials are
sent in the Authorization header, never in the URL. Environment variables are
not serialized into requests or history.

## Protections verified offline

- `SecretStr` retains the API key; provider and evaluation error paths redact keys
  and Bearer values.
- History sanitizes likely credential assignments and bounds persisted text.
  Observability stores hashes, not prompts or responses.
- Source-originated instruction injection is constrained by role-separated prompts
  and deterministic location/evidence validation.
- HTTP 4xx/5xx, malformed envelopes, rate limits, timeouts, retries, and network
  errors are categorized without retaining response bodies.

## Token-limit evidence and limitation

NVIDIA's hosted chat-completions reference documents `max_tokens` as a maximum
generated-output setting, not an input-plus-output account ceiling. Self-hosted
NIM documentation lists token-counting endpoints, but does not establish hosted
endpoint availability or billing semantics. See [hosted chat completions](https://docs.api.nvidia.com/nim/reference/meta-llama2-70b-infer)
and [NIM API reference](https://docs.nvidia.com/nim/large-language-models/latest/reference/api-reference.html).

DEICIDE uses a local estimate, a 256-token margin, and dynamic output reservation.
This reduces avoidable overspend but cannot prove an absolute 6,000-token cap.
