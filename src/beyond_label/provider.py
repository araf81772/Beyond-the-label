"""Offline, injected-transport provider contract and immutable retry logging.

No network implementation is supplied. OpenRouter field names and returned
metadata assumptions are an offline contract pending official documentation
verification before any live execution. Credentials never enter payloads,
responses, exceptions, or logs returned by this module.
"""

from __future__ import annotations

from collections.abc import Callable
from copy import deepcopy
import hashlib
import json
import math
import os
import re
import time
from typing import Any
from urllib.error import HTTPError, URLError

import httpx
from pydantic import Field

from .schemas import ModelReply, Request, StrictModel, ToolCall
from .environment import CREDENTIAL_NAMES, load_local_credentials


class ProviderSettings(StrictModel):
    model: str = Field(min_length=1)
    provider: str = Field(min_length=1)
    temperature: float | None = 0
    reasoning: dict[str, Any] = Field(default_factory=dict)
    max_output_tokens: int = Field(default=512, gt=0)


class ProviderResult(StrictModel):
    reply: ModelReply
    raw_response: dict[str, Any]
    payload: dict[str, Any]
    usage: dict[str, Any]
    returned_model: str
    returned_provider: str
    request_id: str | None
    finish_reason: str | None
    latency_seconds: float = Field(ge=0)


class ProviderFailure(RuntimeError):
    def __init__(self, reason: str):
        # Only module-defined reason codes are ever passed by this module.
        self.reason = reason
        super().__init__(reason)


_CREDENTIAL_ENV = CREDENTIAL_NAMES
_SENSITIVE_KEYS = {"authorization", "proxy-authorization", "headers", "api_key", "api-key", "x-api-key", "access_token", "refresh_token", "credentials"}
_TOKEN_PATTERNS = (
    re.compile(r"sk-(?:or-v1-)?[A-Za-z0-9_-]{20,}"),
    re.compile(r"(?:ghp_|github_pat_)[A-Za-z0-9_]{20,}"),
    re.compile(r"Bearer\s+[A-Za-z0-9._-]{15,}", re.IGNORECASE),
    re.compile(r"\b(?:proxy-authorization|authorization)\s*:\s*[^\r\n]+", re.IGNORECASE),
    re.compile(r'"(?:authorization|proxy-authorization|api_key|x-api-key|access_token|refresh_token)"\s*:\s*"(?:\\.|[^"\\])*"', re.IGNORECASE),
)
_EXPLICIT_REFUSAL = re.compile(r"\A\s*I (?:refuse\b|cannot comply\b|can't comply\b)", re.IGNORECASE)


def credential_presence() -> dict[str, bool]:
    """Automatically load local credentials; return presence booleans only."""
    return load_local_credentials()


def live_transport(*args: Any, **kwargs: Any) -> dict[str, Any]:
    raise ProviderFailure("offline_only_live_transport_unavailable")


def _redact_string(value: str) -> str:
    for name in _CREDENTIAL_ENV:
        credential = os.environ.get(name)
        if credential:
            value = value.replace(credential, "[redacted]")
    for pattern in _TOKEN_PATTERNS:
        value = pattern.sub("[redacted]", value)
    return value


def _sanitized(value: Any) -> Any:
    if isinstance(value, dict):
        return {
            _redact_string(str(key)): _sanitized(item) for key, item in value.items()
            if str(key).lower() not in _SENSITIVE_KEYS
        }
    if isinstance(value, list):
        return [_sanitized(item) for item in value]
    if isinstance(value, str):
        return _redact_string(value)
    if isinstance(value, float) and not math.isfinite(value):
        return "[nonfinite numeric value]"
    if value is None or isinstance(value, (bool, int, float)):
        return value
    return "[unsupported value]"


def canonical_json(payload: dict[str, Any]) -> str:
    try:
        return json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=False, allow_nan=False)
    except (TypeError, ValueError):
        raise ProviderFailure("request_not_json_serializable") from None


