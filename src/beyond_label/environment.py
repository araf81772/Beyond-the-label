"""Load local credentials without enabling execution or revealing their values.

Imports have no side effects. The pinned python-dotenv parser handles quoting
without interpolation; only known credential names enter the process environment.
"""
from __future__ import annotations

import json
import os
from pathlib import Path

from dotenv.parser import parse_stream

ENV_PATH = Path(__file__).resolve().parents[2] / ".env"
CREDENTIAL_NAMES = ("OPENROUTER_API_KEY", "OPENAI_API_KEY", "ANTHROPIC_API_KEY", "ADAPTION_API_KEY")


class CredentialLoadError(RuntimeError):
    """Contains a fixed reason code only, never file contents or exception text."""


def load_local_credentials() -> dict[str, bool]:
    """Load the project's .env lazily; existing process values always win.

    Missing files are normal for clean clones. Invalid files fail before any
    partial assignment. No model, budget, routing or execution flags are loaded.
    """
    values: dict[str, str] = {}
    try:
        with ENV_PATH.open("r", encoding="utf-8-sig") as stream:
            for binding in parse_stream(stream):
                if binding.error:
                    raise CredentialLoadError("invalid_local_credentials_format")
                if binding.key in CREDENTIAL_NAMES and binding.value is not None:
                    values[binding.key] = binding.value
    except FileNotFoundError:
        pass
    except (OSError, UnicodeError, ValueError):
        raise CredentialLoadError("local_credentials_unreadable") from None
    # Validate the complete set before changing the process environment.
    if any("\x00" in value for value in values.values()):
        raise CredentialLoadError("invalid_local_credentials_format")
    inserted: list[str] = []
    try:
        for name, value in values.items():
            if name not in os.environ:
                os.environ[name] = value
                inserted.append(name)
    except (OSError, UnicodeError, ValueError):
        # Restore the pre-load state if the OS rejects a later assignment.
        for name in inserted:
            os.environ.pop(name, None)
        raise CredentialLoadError("local_credentials_unreadable") from None
    return {name: bool(os.environ.get(name, "").strip()) for name in CREDENTIAL_NAMES}


def main() -> int:
    try:
        presence = load_local_credentials()
    except CredentialLoadError as error:
        print(json.dumps({"status": "error", "reason": str(error)}))
        return 1
    print(json.dumps({"status": "ok", "credential_presence": presence,
                      "provider_calls": 0}))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
