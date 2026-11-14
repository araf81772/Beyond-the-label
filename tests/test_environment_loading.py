"""Credential loading uses temporary fake secrets and never the user's .env."""
from __future__ import annotations

import json
import os
from pathlib import Path
import shutil
import subprocess
import sys

import pytest

from beyond_label import environment
from beyond_label.provider import (
    PinnedProvider, ProviderFailure, ProviderSettings, credential_presence,
    live_transport, parse_response, serialize_request,
)
from beyond_label.schemas import Request


@pytest.fixture(scope="module")
def module_scope_has_isolated_env_path():
    # This executes before function-scoped fixtures. Do not load/read any file
    # or return environment values: only the path-isolation boolean is needed.
    real_project_env = Path(environment.__file__).resolve().parents[2] / ".env"
    return environment.ENV_PATH != real_project_env


def test_module_scoped_fixtures_are_isolated_before_function_fixtures(module_scope_has_isolated_env_path):
    assert module_scope_has_isolated_env_path is True


@pytest.fixture
def local_env(tmp_path, monkeypatch):
    path = tmp_path / ".env"
    monkeypatch.setattr(environment, "ENV_PATH", path)
    for name in environment.CREDENTIAL_NAMES:
        monkeypatch.delenv(name, raising=False)
    return path


def write_fake(path: Path, content: str) -> None:
    path.write_text(content, encoding="utf-8", newline="\n")


def test_missing_file_is_benign_and_presence_is_boolean(local_env, capsys):
    present = environment.load_local_credentials()
    assert present == {name: False for name in environment.CREDENTIAL_NAMES}
    assert credential_presence() == present
    captured = capsys.readouterr()
    assert captured.out == captured.err == ""


def test_quoted_key_loads_without_disclosure(local_env, capsys, caplog):
    sentinel = "synthetic local key with spaces"
    write_fake(local_env, f'OPENROUTER_API_KEY="{sentinel}"\n')
    present = environment.load_local_credentials()
    assert os.environ["OPENROUTER_API_KEY"] == sentinel
    assert present["OPENROUTER_API_KEY"] is True
    assert all(type(value) is bool for value in present.values())
    captured = capsys.readouterr()
    assert sentinel not in captured.out + captured.err + caplog.text + json.dumps(present)


@pytest.mark.parametrize("existing", ["synthetic-process-key", ""])
def test_existing_environment_wins_even_when_empty(local_env, monkeypatch, existing):
    write_fake(local_env, "OPENROUTER_API_KEY=synthetic-file-key\n")
    monkeypatch.setenv("OPENROUTER_API_KEY", existing)
    present = environment.load_local_credentials()
    assert os.environ["OPENROUTER_API_KEY"] == existing
    assert present["OPENROUTER_API_KEY"] is bool(existing)


def test_only_credential_allowlist_is_loaded_without_interpolation(local_env, monkeypatch):
    monkeypatch.setenv("BTL_INTERPOLATION_SENTINEL", "must-not-expand")
    monkeypatch.delenv("BTL_UNEXPECTED_SETTING", raising=False)
    write_fake(local_env, 'OPENROUTER_API_KEY="literal-${BTL_INTERPOLATION_SENTINEL}"\n'
               'BTL_UNEXPECTED_SETTING=enable-network\n'
               'live_execution_enabled=true\n')
    before_live = os.environ.get("live_execution_enabled")
    present = environment.load_local_credentials()
    assert os.environ["OPENROUTER_API_KEY"] == "literal-${BTL_INTERPOLATION_SENTINEL}"
    assert "BTL_UNEXPECTED_SETTING" not in os.environ
    assert os.environ.get("live_execution_enabled") == before_live
    assert set(present) == set(environment.CREDENTIAL_NAMES)


def test_blank_and_bare_entries_do_not_create_credentials(local_env):
    write_fake(local_env, "OPENROUTER_API_KEY=\nOPENAI_API_KEY\n")
    present = environment.load_local_credentials()
    assert present["OPENROUTER_API_KEY"] is False
    assert present["OPENAI_API_KEY"] is False


