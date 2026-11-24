from __future__ import annotations

import gzip
import io
import json
from typing import Any, Iterator


def iter_chunks(items: list[Any], chunk_size: int = 500) -> Iterator[list[Any]]:
    """Yield slices of items with at most chunk_size elements to bound memory usage."""
    size = max(1, chunk_size)
    for idx in range(0, len(items), size):
        yield items[idx : idx + size]


def decode_gzip_json_stream(raw_bytes: bytes) -> dict[str, Any]:
    """Decompress a gzip-compressed JSON payload via streaming reader."""
    with gzip.GzipFile(fileobj=io.BytesIO(raw_bytes), mode="rb") as gz:
        data = json.load(gz)
    if not isinstance(data, dict):
        raise ValueError("Analysis payload must be a JSON object")
    return data
