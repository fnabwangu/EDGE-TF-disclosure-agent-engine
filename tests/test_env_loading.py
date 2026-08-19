"""Environment file loading, and the guarantee that a populated .env is never committed."""

import os
import subprocess
from pathlib import Path

import pytest

from core.env import ensure_env_loaded, load_env_file, parse_env_file, reset_for_tests
from orchestration.llm import model_status, resolve_config

REPO_ROOT = Path(__file__).resolve().parent.parent


@pytest.fixture(autouse=True)
def _clean():
    """load_env_file writes straight to os.environ, so snapshot and restore it."""
    reset_for_tests()
    snapshot = dict(os.environ)
    yield
    os.environ.clear()
    os.environ.update(snapshot)
    reset_for_tests()


# -- the secret must not be committable -----------------------------------


def test_a_populated_env_file_is_ignored_by_git():
    result = subprocess.run(
        ["git", "check-ignore", "-q", ".env"], cwd=REPO_ROOT, capture_output=True
    )
    assert result.returncode == 0, ".env is not gitignored; a real key could be committed"


def test_the_template_stays_tracked():
    result = subprocess.run(
        ["git", "check-ignore", "-q", ".env.template"], cwd=REPO_ROOT, capture_output=True
    )
    assert result.returncode != 0, ".env.template must remain tracked"


# -- parsing ---------------------------------------------------------------


def test_parses_comments_blanks_quotes_and_export():
    parsed = parse_env_file(
        """
        # a comment
        OPENAI_API_KEY=sk-plain

        export ANTHROPIC_API_KEY=sk-ant-exported
        QUOTED="with spaces"
        SINGLE='single'
        NOT_A_PAIR
        """
    )
    assert parsed["OPENAI_API_KEY"] == "sk-plain"
    assert parsed["ANTHROPIC_API_KEY"] == "sk-ant-exported"
    assert parsed["QUOTED"] == "with spaces"
    assert parsed["SINGLE"] == "single"
    assert "NOT_A_PAIR" not in parsed


def test_values_containing_equals_survive():
    assert parse_env_file("TOKEN=abc=def==")["TOKEN"] == "abc=def=="


def test_a_missing_file_is_not_an_error(tmp_path):
    assert load_env_file(tmp_path / "absent") == {}


# -- precedence ------------------------------------------------------------


def test_a_real_environment_variable_wins(tmp_path, monkeypatch):
    env_file = tmp_path / ".env"
    env_file.write_text("EDGE_TEST_KEY=from-file\n", encoding="utf-8")
    monkeypatch.setenv("EDGE_TEST_KEY", "from-environment")

    load_env_file(env_file)
    assert os.environ["EDGE_TEST_KEY"] == "from-environment"


def test_override_is_available_when_asked(tmp_path, monkeypatch):
    env_file = tmp_path / ".env"
    env_file.write_text("EDGE_TEST_KEY=from-file\n", encoding="utf-8")
    monkeypatch.setenv("EDGE_TEST_KEY", "from-environment")

    load_env_file(env_file, override=True)
    assert os.environ["EDGE_TEST_KEY"] == "from-file"


def test_load_reports_names_only(tmp_path, monkeypatch):
    """A secret value must never come back out of the loader."""
    monkeypatch.delenv("EDGE_TEST_KEY", raising=False)
    env_file = tmp_path / ".env"
    env_file.write_text("EDGE_TEST_KEY=super-secret\n", encoding="utf-8")

    applied = load_env_file(env_file)
    assert applied == {"EDGE_TEST_KEY": "set"}
    assert "super-secret" not in str(applied)


def test_ensure_is_idempotent(tmp_path, monkeypatch):
    env_file = tmp_path / ".env"
    env_file.write_text("EDGE_TEST_KEY=first\n", encoding="utf-8")
    monkeypatch.delenv("EDGE_TEST_KEY", raising=False)

    ensure_env_loaded(env_file)
    env_file.write_text("EDGE_TEST_KEY=second\n", encoding="utf-8")
    ensure_env_loaded(env_file)

    assert os.environ["EDGE_TEST_KEY"] == "first"


# -- the router picks it up ------------------------------------------------


def test_a_key_in_the_env_file_activates_the_router(tmp_path, monkeypatch):
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
    monkeypatch.chdir(tmp_path)
    (tmp_path / ".env").write_text("OPENAI_API_KEY=sk-from-file\nOPENAI_MODEL=gpt-4o\n", encoding="utf-8")

    config = resolve_config()
    assert config is not None
    assert config.provider == "openai"


def test_status_reports_the_model_without_the_secret(tmp_path, monkeypatch):
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
    monkeypatch.setenv("OPENAI_API_KEY", "sk-should-never-be-printed")
    monkeypatch.setenv("OPENAI_MODEL", "gpt-4o")

    status = model_status()
    assert status == "openai:gpt-4o"
    assert "sk-should-never-be-printed" not in status


def test_template_placeholders_do_not_activate_the_router(tmp_path, monkeypatch):
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
    monkeypatch.chdir(tmp_path)
    (tmp_path / ".env").write_text("OPENAI_API_KEY=your_openai_api_key_here\n", encoding="utf-8")
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)

    assert resolve_config() is None
    assert "keyword router" in model_status()