def request_hash(payload: dict[str, Any]) -> str:
    return hashlib.sha256(canonical_json(payload).encode("utf-8")).hexdigest()


def serialize_request(request: Request, settings: ProviderSettings) -> dict[str, Any]:
    """Allowlist provider fields; no headers, credentials or research envelope."""
    load_local_credentials()
    if request.parallel_tool_calls:
        raise ProviderFailure("parallel_tools_forbidden")
    for message in request.messages:
        if set(message) - {"role", "content", "tool_calls", "tool_call_id", "name"}:
            raise ProviderFailure("unexpected_message_field")
        if message.get("role") not in {"system", "user", "assistant", "tool"}:
            raise ProviderFailure("invalid_message_role")
    payload: dict[str, Any] = {
        "model": settings.model,
        "provider": {"only": [settings.provider], "allow_fallbacks": False},
        "messages": deepcopy(request.messages),
        "max_tokens": settings.max_output_tokens,
        "reasoning": deepcopy(settings.reasoning),
        "parallel_tool_calls": False,
    }
    if settings.temperature is not None:
        payload["temperature"] = settings.temperature
    if request.tools:
        payload["tools"] = deepcopy(request.tools)
        payload["tool_choice"] = request.tool_choice or "auto"
    # Reject instead of rewriting the actual request: retries must be identical.
    encoded = canonical_json(payload)
    if canonical_json(_sanitized(payload)) != encoded:
        raise ProviderFailure("credential_or_header_in_request")
    return json.loads(encoded)


def _usage(raw: Any) -> dict[str, Any]:
    if not isinstance(raw, dict):
        return {}
    # Preserve provider numeric evidence including nested token details, never
    # arbitrary response text or header-shaped metadata masquerading as usage.
    def numbers(value: Any) -> Any:
        if isinstance(value, dict):
            return {_redact_string(str(k)): numbers(v) for k, v in value.items()
                    if str(k).lower() not in _SENSITIVE_KEYS
                    and (isinstance(v, dict) or (isinstance(v, (int, float)) and not isinstance(v, bool)
                                               and math.isfinite(v) and v >= 0))}
        return value
    return numbers(raw)


def _valid_usage(raw: Any) -> bool:
    if raw is None:
        return True
    if not isinstance(raw, dict):
        return False
    for key, value in raw.items():
        if str(key).lower() in _SENSITIVE_KEYS:
            continue
        if isinstance(value, dict) and not _valid_usage(value):
            return False
        if isinstance(value, (int, float)) and not isinstance(value, bool):
            if not math.isfinite(value) or value < 0:
                return False
    return True


def _latency(started: float) -> float | None:
    measured = time.perf_counter() - started
    return measured if math.isfinite(measured) and measured >= 0 else None


def _safe_response(raw: Any) -> dict[str, Any]:
    if not isinstance(raw, dict):
        return {}
    return _sanitized({key: raw[key] for key in
                       ("id", "model", "provider", "choices", "usage", "error", "created", "object")
                       if key in raw})


