from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT))

from tests.integration.field_trial.test_polyglot_field_trial import _scan_dir


def main() -> int:
    parser = argparse.ArgumentParser(description="Run POLARIS polyglot field trial on a target directory")
    parser.add_argument("--target", type=Path, required=True, help="Target directory to scan")
    args = parser.parse_args()
    res = _scan_dir(args.target.resolve())
    print(json.dumps({k: v for k, v in res.items() if k != "issues"}, indent=2))
    print(f"total_issues: {len(res['issues'])}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
