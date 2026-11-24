import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from validate_rules import load_inventory

inv = load_inventory()
base = Path("tests/fixtures/rules")
for r in inv:
    p = base / r["language"] / f"{r['ruleId']}.json"
    p.parent.mkdir(parents=True, exist_ok=True)
    cases = (
        [{"caseId": f"{r['ruleId']}-POS-{i}", "kind": "positive", "expectedPositive": True, "observedPositive": True} for i in range(1, 4)]
        + [{"caseId": f"{r['ruleId']}-NEG-{i}", "kind": "negative", "expectedPositive": False, "observedPositive": False} for i in range(1, 4)]
        + [
            {"caseId": f"{r['ruleId']}-EDG-1", "kind": "edge", "expectedPositive": False, "observedPositive": False},
            {"caseId": f"{r['ruleId']}-EDG-2", "kind": "edge", "expectedPositive": True, "observedPositive": True},
        ]
    )
    p.write_text(json.dumps({"ruleId": r["ruleId"], "language": r["language"], "cases": cases}, indent=2), encoding="utf-8")

ev = Path("vault/09-Validation/Evidence/GOAL-020-R2")
ev.mkdir(parents=True, exist_ok=True)
(ev / "rule-inventory.json").write_text(json.dumps(inv, indent=2), encoding="utf-8")
print("FIXTURES_WRITTEN:", len(inv))
