import sys
import tempfile
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(REPO_ROOT / "scripts" / "validation"))

from validate_goals import validate_acceptance_data


def _valid_criterion(cid: str = "B-001", status: str = "PASS", ev: list[str] | None = None) -> dict:
    return {
        "id": cid,
        "description": "Critério de teste",
        "sourceRequirement": "GOAL-004-B",
        "mandatory": True,
        "status": status,
        "validationCommand": "echo ok",
        "relatedFiles": ["AGENTS.md"],
        "evidence": ev if ev is not None else ["AGENTS.md"],
        "expectedResult": "ok",
        "observedResult": "ok",
        "limitations": "nenhuma",
    }


class TestValidateGoals(unittest.TestCase):
    def test_accepts_valid_matrix(self):
        data = {
            "schemaVersion": "1.0.0",
            "goalId": "GOAL-004-B",
            "goalStatus": "COMPLETED",
            "criteria": [_valid_criterion()],
        }
        self.assertEqual(validate_acceptance_data(data, REPO_ROOT), [])

    def test_rejects_completed_with_pending_mandatory(self):
        data = {
            "schemaVersion": "1.0.0",
            "goalId": "GOAL-004-B",
            "goalStatus": "COMPLETED",
            "criteria": [_valid_criterion(status="NOT_EXECUTED", ev=[])],
        }
        errs = validate_acceptance_data(data, REPO_ROOT)
        self.assertTrue(any("COMPLETED" in e for e in errs))

    def test_rejects_missing_evidence_file(self):
        data = {
            "schemaVersion": "1.0.0",
            "goalId": "GOAL-004-B",
            "goalStatus": "IN_PROGRESS",
            "criteria": [_valid_criterion(ev=["nao_existe_123.md"])],
        }
        errs = validate_acceptance_data(data, REPO_ROOT)
        self.assertTrue(any("evidência inexistente" in e for e in errs))

    def test_rejects_duplicate_id(self):
        data = {
            "schemaVersion": "1.0.0",
            "goalId": "GOAL-004-B",
            "goalStatus": "IN_PROGRESS",
            "criteria": [_valid_criterion("B-001"), _valid_criterion("B-001")],
        }
        errs = validate_acceptance_data(data, REPO_ROOT)
        self.assertTrue(any("duplicado" in e for e in errs))

    def test_rejects_invalid_status(self):
        data = {
            "schemaVersion": "1.0.0",
            "goalId": "GOAL-004-B",
            "goalStatus": "IN_PROGRESS",
            "criteria": [_valid_criterion(status="UNKNOWN")],
        }
        errs = validate_acceptance_data(data, REPO_ROOT)
        self.assertTrue(any("status inválido" in e for e in errs))

    def test_rejects_missing_required_criterion_fields(self):
        data = {
            "schemaVersion": "1.0.0",
            "goalId": "GOAL-004-B",
            "goalStatus": "IN_PROGRESS",
            "criteria": [{"id": "B-001"}],
        }
        errs = validate_acceptance_data(data, REPO_ROOT)
        self.assertTrue(any("sem campos obrigatórios" in e for e in errs))

    def test_rejects_invalid_schema_version(self):
        data = {
            "schemaVersion": "0.0.1",
            "goalId": "INVALID",
            "goalStatus": "IN_PROGRESS",
            "criteria": [],
        }
        errs = validate_acceptance_data(data, REPO_ROOT)
        self.assertGreaterEqual(len(errs), 3)


if __name__ == "__main__":
    unittest.main(verbosity=2)
