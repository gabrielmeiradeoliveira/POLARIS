# GOAL 26 MiniMax tokenization audit

The local tokenizer is the official `MiniMaxAI/MiniMax-M3.1-Flash` artifact at commit `4644d202ac129a244c6e039e273090c11257f22f`. Its five files are pinned by SHA-256 in `goal26-minimax-tokenizer.json` and loaded without network access or remote code.

The official chat template counted the forty rendered POLARIS prompts as follows:

| Arm | Prompts | Minimum | Maximum | Total |
| --- | ---: | ---: | ---: | ---: |
| OFF | 20 | 1,127 | 1,368 | 23,945 |
| ON | 20 | 1,127 | 1,528 | 25,456 |
| Combined | 40 | 1,127 | 1,528 | 49,401 |

With these local counts and no serving overhead, a uniform output ceiling would be `floor((100000 - 49401) / 40) = 1,264`. This is planning evidence only: the NVIDIA serving template and overhead have not been proven equivalent, so the live campaign remains blocked.

The runner keeps the 16,000-byte request-body guard and now passes the local post-template count to the shared budget tracker before NVIDIA dispatch. A pair should be reserved before execution in a future approved change; the current sequential runner still requires this scheduling change before a live campaign.
