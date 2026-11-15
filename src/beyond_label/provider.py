"""Injected-transport provider contract and immutable retry logging.

Network adapters are separate and explicitly injected. OpenRouter routing slugs
and returned provider display names are separate pins. Its documented metadata
identity mode requires the transport to request X-OpenRouter-Metadata: enabled; that
noncredential HTTP header is not part of this module's JSON request payload.
Credentials never enter payloads, responses, exceptions, or returned logs.
"""

from __future__ import annotations

from collections.abc import Callable
from copy import deepcopy
from dataclasses import dataclass
import hashlib
import json
import math
import os
import re
import time
from typing import Any, Literal
from urllib.error import HTTPError, URLError

import httpx
from pydantic import Field

from .schemas import ModelReply, Request, StrictModel, ToolCall
from .environment import CREDENTIAL_NAMES, load_local_credentials


class ProviderSettings(StrictModel):
    model: str = Field(min_length=1)
    provider: str = Field(min_length=1)
    provider_route: str | None = Field(default=None, min_length=1)
    provider_identity_source: Literal["provider", "openrouter_metadata"] = "provider"
    require_parameters: bool = Field(default=False, strict=True)
    free_only: bool = Field(default=False, strict=True)
    # OpenRouter prompt/completion caps use USD per million tokens; request and
    # image caps use USD per unit. None retains the historical serialization.
    max_price: dict[str, Any] | None = None
    # Explicit documented names of the SAME model snapshot, never fallbacks.
    # Empty preserves the historical exact-request-model identity requirement.
    accepted_returned_models: tuple[str, ...] = ()
    temperature: float | None = 0
    reasoning: dict[str, Any] | None = Field(default_factory=dict)
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


@dataclass(frozen=True)
class TransportOutcome:
    """A delivered response plus separate, fixed local accounting evidence.

    The local error is logged on the attempt, never inserted into upstream raw
    response bytes or the replayed ProviderResult.
    """

    raw_response: Any
    accounting_error: str

    def __post_init__(self):
        if self.accounting_error != "budget_settlement_failed":
            raise ProviderFailure("invalid_transport_accounting_metadata")


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


def _provider_pin(settings: ProviderSettings) -> dict[str, Any]:
    route = settings.provider if settings.provider_route is None else settings.provider_route
    pin = {"only": [route], "allow_fallbacks": False}
    if settings.require_parameters:
        pin["require_parameters"] = True
    if settings.free_only:
        pin["max_price"] = {"prompt": 0, "completion": 0, "request": 0, "image": 0}
    elif settings.max_price is not None:
        pin["max_price"] = deepcopy(settings.max_price)
    return pin


def _validate_settings_safety(settings: ProviderSettings) -> None:
    # The expected display identity may not appear in the wire payload when a
    # distinct routing slug is used, but it is still recorded in run manifests.
    values = settings.model_dump(mode="json")
    if canonical_json(_sanitized(values)) != canonical_json(values):
        raise ProviderFailure("credential_or_header_in_request")
    if settings.max_price is not None:
        prices = settings.max_price
        try:
            valid_prices = (isinstance(prices, dict) and set(prices) == {"prompt", "completion", "request", "image"}
                            and all(type(value) in (int, float) and math.isfinite(value) and value >= 0
                                    for value in prices.values()) and not settings.free_only)
        except (OverflowError, ValueError):
            valid_prices = False
        if not valid_prices:
            raise ProviderFailure("invalid_provider_price_caps")
    if settings.accepted_returned_models:
        # OpenRouter's endpoint catalog identifies this exact dated snapshot.
        # Native and namespaced response forms are explicitly recorded in the
        # run settings; arbitrary aliases or other models remain forbidden.
        allowed = {"openai/gpt-4.1-mini-2025-04-14", "gpt-4.1-mini-2025-04-14"}
        if (settings.model != "openai/gpt-4.1-mini" or settings.provider != "OpenAI"
                or settings.provider_route != "openai" or settings.free_only
                or settings.provider_identity_source != "openrouter_metadata"
                or not settings.require_parameters
                or not isinstance(settings.accepted_returned_models, tuple)
                or len(set(settings.accepted_returned_models)) != len(settings.accepted_returned_models)
                or any(value not in allowed for value in settings.accepted_returned_models)):
            raise ProviderFailure("invalid_returned_model_pins")
    if settings.free_only and (not re.fullmatch(r"[A-Za-z0-9_-]+/[A-Za-z0-9_.-]+:free", settings.model)
            or settings.model.startswith("openrouter/") or not settings.provider_route
            or not settings.require_parameters or settings.provider_identity_source != "openrouter_metadata"):
        raise ProviderFailure("invalid_free_provider_settings")


