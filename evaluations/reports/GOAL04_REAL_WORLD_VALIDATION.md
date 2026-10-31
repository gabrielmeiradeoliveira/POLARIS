# GOAL 04 — Real-World Validation

## Status

PARTIAL. The offline corpus and observability work are complete and one
authorized NVIDIA pilot was executed. The environment blocked every outbound
socket before the NVIDIA endpoint could be contacted, so there are no model
responses or detection-quality metrics.

## Corpus

`evaluations/fixtures/real_world_verified_benchmark.json` contains eight
scored `DOCUMENTED_VERIFIED` defects reconstructed from public, immutable fix
commits. Each fixture records the vulnerable parent revision, fix revision,
independent evidence, a reproduction procedure, and limitations. The review
diff is deliberately the inverse of the fix so it evaluates an introducing
change rather than asking the model to report a fix.

The older `real_world_benchmark.json` remains unchanged and is not suitable
for this pilot: its historical positive entries predominantly model fixes.

| Case | Repository | vulnerable revision | fix revision | evidence |
| --- | --- | --- | --- | --- |
| `rw-requests-2023-proxy-authorization` | psf/requests | `302225334678490ec66b3614a9dddb8a02c5f4fe` | `74ea7cf7a6a27a4eeb2ae24e162bcc942a6706d5` | CVE-2023-32681 and added regression test |
| `rw-requests-jsondecodeerror-pickle` | psf/requests | `96b22fa18c00831656ee4b286bf1c9062459b00a` | `3ff3ff21dd45957c9e143cd500291959bb15f690` | issue #6628 and added pickle test |
| `rw-requests-super-len-unicode` | psf/requests | `f6707042d8b18d2a3737380bf58ff020872fb07b` | `3fd309a5c14e4cfbd96bea6c8e71b4958fe090bb` | focused fix commit |
| `rw-urllib3-cookie-cross-origin` | urllib3/urllib3 | `740380c59ca2a7c2dceca19e5dba99f6b7060e62` | `644124ecd0b6e417c527191f866daa05a5a2056d` | CVE-2023-43804 and redirect tests |
| `rw-urllib3-proxy-redirect-origin` | urllib3/urllib3 | `e349d97f2bf234b95d5dd9e689d056a521dfc3b0` | `01cd60b539f808a65e9c5aa93db1c48292432176` | changelog 5126 and socket tests |
| `rw-urllib3-port-zero` | urllib3/urllib3 | `f4e4bc31f40f8c94c6a1f1685df28f97ff48c305` | `f5cf122346141b187cca0db6e6445297d336b610` | changelog 5071 and tests |
| `rw-urllib3-invalid-timeout-error` | urllib3/urllib3 | `29ae1419530857dc43f5d28907da5d6fbc229739` | `9f1b31d7daab252962d3400f64c3574c0ccb122f` | changelog 5059 and test |
| `rw-werkzeug-debugger-trusted-host` | pallets/werkzeug | `d2d3869525a4ffb2c41dfb2c0e39d94dab2d870c` | `71b69dfb7df3d912e66bab87fbb1f21f83504967` | GHSA-2g68-c3qc-8985 |

All new fixtures use minimized unchanged historical excerpts. This is enough
to validate the diff/source relationship and production-parity materialization,
but it is not an executable checkout of the upstream project. Consequently,
none is labelled `EXECUTABLE_VERIFIED` and no claim of independent runtime
reproduction is made.

## Observability

`deicide evaluate --observability-file PATH` is explicit opt-in telemetry.
It writes the normal JSON summary plus, for each case, provider/model,
SHA-256 prompt and structured-response hashes, attempt number, latency, retry
reason, timeout/error classification, provider-reported usage, and bounded
context-selection diagnostics. Prompts, responses, API keys, and authorization
headers are never persisted. Without that option the `observability` field is
`null` and no file is written.

## Pilot command

The pilot was executed once on 2026-10-27 with a valid key loaded from `.env`.
The first local initialization used an inaccessible quota database and did not
construct a provider or send a request. The single pilot run used a writable
local quota database and this configuration:

```powershell
deicide evaluate --fixtures evaluations/fixtures/real_world_verified_benchmark.json --provider nvidia --end-to-end --production-parity --no-behavioral-delta --context-tokens 2000 --max-requests 16 --max-tokens 100000 --timeout 40 --max-retries 1 --max-elapsed-seconds 720 --allow-external --observability-file evaluations/results/real_world_nvidia_pilot/pilot.json --format json
```

This executed eight distinct cases, permits at most two attempts each, and did
not substitute a provider or model. The canonical artifact is
`evaluations/results/real_world_nvidia_pilot_2026_10_27/pilot.json`. Do not
run the pilot again or overwrite it.

## Pilot result

| Measure | Result |
| --- | ---: |
| Model | `minimaxai/minimax-m3.1-flash` |
| Cases | 8 |
| Successful cases | 0 |
| Infrastructure failures | 8 |
| Attempted requests | 16 (two per case) |
| Strict TP / FP / FN | 0 / 0 / 0 |
| Strict precision / recall | undefined / undefined |
| Diagnostic precision / recall | undefined / undefined |
| Total latency | 8,306 ms |
| Average case latency | 1,038.25 ms |
| Provider-reported completion tokens | 0 |
| Locally estimated prompt reservations | 19,562 |

Every attempt failed with Windows socket error `10013` (access forbidden)
before a connection was established. Attempt-level observability classifies
these as `connection_error`; the legacy case-level error classifier labels the
provider's generic `network/timeout` wrapper as `timeout`. Both designate
infrastructure failure, not a missed defect. The 19,562 prompt tokens are
local reservation estimates for the failed attempts, not provider-reported or
confirmed-billed token usage.

All cases stayed within the shared context budget: the maximum selected context
was 275 estimated tokens against the configured 2,000-token cap. Behavioral
Delta was disabled throughout.

## Validity limits

- Reversing a documented fix is a reconstructed introducing change, not proof
  of the original introducing commit.
- The corpus is security and HTTP-library heavy (Requests, urllib3, Werkzeug);
  it cannot establish broad generalization.
- The NVIDIA pilot must be interpreted as a small, nondeterministic sample;
  provider timeouts and failures remain infrastructure outcomes, not FNs.
- This run is not a sample of NVIDIA model quality because no request reached
  the provider. A future pilot requires an environment that permits outbound
  HTTPS to `integrate.api.nvidia.com`; it must use a new result directory and
  must not overwrite this infrastructure-failure artifact.