def test_loading_uses_explicit_path_instead_of_current_directory(local_env, tmp_path, monkeypatch):
    write_fake(local_env, "OPENROUTER_API_KEY=synthetic-authorized-location\n")
    other = tmp_path / "different-working-directory"
    other.mkdir()
    write_fake(other / ".env", "OPENROUTER_API_KEY=synthetic-wrong-location\n")
    monkeypatch.chdir(other)
    environment.load_local_credentials()
    assert os.environ["OPENROUTER_API_KEY"] == "synthetic-authorized-location"


@pytest.mark.parametrize("kind", ["malformed", "invalid_encoding", "unreadable"])
def test_errors_are_safe_and_do_not_partially_load(local_env, monkeypatch, capsys, caplog, kind):
    sentinel = "synthetic-do-not-disclose-file-value"
    if kind == "malformed":
        write_fake(local_env, f"OPENROUTER_API_KEY={sentinel}\nOPENAI_API_KEY='unterminated\n")
    elif kind == "invalid_encoding":
        local_env.write_bytes(f"OPENROUTER_API_KEY={sentinel}\n".encode() + b"\xff")
    else:
        write_fake(local_env, f"OPENROUTER_API_KEY={sentinel}\n")
        original = Path.open

        def denied(path, *args, **kwargs):
            if path == local_env:
                raise OSError(sentinel)
            return original(path, *args, **kwargs)

        monkeypatch.setattr(Path, "open", denied)
    with pytest.raises(environment.CredentialLoadError) as error:
        environment.load_local_credentials()
    assert "OPENROUTER_API_KEY" not in os.environ
    assert error.value.__cause__ is None
    captured = capsys.readouterr()
    assert sentinel not in str(error.value) + captured.out + captured.err + caplog.text


def test_nul_value_is_rejected_before_any_environment_assignment(local_env):
    write_fake(local_env, "OPENROUTER_API_KEY=synthetic-first-key\n"
               "OPENAI_API_KEY=synthetic-invalid\x00value\n")
    error_type = None
    try:
        environment.load_local_credentials()
    except Exception as error:
        # Native os.environ failures can expose an environment repr in pytest's
        # traceback. Capture only the class while preserving the regression.
        error_type = type(error)
    assert error_type is environment.CredentialLoadError
    assert all(name not in os.environ for name in environment.CREDENTIAL_NAMES)


def settings():
    return ProviderSettings(model="synthetic/model", provider="synthetic-provider")


def test_os_assignment_failure_rolls_back_without_disclosure(local_env, monkeypatch):
    sentinel = "synthetic-assignment-error-secret"
    write_fake(local_env, f"OPENROUTER_API_KEY=synthetic-first\nOPENAI_API_KEY={sentinel}\n")
    original = type(os.environ).__setitem__

    def denied(mapping, name, value):
        if name == "OPENAI_API_KEY":
            raise OSError(sentinel)
        return original(mapping, name, value)

    monkeypatch.setattr(type(os.environ), "__setitem__", denied)
    error_type = None
    safe_message = ""
    try:
        environment.load_local_credentials()
    except Exception as error:
        error_type, safe_message = type(error), str(error)
    assert error_type is environment.CredentialLoadError
    assert safe_message == "local_credentials_unreadable"
    assert all(name not in os.environ for name in environment.CREDENTIAL_NAMES)


def test_provider_constructor_loads_and_secret_request_never_reaches_transport(local_env):
    sentinel = "synthetic-constructor-private-key"
    write_fake(local_env, f"OPENROUTER_API_KEY={sentinel}\n")
    calls = []
    provider = PinnedProvider(settings(), lambda payload: calls.append(payload))
    assert os.environ["OPENROUTER_API_KEY"] == sentinel
    with pytest.raises(ProviderFailure, match="credential_or_header_in_request") as error:
        provider.request(Request(messages=[{"role": "user", "content": sentinel}]))
    assert calls == [] and sentinel not in str(error.value)
    with pytest.raises(ProviderFailure, match="offline_only_live_transport_unavailable"):
        live_transport()


