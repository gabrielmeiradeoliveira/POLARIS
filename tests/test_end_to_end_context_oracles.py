"""Executable, fixture-backed before/after contracts for selected E2E cases."""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path
from types import SimpleNamespace

import pytest

from deicide.evaluation.runner import load_fixtures_from_file


FIXTURES = Path("evaluations/fixtures/end_to_end_context_benchmark.json")


def _fixture(case_id: str):
    return next(item for item in load_fixtures_from_file(FIXTURES) if item.case_id == case_id)


def _reverse_single_file_hunk(after_source: str, diff_text: str) -> str:
    """Recover BEFORE for a complete single-file hunk without inventing source."""
    old_lines: list[str] = []
    new_lines: list[str] = []
    in_hunk = False
    for line in diff_text.splitlines():
        if line.startswith("@@"):
            in_hunk = True
            continue
        if not in_hunk or line.startswith(("diff ", "---", "+++")):
            continue
        if line.startswith("-"):
            old_lines.append(line[1:])
        elif line.startswith("+"):
            new_lines.append(line[1:])
        else:
            old_lines.append(line[1:] if line.startswith(" ") else line)
            new_lines.append(line[1:] if line.startswith(" ") else line)
    old_block = "\n".join(old_lines) + "\n"
    new_block = "\n".join(new_lines) + "\n"
    assert old_block and new_block, "fixture diff must contain both BEFORE and AFTER source"
    assert after_source.count(new_block) == 1, "AFTER hunk must match exactly one source location"
    return after_source.replace(new_block, old_block, 1)


def _materialize(tmp_path: Path, fixture, version: str) -> Path:
    assert fixture.diff_text.count("diff --git ") == 1, "oracle executor supports one modified file"
    assert fixture.diff_text.count("\n@@ ") == 1, "oracle executor supports one complete hunk"
    assert version in {"before", "after"}
    root = tmp_path / version
    sources = dict(fixture.file_contents)
    diff_header = next(line for line in fixture.diff_text.splitlines() if line.startswith("diff --git "))
    changed_path = diff_header.removeprefix("diff --git ").split(" b/", maxsplit=1)[1]
    if fixture.expected_findings:
        assert fixture.expected_findings[0].file_path == changed_path, "expected finding must identify the modified file"
    assert changed_path in sources, "modified source must be present in file_contents"
    if version == "before":
        sources[changed_path] = _reverse_single_file_hunk(sources[changed_path], fixture.diff_text)
    for relative_path, source in sources.items():
        destination = root / relative_path
        destination.parent.mkdir(parents=True, exist_ok=True)
        destination.write_text(source, encoding="utf-8")
    return root


def _run_isolated(root: Path, program: str) -> subprocess.CompletedProcess[str]:
    """Use a fresh interpreter so imported fixture modules and globals cannot leak."""
    bootstrap = f"import sys; sys.path.insert(0, {str(root)!r});\n{program}"
    return subprocess.run(
        [sys.executable, "-I", "-c", bootstrap],
        text=True,
        capture_output=True,
        check=False,
        cwd=root,
    )


def test_reconstruction_rejects_ambiguous_or_unsupported_diffs(tmp_path: Path) -> None:
    with pytest.raises(AssertionError, match="exactly one"):
        _reverse_single_file_hunk("new\nnew\n", "@@ -1 +1 @@\n-old\n+new\n")

    fixture = SimpleNamespace(
        diff_text=(
            "diff --git a/a.py b/a.py\n@@ -1 +1 @@\n-old\n+new\n"
            "diff --git a/b.py b/b.py\n@@ -1 +1 @@\n-old\n+new\n"
        ),
        file_contents={"a.py": "new\n", "b.py": "new\n"},
        expected_findings=[SimpleNamespace(file_path="a.py")],
    )
    with pytest.raises(AssertionError, match="one modified file"):
        _materialize(tmp_path, fixture, "before")

    fixture = SimpleNamespace(
        diff_text="diff --git a/a.py b/a.py\n@@ -1 +1 @@\n-old\n+new\n@@ -3 +3 @@\n-old\n+new\n",
        file_contents={"a.py": "new\nnew\n"},
        expected_findings=[SimpleNamespace(file_path="a.py")],
    )
    with pytest.raises(AssertionError, match="one complete hunk"):
        _materialize(tmp_path, fixture, "before")


