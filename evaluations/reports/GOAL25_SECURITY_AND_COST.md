# GOAL 25 Security and Cost

## Data handling

The runner's serialized result schema records case identifiers, aggregate and per-case metrics, timing, retry counts, and token counts only. It rejects fields named `prompt`, `response`, `api_key`, `authorization`, `diff_text`, and `file_contents`. Credentials were resolved from trusted configuration and were neither displayed nor written to results.

## Budget controls

- Input and output budgets are separately reserved before transport.
- Per-request caps are 8,000 input and 2,000 output tokens.
- Cumulative caps are 50,000 input and 20,000 output tokens; the total-token ceiling is 70,000.
- The health request used 186 reported input tokens and 128 reported output tokens.
- The frozen A/B runner now has a stricter 12-additional-request ceiling and runs sequentially.
- A response without usage is conservatively charged and can block a subsequent attempt; tests cover this path.

## Cost evidence and limitation

NVIDIA reported 314 total tokens for the health request. No model price was assumed, so this report does not fabricate a currency cost. The hybrid A/B process returned no reliable result payload; its token consumption, cost, failure count, and latency are unknown. The safe action was to stop rather than submit more requests.