def test_direct_serialization_loads_before_secret_check(local_env):
    sentinel = "synthetic-direct-serialization-key"
    write_fake(local_env, f"OPENROUTER_API_KEY={sentinel}\n")
    with pytest.raises(ProviderFailure, match="credential_or_header_in_request"):
        serialize_request(Request(messages=[{"role": "user", "content": sentinel}]), settings())


def test_direct_response_parse_loads_before_redaction(local_env):
    sentinel = "synthetic-direct-response-key"
    write_fake(local_env, f"OPENROUTER_API_KEY={sentinel}\n")
    pinned = settings()
    payload = {"model": pinned.model,
               "provider": {"only": [pinned.provider], "allow_fallbacks": False},
               "messages": []}
    raw = {"model": pinned.model, "provider": pinned.provider, "id": "synthetic-response",
           "choices": [{"message": {"role": "assistant", "content": sentinel}, "finish_reason": "stop"}],
           "usage": {}}
    result = parse_response(raw, payload, pinned)
    assert result.reply.content == "[redacted]"
    assert sentinel not in result.model_dump_json()


def test_credential_presence_automatically_loads_and_returns_no_values(local_env):
    sentinel = "synthetic-presence-private-key"
    write_fake(local_env, f"OPENROUTER_API_KEY={sentinel}\n")
    present = credential_presence()
    assert present["OPENROUTER_API_KEY"] is True
    assert all(type(value) is bool for value in present.values())
    assert sentinel not in json.dumps(present)


def test_import_has_no_loading_side_effects_in_isolated_package(tmp_path):
    package = tmp_path / "src" / "beyond_label"
    package.mkdir(parents=True)
    (package / "__init__.py").write_text("", encoding="utf-8")
    shutil.copyfile(Path(environment.__file__), package / "environment.py")
    write_fake(tmp_path / ".env", "OPENROUTER_API_KEY=synthetic-import-key\n")
    child_env = {key: value for key, value in os.environ.items()
                 if key not in environment.CREDENTIAL_NAMES}
    child_env["PYTHONPATH"] = str(tmp_path / "src")
    code = ("import os, socket; "
            "socket.socket.connect=lambda *a,**k: (_ for _ in ()).throw(AssertionError('offline')); "
            "import beyond_label.environment; "
            "print('present' if 'OPENROUTER_API_KEY' in os.environ else 'absent')")
    result = subprocess.run([sys.executable, "-c", code], cwd=tmp_path,
                            env=child_env, capture_output=True, text=True, timeout=15)
    assert result.returncode == 0
    assert result.stdout.strip() == "absent" and result.stderr == ""


def test_presence_cli_uses_project_root_and_prints_only_safe_metadata(tmp_path):
    package = tmp_path / "src" / "beyond_label"
    package.mkdir(parents=True)
    (package / "__init__.py").write_text("", encoding="utf-8")
    shutil.copyfile(Path(environment.__file__), package / "environment.py")
    sentinel = "synthetic-cli-private-key"
    write_fake(tmp_path / ".env", f"OPENROUTER_API_KEY={sentinel}\n")
    other = tmp_path / "another-working-directory"
    other.mkdir()
    child_env = {key: value for key, value in os.environ.items()
                 if key not in environment.CREDENTIAL_NAMES}
    child_env["PYTHONPATH"] = str(tmp_path / "src")
    code = ("import runpy, socket; "
            "socket.socket.connect=lambda *a,**k: (_ for _ in ()).throw(AssertionError('offline')); "
            "runpy.run_module('beyond_label.environment',run_name='__main__')")
    result = subprocess.run([sys.executable, "-c", code], cwd=other,
                            env=child_env, capture_output=True, text=True, timeout=15)
    assert result.returncode == 0
    data = json.loads(result.stdout)
    assert data["status"] == "ok" and data["provider_calls"] == 0
    assert data["credential_presence"]["OPENROUTER_API_KEY"] is True
    assert all(type(value) is bool for value in data["credential_presence"].values())
    assert sentinel not in result.stdout + result.stderr
    assert result.stderr == ""