def test_fixture_01_executes_actual_before_and_after_modules(tmp_path: Path) -> None:
    fixture = _fixture("e2e-ctx-01-return-contract-multiple-callers")
    before_root = _materialize(tmp_path, fixture, "before")
    after_root = _materialize(tmp_path, fixture, "after")
    assert (after_root / "auth/token.py").read_text(encoding="utf-8") == fixture.file_contents["auth/token.py"]

    contract = """
from api.login import login
from jobs.audit import audit
assert login('alice') == 'alice'
assert audit('bob') == 'bob'
"""
    assert _run_isolated(before_root, contract).returncode == 0

    after = _run_isolated(after_root, contract)
    assert after.returncode != 0
    assert "TypeError" in after.stderr


def test_fixture_03_executes_actual_before_and_after_resource_lifecycle(tmp_path: Path) -> None:
    fixture = _fixture("e2e-ctx-03-retry-leaks-resource")
    before_root = _materialize(tmp_path, fixture, "before")
    after_root = _materialize(tmp_path, fixture, "after")
    assert "finally:" in (before_root / "db/retry.py").read_text(encoding="utf-8")
    assert (after_root / "db/retry.py").read_text(encoding="utf-8") == fixture.file_contents["db/retry.py"]

    contract = """
from db.retry import run
class Resource:
    def __init__(self): self.closed = False
    def open(self): pass
    def close(self): self.closed = True
resource = Resource()
assert run(resource, 'query', lambda _: 'ok') == 'ok'
assert resource.closed
"""
    assert _run_isolated(before_root, contract).returncode == 0

    after = _run_isolated(after_root, contract)
    assert after.returncode != 0
    assert "AssertionError" in after.stderr


def test_fixture_02_executes_actual_before_and_after_request_modules(tmp_path: Path) -> None:
    fixture = _fixture("e2e-ctx-02-shared-session-state")
    before_root = _materialize(tmp_path, fixture, "before")
    after_root = _materialize(tmp_path, fixture, "after")
    contract = """
from web.request import request
from web.admin import read
request('tenant', 'alpha')
assert read('tenant') is None
"""
    assert _run_isolated(before_root, contract).returncode == 0
    after = _run_isolated(after_root, contract)
    assert after.returncode != 0
    assert "AssertionError" in after.stderr


def test_fixture_04_executes_actual_callback_propagation_contract(tmp_path: Path) -> None:
    fixture = _fixture("e2e-ctx-04-callback-exception-swallowed")
    before_root = _materialize(tmp_path, fixture, "before")
    after_root = _materialize(tmp_path, fixture, "after")
    contract = """
from api.submit import submit
try:
    submit('order-1')
except ValueError as exc:
    assert str(exc) == 'declined'
else:
    raise AssertionError('decline must reach caller')
"""
    assert _run_isolated(before_root, contract).returncode == 0
    after = _run_isolated(after_root, contract)
    assert after.returncode != 0
    assert "AssertionError" in after.stderr


def test_fixture_05_executes_actual_plugin_inheritance_contract(tmp_path: Path) -> None:
    fixture = _fixture("e2e-ctx-05-null-plugin-result")
    before_root = _materialize(tmp_path, fixture, "before")
    after_root = _materialize(tmp_path, fixture, "after")
    contract = """
from api.view import view
assert view('alice') == 'alice'
"""
    assert _run_isolated(before_root, contract).returncode == 0
    after = _run_isolated(after_root, contract)
    assert after.returncode != 0
    assert "TypeError" in after.stderr


def test_fixture_06_executes_actual_pagination_callback_contract(tmp_path: Path) -> None:
    fixture = _fixture("e2e-ctx-06-page-boundary-callback")
    before_root = _materialize(tmp_path, fixture, "before")
    after_root = _materialize(tmp_path, fixture, "after")
    contract = """
from jobs.export import run
assert run([1, 2, 3, 4]) is None
"""
    assert _run_isolated(before_root, contract).returncode == 0
    after = _run_isolated(after_root, contract)
    assert after.returncode != 0
    assert "ValueError: empty" in after.stderr


def test_fixture_07_executes_actual_concurrent_worker_contract(tmp_path: Path) -> None:
    fixture = _fixture("e2e-ctx-07-async-shared-callback")
    before_root = _materialize(tmp_path, fixture, "before")
    after_root = _materialize(tmp_path, fixture, "after")
    contract = """
from threading import Barrier, Thread
from asyncq.report import pending_count
from asyncq.schedule import schedule

barrier = Barrier(2)
results = [None, None]
threads = [
    Thread(target=lambda index=index: results.__setitem__(index, schedule(barrier)))
    for index in range(2)
]
for thread in threads: thread.start()
for thread in threads: thread.join()
assert all(not thread.is_alive() for thread in threads)
assert pending_count(results[0]) == 1
assert pending_count(results[1]) == 1
assert results[0] is not results[1]
"""
    assert _run_isolated(before_root, contract).returncode == 0
    after = _run_isolated(after_root, contract)
    assert after.returncode != 0
    assert "AssertionError" in after.stderr