def serialize_request(request: Request, settings: ProviderSettings) -> dict[str, Any]:
    """Allowlist provider fields; no headers, credentials or research envelope."""
    load_local_credentials()
    _validate_settings_safety(settings)
    if request.parallel_tool_calls:
        raise ProviderFailure("parallel_tools_forbidden")
    for message in request.messages:
        if set(message) - {"role", "content", "tool_calls", "tool_call_id", "name"}:
            raise ProviderFailure("unexpected_message_field")
        if message.get("role") not in {"system", "user", "assistant", "tool"}:
            raise ProviderFailure("invalid_message_role")
    payload: dict[str, Any] = {
        "model": settings.model,
        "provider": _provider_pin(settings),
        "messages": deepcopy(request.messages),
        "max_tokens": settings.max_output_tokens,
        "parallel_tool_calls": False,
    }
    if settings.reasoning is not None:
        payload["reasoning"] = deepcopy(settings.reasoning)
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
    result = numbers(raw)
    # This documented billing-mode flag is the sole nonnumeric usage field
    # retained. Paid accounting must distinguish upstream BYOK spend from
    # OpenRouter credits; neither absent evidence nor 0/1 means false/true.
    if type(raw.get("is_byok")) is bool:
        result["is_byok"] = raw["is_byok"]
    return result


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
                       ("id", "model", "provider", "openrouter_metadata", "choices", "usage", "error", "created", "object")
                       if key in raw})


def _validate_provider_identity(raw: dict[str, Any], settings: ProviderSettings) -> None:
    if settings.provider_identity_source == "provider":
        if raw.get("provider") != settings.provider:
            raise ProviderFailure("provider_mismatch")
        return
    # Metadata is opt-in. Never use the legacy top-level field as a fallback:
    # absent or ambiguous routing evidence cannot establish a successful pin.
    metadata = raw.get("openrouter_metadata")
    if metadata is None:
        raise ProviderFailure("provider_metadata_missing")
    if not isinstance(metadata, dict) or not isinstance(metadata.get("endpoints"), dict):
        raise ProviderFailure("protocol_invalid_provider_metadata")
    available = metadata["endpoints"].get("available")
    if not isinstance(available, list):
        raise ProviderFailure("protocol_invalid_provider_metadata")
    selected = []
    for endpoint in available:
        if (not isinstance(endpoint, dict) or type(endpoint.get("selected")) is not bool
                or not isinstance(endpoint.get("provider"), str) or not endpoint["provider"]
                or not isinstance(endpoint.get("model"), str) or not endpoint["model"]):
            raise ProviderFailure("protocol_invalid_provider_metadata")
        if endpoint["selected"]:
            selected.append(endpoint)
    if len(selected) != 1:
        raise ProviderFailure("protocol_invalid_provider_metadata")
    if selected[0]["model"] not in (settings.model, *settings.accepted_returned_models):
        raise ProviderFailure("model_mismatch")
    if selected[0]["provider"] != settings.provider:
        raise ProviderFailure("provider_mismatch")
    if "provider" in raw and raw["provider"] != settings.provider:
        raise ProviderFailure("provider_mismatch")


