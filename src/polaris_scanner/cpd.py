from __future__ import annotations

import re
from dataclasses import dataclass

_TOKEN_RE = re.compile(r"[A-Za-z_][A-Za-z0-9_]*|\d+(?:\.\d+)?|\"[^\"]*\"|'[^']*'|\S")
_NUM_RE = re.compile(r"^\d+(?:\.\d+)?$")
_STR_RE = re.compile(r"^(\"[^\"]*\"|'[^']*')$")
_IDENT_RE = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*$")


@dataclass(frozen=True)
class CpdResult:
    duplicated_lines: int
    duplicated_blocks: int
    duplicated_lines_density: float


def normalize_tokens(source: str) -> list[tuple[str, int]]:
    """Tokenize source into (normalized_token, 1_based_line) pairs."""
    tokens: list[tuple[str, int]] = []
    for line_no, line in enumerate(source.splitlines(), start=1):
        stripped = line.strip()
        if not stripped or stripped.startswith(("#", "//", "--", "/*", "*")):
            continue
        for tok in _TOKEN_RE.findall(stripped):
            if _STR_RE.match(tok) or _NUM_RE.match(tok):
                norm = "$LIT"
            elif _IDENT_RE.match(tok):
                norm = "$ID"
            else:
                norm = tok
            tokens.append((norm, line_no))
    return tokens


def detect_duplicates(
    files_content: dict[str, str],
    *,
    min_lines: int = 10,
    min_tokens: int = 100,
) -> CpdResult:
    """Detect duplicated token blocks across files using Rabin-Karp rolling hash."""
    base = 257
    mod = (1 << 61) - 1
    seen: dict[int, tuple[str, int, int]] = {}
    dup_lines_by_file: dict[str, set[int]] = {}
    blocks = 0
    total_lines = sum(len(c.splitlines()) for c in files_content.values())

    for path in sorted(files_content):
        toks = normalize_tokens(files_content[path])
        if len(toks) < min_tokens:
            continue
        power = pow(base, min_tokens - 1, mod)
        h = 0
        for i in range(min_tokens):
            h = (h * base + hash(toks[i][0]) % 1000003) % mod
        for start in range(len(toks) - min_tokens + 1):
            if start > 0:
                out_v = hash(toks[start - 1][0]) % 1000003
                in_v = hash(toks[start + min_tokens - 1][0]) % 1000003
                h = ((h - out_v * power) * base + in_v) % mod
            l_start = toks[start][1]
            l_end = toks[start + min_tokens - 1][1]
            if (l_end - l_start + 1) < min_lines:
                continue
            prev = seen.get(h)
            if prev is None:
                seen[h] = (path, l_start, l_end)
            else:
                p_path, p_start, p_end = prev
                if p_path != path or abs(p_start - l_start) >= min_lines:
                    blocks += 1
                    dup_lines_by_file.setdefault(path, set()).update(range(l_start, l_end + 1))
                    dup_lines_by_file.setdefault(p_path, set()).update(range(p_start, p_end + 1))

    dup_lines = sum(len(v) for v in dup_lines_by_file.values())
    density = round((dup_lines / total_lines) * 100.0, 2) if total_lines > 0 else 0.0
    return CpdResult(duplicated_lines=dup_lines, duplicated_blocks=blocks, duplicated_lines_density=density)