def test_fixture_08_executes_actual_inheritance_validation_contract(tmp_path: Path) -> None:
    fixture = _fixture("e2e-ctx-08-override-skips-validation")
    before_root = _materialize(tmp_path, fixture, "before")
    after_root = _materialize(tmp_path, fixture, "after")
    contract = """
from api.admin import access
class User:
    active = False
assert access(User()) is False
"""
    assert _run_isolated(before_root, contract).returncode == 0
    after = _run_isolated(after_root, contract)
    assert after.returncode != 0
    assert "AssertionError" in after.stderr


def test_fixture_09_executes_actual_adapter_mapper_publisher_contract(tmp_path: Path) -> None:
    fixture = _fixture("e2e-ctx-09-indirect-serializer-contract")
    before_root = _materialize(tmp_path, fixture, "before")
    after_root = _materialize(tmp_path, fixture, "after")
    contract = """
from messaging.publish import publish
assert publish('user-1') == 'user-1'
"""
    assert _run_isolated(before_root, contract).returncode == 0
    after = _run_isolated(after_root, contract)
    assert after.returncode != 0
    assert "TypeError" in after.stderr


def test_fixture_10_executes_actual_callback_identity_contract(tmp_path: Path) -> None:
    fixture = _fixture("e2e-ctx-10-unregisters-wrong-callback")
    before_root = _materialize(tmp_path, fixture, "before")
    after_root = _materialize(tmp_path, fixture, "after")
    contract = """
from ui.app import shutdown
from ui.bus import Bus
from ui.controller import Controller
bus = Bus()
controller = Controller(bus)
shutdown(controller)
bus.emit('after-close')
assert controller.events == []
"""
    assert _run_isolated(before_root, contract).returncode == 0
    after = _run_isolated(after_root, contract)
    assert after.returncode != 0
    assert "AssertionError" in after.stderr


def test_fixture_11_executes_actual_authorization_contract(tmp_path: Path) -> None:
    fixture = _fixture("e2e-ctx-11-permission-default-multiple-callers")
    before_root = _materialize(tmp_path, fixture, "before")
    after_root = _materialize(tmp_path, fixture, "after")
    contract = """
from api.delete import delete
from api.export import export
assert delete() is False
assert export() is False
"""
    assert _run_isolated(before_root, contract).returncode == 0
    after = _run_isolated(after_root, contract)
    assert after.returncode != 0
    assert "AssertionError" in after.stderr


def test_fixture_12_executes_actual_generator_cleanup_contract(tmp_path: Path) -> None:
    fixture = _fixture("e2e-ctx-12-generator-cleanup-after-yield")
    before_root = _materialize(tmp_path, fixture, "before")
    after_root = _materialize(tmp_path, fixture, "after")
    contract = """
from api.file import fetch
class Source:
    def __init__(self): self.closed = False
    def read(self): return b'data'
    def close(self): self.closed = True
source = Source()
value, stream = fetch(source)
assert value == b'data'
stream.close()
assert source.closed
"""
    assert _run_isolated(before_root, contract).returncode == 0
    after = _run_isolated(after_root, contract)
    assert after.returncode != 0
    assert "AssertionError" in after.stderr


def test_fixture_13_executes_actual_signature_migration_contract(tmp_path: Path) -> None:
    fixture = _fixture("e2e-ctx-13-safe-signature-migration-three-callers")
    before_root = _materialize(tmp_path, fixture, "before")
    after_root = _materialize(tmp_path, fixture, "after")
    contract = """
from api.a import a
from api.b import b
from jobs.audit import audit
assert a('alpha') == 'v1:alpha'
assert b('bravo') == 'v1:bravo'
assert audit('charlie') == 'v1:charlie'
"""
    assert _run_isolated(before_root, contract).returncode == 0
    assert _run_isolated(after_root, contract).returncode == 0


def test_fixture_14_executes_actual_copy_on_write_contract(tmp_path: Path) -> None:
    fixture = _fixture("e2e-ctx-14-copy-on-write-session")
    before_root = _materialize(tmp_path, fixture, "before")
    after_root = _materialize(tmp_path, fixture, "after")
    contract = """
from web.read import read
from web.request import request
base = {'tenant': 'alpha'}
updated = request(base)
assert updated['x'] == 1
assert read(base) == {'tenant': 'alpha'}
assert updated is not base
"""
    before = _run_isolated(before_root, contract)
    assert before.returncode != 0
    assert "AssertionError" in before.stderr
    assert _run_isolated(after_root, contract).returncode == 0


