# GOAL 26 Phase 3 NVIDIA preparation

The NVIDIA paired runner is prepared but must not be executed until a separate live-campaign approval.

It uses one sequential `BudgetTracker` for both arms. Before dispatch, the runner rejects a JSON request body over 16,000 bytes and reserves 16,512 input tokens (the frozen wire-payload bound plus 512 provider-tokenizer overhead tokens) and the request's `max_tokens` output cap. The shared tracker rejects a request when the combined reservation would exceed 40 requests or 100,000 tokens.

The runner stores only metrics, status, categories, paths, line ranges, latency, and token accounting. It refuses an existing output directory, so prior campaign records cannot be overwritten. Comparative metrics include only case IDs completed by both arms.

The NVIDIA API key is resolved only by `PolarisConfig` from `NVIDIA_API_KEY` or `POLARIS_API_KEY`; it is not printed or serialized.

The byte bound is mathematically exact for the JSON body sent by this adapter, but it is not a model-tokenizer bound. The 512-token overhead is conservative policy, not a proof. Under the provider's `max_tokens` contract, reservations bound planned output; live execution remains blocked until a model-compatible input-token counter or an NVIDIA-documented request-accounting bound is available.
