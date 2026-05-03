"""Tests for filesystem tools — pure I/O, no LLM."""

from pathlib import Path

import pytest

from chorus.tools import Deps, find_callers, grep, read_file


@pytest.fixture
def repo(tmp_path: Path) -> Path:
    (tmp_path / "src").mkdir()
    (tmp_path / "src" / "main.py").write_text(
        "def calculate_fee(amount):\n    return amount * 0.05\n"
    )
    (tmp_path / "src" / "billing.py").write_text(
        "from .main import calculate_fee\n"
        "result = calculate_fee(100)\n"
    )
    return tmp_path


def test_read_file_returns_contents(repo):
    deps = Deps(repo_dir=repo)
    out = read_file(deps, "src/main.py")
    assert "calculate_fee" in out


def test_read_file_not_found(repo):
    deps = Deps(repo_dir=repo)
    out = read_file(deps, "src/nonexistent.py")
    assert out.startswith("NOT FOUND")


def test_read_file_path_traversal_blocked(repo):
    deps = Deps(repo_dir=repo)
    out = read_file(deps, "../../../etc/passwd")
    assert "outside repo root" in out


def test_grep_finds_pattern(repo):
    deps = Deps(repo_dir=repo)
    out = grep(deps, "calculate_fee")
    # ripgrep may not be available in test env; skip then
    if "ripgrep (rg) not installed" in out:
        pytest.skip("ripgrep not available")
    assert "main.py" in out
    assert "billing.py" in out


def test_find_callers(repo):
    deps = Deps(repo_dir=repo)
    out = find_callers(deps, "calculate_fee")
    if "ripgrep (rg) not installed" in out:
        pytest.skip("ripgrep not available")
    # The definition has `calculate_fee(amount)` and the call has `calculate_fee(100)`
    # Both match the heuristic. That's expected — better than missing real callers.
    assert "calculate_fee" in out