def test_fixture_15_executes_actual_context_manager_cleanup_contract(tmp_path: Path) -> None:
    fixture = _fixture("e2e-ctx-15-context-manager-retry")
    before_root = _materialize(tmp_path, fixture, "before")
    after_root = _materialize(tmp_path, fixture, "after")
    contract = """
from db.conn import Conn
from service.job import job
connection = Conn()
try:
    job(connection, lambda: (_ for _ in ()).throw(RuntimeError('retry failed')))
except RuntimeError as exc:
    assert str(exc) == 'retry failed'
else:
    raise AssertionError('retry failure must propagate')
assert connection.closed
"""
    before = _run_isolated(before_root, contract)
    assert before.returncode != 0
    assert "AssertionError" in before.stderr
    assert _run_isolated(after_root, contract).returncode == 0


def test_fixture_16_executes_actual_exception_narrowing_contract(tmp_path: Path) -> None:
    fixture = _fixture("e2e-ctx-16-narrow-exception-preserves-contract")
    before_root = _materialize(tmp_path, fixture, "before")
    after_root = _materialize(tmp_path, fixture, "after")
    contract = """
from api.read import read
def timeout(): raise TimeoutError('offline')
def programming_error(): raise ValueError('invalid input')
assert read(timeout) == 'cached'
try:
    read(programming_error)
except ValueError as exc:
    assert str(exc) == 'invalid input'
else:
    raise AssertionError('programming errors must not use transport fallback')
"""
    before = _run_isolated(before_root, contract)
    assert before.returncode != 0
    assert "AssertionError" in before.stderr
    assert _run_isolated(after_root, contract).returncode == 0


def test_fixture_17_executes_actual_optional_callback_contract(tmp_path: Path) -> None:
    fixture = _fixture("e2e-ctx-17-null-guard-callback")
    before_root = _materialize(tmp_path, fixture, "before")
    after_root = _materialize(tmp_path, fixture, "after")
    contract = """
from api.start import start
assert start(None) is None
assert start(lambda value: value + 1) == 2
"""
    before = _run_isolated(before_root, contract)
    assert before.returncode != 0
    assert "TypeError" in before.stderr
    assert _run_isolated(after_root, contract).returncode == 0


def test_fixture_18_executes_actual_pagination_bound_contract(tmp_path: Path) -> None:
    fixture = _fixture("e2e-ctx-18-boundary-clamp-pagination")
    before_root = _materialize(tmp_path, fixture, "before")
    after_root = _materialize(tmp_path, fixture, "after")
    contract = """
from jobs.export import run
items = ['a', 'b', 'c']
last, serialized = run(2, 10, items)
assert last == len(items)
assert serialized == 'c'
"""
    before = _run_isolated(before_root, contract)
    assert before.returncode != 0
    assert "AssertionError" in before.stderr
    assert _run_isolated(after_root, contract).returncode == 0


def test_fixture_19_executes_actual_concurrent_state_contract(tmp_path: Path) -> None:
    fixture = _fixture("e2e-ctx-19-locked-task-state")
    before_root = _materialize(tmp_path, fixture, "before")
    after_root = _materialize(tmp_path, fixture, "after")
    contract = """
from threading import Barrier, Thread
from asyncq.report import report
from asyncq.state import TaskState
from asyncq.work import work
state = TaskState(Barrier(2))
threads = [Thread(target=work, args=(state, value)) for value in ('one', 'two')]
for thread in threads: thread.start()
for thread in threads: thread.join()
assert all(not thread.is_alive() for thread in threads)
assert set(report(state)) == {'one', 'two'}
assert len(report(state)) == 2
"""
    before = _run_isolated(before_root, contract)
    assert before.returncode != 0
    assert "AssertionError" in before.stderr
    assert _run_isolated(after_root, contract).returncode == 0


def test_fixture_20_executes_actual_super_validation_contract(tmp_path: Path) -> None:
    fixture = _fixture("e2e-ctx-20-override-calls-super")
    before_root = _materialize(tmp_path, fixture, "before")
    after_root = _materialize(tmp_path, fixture, "after")
    contract = """
from api.admin import access
class User:
    active = True
    internal = False
assert access(User()) is False
"""
    before = _run_isolated(before_root, contract)
    assert before.returncode != 0
    assert "AssertionError" in before.stderr
    assert _run_isolated(after_root, contract).returncode == 0
