"""Tests for app.config — Settings defaults, env-var binding, and the get_settings() singleton.

All Settings(...) constructions pass `_env_file=None` to bypass the repo's `.env`
file so tests assert against the code's defaults, not whatever the developer has
locally.
"""
from __future__ import annotations

from pathlib import Path

import pytest

from app import config
from app.config import Settings, get_settings


# Env vars that Settings binds. Cleared at the start of every test that
# instantiates Settings, so the test sees the defined defaults (or its own
# explicit setenv) and not the developer's shell.
_BOUND_ENV_VARS = (
    "OPENAI_API_KEY",
    "OPENAI_BASE_URL",
    "MODEL_NAME",
    "WORKSPACE_DIR",
    "MAX_TOOL_ITERATIONS",
)


@pytest.fixture
def clean_env(monkeypatch: pytest.MonkeyPatch):
    for var in _BOUND_ENV_VARS:
        monkeypatch.delenv(var, raising=False)
    # Reset the module-level singleton so get_settings() in this test sees a
    # fresh environment.
    monkeypatch.setattr(config, "_settings", None)
    yield monkeypatch


# ---------------------------------------------------------------- defaults

def test_settings_openai_api_key_defaults_to_sk_missing(clean_env):
    s = Settings(_env_file=None)

    assert s.openai_api_key == "sk-missing"


def test_settings_openai_base_url_default(clean_env):
    s = Settings(_env_file=None)

    assert s.openai_base_url == "https://api.openai.com/v1"


def test_settings_model_name_default(clean_env):
    s = Settings(_env_file=None)

    assert s.model_name == "gpt-4o-mini"


def test_settings_workspace_dir_default(clean_env):
    s = Settings(_env_file=None)

    assert s.workspace_dir == Path("./workspace")


def test_settings_max_tool_iterations_default_is_int(clean_env):
    s = Settings(_env_file=None)

    assert s.max_tool_iterations == 25
    assert isinstance(s.max_tool_iterations, int)


# ---------------------------------------------------------- env-var binding

def test_settings_reads_openai_api_key_from_env(clean_env):
    clean_env.setenv("OPENAI_API_KEY", "sk-from-env")

    s = Settings(_env_file=None)

    assert s.openai_api_key == "sk-from-env"


def test_settings_parses_max_tool_iterations_as_int(clean_env):
    clean_env.setenv("MAX_TOOL_ITERATIONS", "5")

    s = Settings(_env_file=None)

    assert s.max_tool_iterations == 5
    assert isinstance(s.max_tool_iterations, int)


def test_settings_coerces_workspace_dir_to_path(clean_env, tmp_path: Path):
    target = tmp_path / "ws"
    clean_env.setenv("WORKSPACE_DIR", str(target))

    s = Settings(_env_file=None)

    assert s.workspace_dir == target
    assert isinstance(s.workspace_dir, Path)


def test_settings_ignores_unknown_env_vars(clean_env):
    clean_env.setenv("SOMETHING_TOTALLY_UNRELATED", "x")

    # Constructing must not raise; the unknown var is dropped silently
    # because model_config sets extra="ignore".
    s = Settings(_env_file=None)

    assert not hasattr(s, "something_totally_unrelated")


# --------------------------------------------------------- workspace_path

def test_workspace_path_expands_user(clean_env, monkeypatch: pytest.MonkeyPatch, tmp_path: Path):
    # Force ~ to resolve into a known directory so the assertion is stable
    # across machines.
    monkeypatch.setenv("HOME", str(tmp_path))
    clean_env.setenv("WORKSPACE_DIR", "~/ws")

    s = Settings(_env_file=None)

    assert s.workspace_path == (tmp_path / "ws").resolve()


def test_workspace_path_resolves_relative_to_absolute(clean_env, tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    monkeypatch.chdir(tmp_path)
    clean_env.setenv("WORKSPACE_DIR", "rel/ws")

    s = Settings(_env_file=None)

    assert s.workspace_path.is_absolute()
    assert s.workspace_path == (tmp_path / "rel" / "ws").resolve()


# ------------------------------------------------------------- singleton

def test_get_settings_returns_same_instance_on_repeat_calls(clean_env):
    first = get_settings()
    second = get_settings()

    assert first is second


def test_get_settings_returns_fresh_instance_after_reset(clean_env, monkeypatch: pytest.MonkeyPatch):
    first = get_settings()
    monkeypatch.setattr(config, "_settings", None)

    second = get_settings()

    assert first is not second
