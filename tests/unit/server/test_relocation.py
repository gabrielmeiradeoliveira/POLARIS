from __future__ import annotations

import unittest

from polaris_server.relocation import RelocatableIssue, compute_line_hash, relocate_issue


class TestIssueRelocation(unittest.TestCase):
    def test_relocation_after_line_shift_and_rename(self) -> None:
        h = compute_line_hash("password = '123'")
        prev = [
            RelocatableIssue("iss-1", "old_auth.py", "python:S2068", 10, "login", h, "password = '123'", "FALSE_POSITIVE")
        ]
        moved = RelocatableIssue("cand-1", "new_auth.py", "python:S2068", 40, "login", h, "password = '123'")
        matched = relocate_issue(moved, prev, renames={"old_auth.py": "new_auth.py"})
        self.assertIsNotNone(matched)
        self.assertEqual(matched.state, "FALSE_POSITIVE")


if __name__ == "__main__":
    unittest.main()
