import json
import re
import sys
from pathlib import Path

VALID_GOAL_STATUSES = {"PROPOSED", "APPROVED", "IN_PROGRESS", "BLOCKED", "FAILED", "COMPLETED"}
VALID_CRITERIA_STATUSES = {"PASS", "FAIL", "BLOCKED", "NOT_EXECUTED"}
REQUIRED_CRITERION_KEYS = {
    "id", "description", "sourceRequirement", "mandatory", "status",
    "validationCommand", "relatedFiles", "evidence", "expectedResult",
    "observedResult", "limitations",
}


def validate_acceptance_data(data: dict, repo_root: Path) -> list[str]:
    errors: list[str] = []
    if not isinstance(data, dict):
        return ["Documento deve ser um objeto JSON."]
    if data.get("schemaVersion") != "1.0.0":
        errors.append("schemaVersion inválida ou ausente (esperado '1.0.0').")
    goal_id = data.get("goalId", "")
    if not isinstance(goal_id, str) or not re.match(r"^GOAL-[0-9]{3}(-[A-Z0-9]+)?$", goal_id):
        errors.append(f"goalId inválido: {goal_id!r}")
    goal_status = data.get("goalStatus")
    if goal_status not in VALID_GOAL_STATUSES:
        errors.append(f"goalStatus inválido: {goal_status!r}")

    criteria = data.get("criteria")
    if not isinstance(criteria, list) or len(criteria) == 0:
        errors.append("criteria deve ser uma lista não vazia.")
        return errors

    seen_ids: set[str] = set()
    for idx, item in enumerate(criteria):
        if not isinstance(item, dict):
            errors.append(f"Critério [{idx}] deve ser um objeto.")
            continue
        missing = REQUIRED_CRITERION_KEYS - set(item.keys())
        if missing:
            errors.append(f"Critério [{idx}] sem campos obrigatórios: {sorted(missing)}")
            continue
        cid = item["id"]
        if cid in seen_ids:
            errors.append(f"ID de critério duplicado: {cid}")
        seen_ids.add(cid)

        if not isinstance(item["mandatory"], bool):
            errors.append(f"Critério {cid}: mandatory deve ser booleano.")
        if item["status"] not in VALID_CRITERIA_STATUSES:
            errors.append(f"Critério {cid}: status inválido {item['status']!r}.")

        for ev in item["evidence"]:
            if not (repo_root / ev).exists():
                errors.append(f"Critério {cid}: evidência inexistente '{ev}'.")

        if goal_status == "COMPLETED" and item["mandatory"] and item["status"] != "PASS":
            errors.append(f"GOAL {goal_id} está COMPLETED mas critério obrigatório {cid} está '{item['status']}'.")
        if item["mandatory"] and item["status"] == "PASS" and len(item["evidence"]) == 0:
            errors.append(f"Critério obrigatório {cid} está PASS sem evidência registrada.")

    return errors


def validate_all(acceptance_dir: Path, repo_root: Path) -> int:
    files = sorted(p for p in acceptance_dir.glob("*.json") if p.name != "acceptance.schema.json")
    all_errors: list[str] = []
    for f in files:
        try:
            data = json.loads(f.read_text(encoding="utf-8"))
        except Exception as exc:
            all_errors.append(f"{f.name}: JSON inválido ({exc})")
            continue
        errs = validate_acceptance_data(data, repo_root)
        for e in errs:
            all_errors.append(f"{f.name}: {e}")

    print(f"VALIDATED_ACCEPTANCE_FILES={len(files)}")
    print(f"ACCEPTANCE_ERRORS={len(all_errors)}")
    for e in all_errors:
        print(f"ERROR: {e}")
    return 1 if all_errors else 0


if __name__ == "__main__":
    root = Path(__file__).resolve().parents[2]
    acc_dir = root / "vault" / "09-Validation" / "Acceptance"
    raise SystemExit(validate_all(acc_dir, root))