def _parse(raw: Any, payload: dict[str, Any], settings: ProviderSettings, latency: float) -> ProviderResult:
    if not isinstance(raw, dict):
        raise ProviderFailure("protocol_invalid_response")
    if raw.get("model") not in (settings.model, *settings.accepted_returned_models):
        raise ProviderFailure("model_mismatch")
    _validate_provider_identity(raw, settings)
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
        "model": raw["model"],
        "choices": [{"message": safe_message, "finish_reason": _redact_string(finish_reason) if isinstance(finish_reason, str) else None}],
        "usage": usage,
    }
    if "provider" in raw:
        safe_raw["provider"] = settings.provider
    if "openrouter_metadata" in raw:
        safe_raw["openrouter_metadata"] = _sanitized(raw["openrouter_metadata"])
    return ProviderResult(
        reply=reply, raw_response=safe_raw, payload=deepcopy(payload), usage=usage,
        returned_model=raw["model"], returned_provider=settings.provider,
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


def _http_status_evidence(exc: BaseException) -> dict[str, int]:
    """Keep only a valid numeric HTTP status, never exception text or headers."""
    status = None
    if isinstance(exc, httpx.HTTPStatusError):
        status = exc.response.status_code
    elif isinstance(exc, HTTPError):
        status = exc.code
    return {"http_status": status} if type(status) is int and 100 <= status <= 599 else {}


def parse_response(raw: Any, payload: dict[str, Any], settings: ProviderSettings,
                   latency_seconds: float = 0.0) -> ProviderResult:
    """Replay saved safe response evidence without invoking any transport."""
    load_local_credentials()
    _validate_settings_safety(settings)
    if not math.isfinite(latency_seconds) or latency_seconds < 0:
        raise ProviderFailure("invalid_latency_measurement")
    if payload.get("model") != settings.model or payload.get("provider") != _provider_pin(settings):
        raise ProviderFailure("request_pin_mismatch")
    if canonical_json(_sanitized(payload)) != canonical_json(payload):
        raise ProviderFailure("credential_or_header_in_request")
    return _parse(raw, payload, settings, latency_seconds)


class PinnedProvider:
    """Exactly one pinned provider/model; transport must be explicitly injected."""

    def __init__(self, settings: ProviderSettings,
                 transport: Callable[[dict[str, Any]], dict[str, Any] | TransportOutcome | None],
                 sleep: Callable[[float], None] | None = None,
                 before_attempt: Callable[[], None] | None = None):
        load_local_credentials()
        self.settings = settings
        self.transport = transport
        self.sleep = sleep or (lambda seconds: None)
        self.before_attempt = before_attempt

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
            if self.before_attempt is not None:
                # Quota suspension precedes attempt_started. Resuming cannot
                # mistake an undispatched request for an ambiguous sample.
                self.before_attempt()
            emit("attempt_started", attempt, usage={}, latency_seconds=0.0)
            started = time.perf_counter()
            local_accounting: dict[str, str] = {}
            http_evidence: dict[str, int] = {}
            try:
                raw = self.transport(json.loads(encoded))
            except Exception as exc:
                reason = _infrastructure_reason(exc)
                http_evidence = _http_status_evidence(exc)
                latency = _latency(started)
                if latency is None:
                    emit("attempt_failed", attempt, reason="invalid_latency_measurement", infrastructure=False,
                         retryable=False, usage={}, latency_seconds=None, **http_evidence)
                    raise ProviderFailure("invalid_latency_measurement") from None
                if reason is None:
                    # Never include exception text, repr, request headers or body.
                    safe_codes = {"offline_only_live_transport_unavailable", "budget_control_blocked",
                                  "rate_control_blocked", "concurrent_dispatch_forbidden",
                                  "attempt_bound_unavailable", "free_quota_day_changed_before_dispatch"}
                    safe_reason = exc.reason if isinstance(exc, ProviderFailure) and exc.reason in safe_codes else "transport_failure"
                    emit("attempt_failed", attempt, reason=safe_reason, infrastructure=False,
                         retryable=False, usage={}, latency_seconds=latency)
                    raise ProviderFailure(safe_reason) from None
            else:
                if isinstance(raw, TransportOutcome):
                    local_accounting = {"accounting_error": raw.accounting_error}
                    raw = raw.raw_response
                latency = _latency(started)
                if latency is None:
                    emit("attempt_failed", attempt, reason="invalid_latency_measurement", infrastructure=False,
                         retryable=False, usage=_usage(raw.get("usage")) if isinstance(raw, dict) else {},
                         latency_seconds=None, raw_response=_safe_response(raw), **local_accounting)
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
                             request_id=safe_raw.get("id"), **local_accounting)
                        raise
                    emit("attempt_succeeded", attempt, usage=result.usage,
                         latency_seconds=latency, result=result.model_dump(mode="json"), **local_accounting)
                    return result
            emit("attempt_failed", attempt, reason=reason, infrastructure=True,
                 retryable=attempt < 4 and not local_accounting, usage={}, latency_seconds=latency,
                 **local_accounting, **http_evidence)
            if local_accounting:
                raise ProviderFailure("budget_control_blocked")
            if attempt == 4:
                raise ProviderFailure(f"infrastructure_exhausted:{reason}")
            self.sleep(float(2 ** (attempt - 1)))
        raise ProviderFailure("unreachable_attempt_state")