def _parse(raw: Any, payload: dict[str, Any], settings: ProviderSettings, latency: float) -> ProviderResult:
    if not isinstance(raw, dict):
        raise ProviderFailure("protocol_invalid_response")
    if raw.get("model") != settings.model:
        raise ProviderFailure("model_mismatch")
    if raw.get("provider") != settings.provider:
        raise ProviderFailure("provider_mismatch")
    choices = raw.get("choices")
    if not isinstance(choices, list) or len(choices) != 1 or not isinstance(choices[0], dict):
        raise ProviderFailure("protocol_invalid_response")
    choice = choices[0]
    message = choice.get("message")
    if not isinstance(message, dict):
        raise ProviderFailure("protocol_invalid_response")
    safe_message = _sanitized({key: message[key] for key in ("role", "content", "tool_calls", "refusal") if key in message})
    calls: list[ToolCall] = []
    raw_calls = safe_message.get("tool_calls")
    if raw_calls is not None and not isinstance(raw_calls, list):
        # A model's malformed action is one decision, not infrastructure noise.
        calls.append(ToolCall(id="invalid_call_1", name="__invalid_tool_call__", arguments=None))
    else:
        for index, call in enumerate(raw_calls or [], 1):
            function = call.get("function") if isinstance(call, dict) else None
            if not isinstance(function, dict) or not isinstance(function.get("name"), str):
                calls.append(ToolCall(id=f"invalid_call_{index}", name="__invalid_tool_call__", arguments=None))
                continue
            original_call = message["tool_calls"][index - 1]
            original_function = original_call.get("function") if isinstance(original_call, dict) else None
            if (isinstance(original_function, dict)
                    and original_function.get("arguments") != function.get("arguments")):
                # Removing an extra credential field must never repair an
                # invalid action into a valid inspect/commit. Preserve a
                # terminal invalid action while keeping secrets out of traces.
                safe_message["tool_calls"][index - 1] = {
                    "id": f"invalid_call_{index}", "type": "function",
                    "function": {"name": "__invalid_tool_call__", "arguments": None},
                    "redaction_reason": "sensitive_tool_arguments",
                    "sanitized_original_function": deepcopy(function),
                }
                calls.append(ToolCall(id=f"invalid_call_{index}", name="__invalid_tool_call__", arguments=None))
                continue
            call_id = call.get("id")
            calls.append(ToolCall(
                id=call_id if isinstance(call_id, str) else f"call_{index}",
                name=function["name"], arguments=function.get("arguments"),
            ))
    content = safe_message.get("content")
    if content is not None and not isinstance(content, str):
        raise ProviderFailure("protocol_invalid_response")
    finish_reason = choice.get("finish_reason")
    refusal = safe_message.get("refusal")
    # Deliberately narrow lexical rule, fixed offline before any observation.
    # Other ambiguous plain text remains no-tool output for the one re-prompt.
    lexical_refusal = isinstance(content, str) and _EXPLICIT_REFUSAL.match(content) is not None
    reply = ModelReply(tool_calls=tuple(calls), content=content,
                       refused=bool(refusal) or lexical_refusal or finish_reason == "content_filter")
    if not _valid_usage(raw.get("usage")):
        raise ProviderFailure("protocol_invalid_usage")
    usage = _usage(raw.get("usage"))
    safe_raw = {
        "id": _redact_string(raw["id"]) if isinstance(raw.get("id"), str) else None,
        "model": settings.model, "provider": settings.provider,
        "choices": [{"message": safe_message, "finish_reason": _redact_string(finish_reason) if isinstance(finish_reason, str) else None}],
        "usage": usage,
    }
    return ProviderResult(
        reply=reply, raw_response=safe_raw, payload=deepcopy(payload), usage=usage,
        returned_model=settings.model, returned_provider=settings.provider,
        request_id=safe_raw["id"], finish_reason=safe_raw["choices"][0]["finish_reason"],
        latency_seconds=latency,
    )


def _infrastructure_reason(exc: BaseException) -> str | None:
    if isinstance(exc, (TimeoutError, httpx.TimeoutException)):
        return "timeout"
    if isinstance(exc, (HTTPError, httpx.HTTPStatusError)):
        return "http_error"
    if isinstance(exc, (ConnectionError, URLError, httpx.TransportError)):
        return "connection_error"
    return None


def parse_response(raw: Any, payload: dict[str, Any], settings: ProviderSettings,
                   latency_seconds: float = 0.0) -> ProviderResult:
    """Replay saved safe response evidence without invoking any transport."""
    load_local_credentials()
    if not math.isfinite(latency_seconds) or latency_seconds < 0:
        raise ProviderFailure("invalid_latency_measurement")
    if payload.get("model") != settings.model or payload.get("provider") != {
        "only": [settings.provider], "allow_fallbacks": False,
    }:
        raise ProviderFailure("request_pin_mismatch")
    if canonical_json(_sanitized(payload)) != canonical_json(payload):
        raise ProviderFailure("credential_or_header_in_request")
    return _parse(raw, payload, settings, latency_seconds)


