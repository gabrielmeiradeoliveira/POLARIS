"""Pinned local MiniMax tokenizer for GOAL 26 planning and reservation."""

from __future__ import annotations

import hashlib
import json
from functools import lru_cache
from pathlib import Path

TOKENIZER_MANIFEST = Path("evaluations/manifests/goal26-minimax-tokenizer.json")


def load_manifest() -> dict[str, object]:
    return json.loads(TOKENIZER_MANIFEST.read_text(encoding="utf-8"))


@lru_cache
def load_tokenizer():
    from transformers import AutoTokenizer

    manifest = load_manifest()
    root = Path(str(manifest["path"]))
    for name, expected in dict(manifest["files"]).items():
        actual = hashlib.sha256((root / name).read_bytes()).hexdigest()
        if actual != expected:
            raise ValueError(f"Pinned MiniMax tokenizer hash mismatch: {name}")
    tokenizer = AutoTokenizer.from_pretrained(root, local_files_only=True, trust_remote_code=False)
    tokenizer.chat_template = (root / "chat_template.jinja").read_text(encoding="utf-8")
    return tokenizer


def count_messages(system_prompt: str, user_prompt: str) -> int:
    tokenizer = load_tokenizer()
    token_ids = tokenizer.apply_chat_template(
        [{"role": "system", "content": system_prompt}, {"role": "user", "content": user_prompt}],
        tokenize=True,
        add_generation_prompt=True,
    )
    return len(token_ids)