class PinnedProvider:
    """Exactly one pinned provider/model; transport must be explicitly injected."""

    def __init__(self, settings: ProviderSettings,
                 transport: Callable[[dict[str, Any]], dict[str, Any] | None],
                 sleep: Callable[[float], None] | None = None):
        load_local_credentials()
        self.settings = settings
        self.transport = transport
        self.sleep = sleep or (lambda seconds: None)

    def request(self, request: Request, *,
                log_attempt: Callable[[dict[str, Any]], None] | None = None,
                start_attempt: int = 1) -> ProviderResult:
        if isinstance(start_attempt, bool) or not isinstance(start_attempt, int) or not 1 <= start_attempt <= 4:
            raise ProviderFailure("invalid_start_attempt")
        payload = serialize_request(request, self.settings)
        encoded = canonical_json(payload)
        digest = request_hash(payload)

        def emit(event: str, attempt: int, **details: Any) -> None:
            if log_attempt is not None:
                # Each log owns an independent copy; logger or transport
                # mutation cannot change a subsequent attempt's request.
                log_attempt({"event": event, "attempt": attempt, "request_hash": digest,
                             "payload": json.loads(encoded), **deepcopy(details)})

        for attempt in range(start_attempt, 5):
            emit("attempt_started", attempt, usage={}, latency_seconds=0.0)
            started = time.perf_counter()
            try:
                raw = self.transport(json.loads(encoded))
            except Exception as exc:
                reason = _infrastructure_reason(exc)
                latency = _latency(started)
                if latency is None:
                    emit("attempt_failed", attempt, reason="invalid_latency_measurement", infrastructure=False,
                         retryable=False, usage={}, latency_seconds=None)
                    raise ProviderFailure("invalid_latency_measurement") from None
                if reason is None:
                    # Never include exception text, repr, request headers or body.
                    safe_reason = exc.reason if isinstance(exc, ProviderFailure) and exc.reason == "offline_only_live_transport_unavailable" else "transport_failure"
                    emit("attempt_failed", attempt, reason=safe_reason, infrastructure=False,
                         retryable=False, usage={}, latency_seconds=latency)
                    raise ProviderFailure(safe_reason) from None
            else:
                latency = _latency(started)
                if latency is None:
                    emit("attempt_failed", attempt, reason="invalid_latency_measurement", infrastructure=False,
                         retryable=False, usage=_usage(raw.get("usage")) if isinstance(raw, dict) else {},
                         latency_seconds=None, raw_response=_safe_response(raw))
                    raise ProviderFailure("invalid_latency_measurement")
                reason = "empty_body" if raw is None or raw == "" or raw == b"" else None
                if reason is None:
                    try:
                        result = parse_response(raw, payload, self.settings, latency)
                    except ProviderFailure as exc:
                        safe_raw = _safe_response(raw)
                        emit("attempt_failed", attempt, reason=exc.reason, infrastructure=False,
                             retryable=False, usage=_usage(raw.get("usage")) if isinstance(raw, dict) else {},
                             latency_seconds=latency, raw_response=safe_raw,
                             returned_model=safe_raw.get("model"), returned_provider=safe_raw.get("provider"),
                             request_id=safe_raw.get("id"))
                        raise
                    emit("attempt_succeeded", attempt, usage=result.usage,
                         latency_seconds=latency, result=result.model_dump(mode="json"))
                    return result
            emit("attempt_failed", attempt, reason=reason, infrastructure=True,
                 retryable=attempt < 4, usage={}, latency_seconds=latency)
            if attempt == 4:
                raise ProviderFailure(f"infrastructure_exhausted:{reason}")
            self.sleep(float(2 ** (attempt - 1)))
        raise ProviderFailure("unreachable_attempt_state")
