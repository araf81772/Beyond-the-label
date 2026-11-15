"""Explicit, separately gated OpenRouter HTTP transports; imports send nothing.

Only the caller enables execution, after its authorization, account preflight,
budget/rate guards and protocol gates. This adapter never retries. The fixed
HTTPS origin, no redirects, explicit price caps, text-only messages,
and local function-tool allowlist prevent unintended routes or billed server plugins
from being introduced through a request. No credentials or HTTP headers are
logged, persisted, or included in raised errors.

Official contracts: https://openrouter.ai/docs/guides/routing/provider-selection
and https://openrouter.ai/docs/api/api-reference/api-keys/get-current-api-key.
Max-price prompt/completion units are USD per million tokens; request and image
are per-unit caps. Zero is exact in all four units. These routing restrictions
do not replace the caller's independent authorization and account preflight.
The free adapter retains its four zero caps. The separate paid adapter pins
only the explicitly authorized GPT-4.1 Mini / OpenAI smoke configuration.
"""
from __future__ import annotations

import json
import math
import os
import re
from typing import Any

import httpx

from .environment import load_local_credentials
from .provider import HTTP_DIAGNOSTICS, ProviderFailure, _sanitized, canonical_json


_CHAT_URL = "https://openrouter.ai/api/v1/chat/completions"
_KEY_URL = "https://openrouter.ai/api/v1/key"
_MODEL = re.compile(r"[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+:free\Z")
_ROUTE = re.compile(r"[a-z0-9][a-z0-9._/-]*\Z")
_PAYLOAD_FIELDS = {"model", "provider", "messages", "max_tokens", "parallel_tool_calls",
                   "temperature", "reasoning", "tools", "tool_choice"}
_MESSAGE_FIELDS = {"role", "content", "tool_calls", "tool_call_id", "name"}
_PRICE_FIELDS = {"prompt", "completion", "request", "image"}
PAID_MODEL = "openai/gpt-4.1-mini"
PAID_PROVIDER_ROUTE = "openai"
PAID_MAX_PRICE = {"prompt": 0.40, "completion": 1.60, "request": 0, "image": 0}
_MAX_ERROR_JSON_BYTES = 32_768
# Exact prefixes verified in primary OpenRouter examples. Never store a prefix
# match's free-form suffix, model IDs, upstream metadata, or original message.
# https://openrouter.ai/blog/tutorials/structured-output-llm/
# https://openrouter.ai/blog/insights/open-weight-vs-closed-weight-models/
# https://openrouter.ai/blog/self-hosted-llm-vs-api/
_ERROR_PREFIXES = (
    ("No endpoints found that can handle the requested parameters.", "unsupported_parameters"),
    ("No endpoints found matching your data policy (Zero data retention).", "data_policy"),
    ("No endpoints found that satisfy the max price for this request", "price_filter"),
    ("No endpoints found supporting your data region.", "data_region"),
)


def _timeout(value: Any) -> float:
    if type(value) not in (int, float):
        raise ProviderFailure("invalid_http_timeout")
    try:
        valid = math.isfinite(value) and value > 0
    except (OverflowError, ValueError):
        valid = False
    if not valid:
        raise ProviderFailure("invalid_http_timeout")
    return float(value)


def _credential() -> str:
    failed = False
    try:
        load_local_credentials()
    except Exception:
        failed = True
    if failed:
        raise ProviderFailure("openrouter_credential_unavailable")
    value = os.environ.get("OPENROUTER_API_KEY", "")
    if not value or any(ord(char) < 33 or ord(char) > 126 for char in value):
        raise ProviderFailure("openrouter_credential_unavailable")
    return value


def _http_error(status: int, method: str, url: str, *,
                diagnostics: dict[str, int | str] | None = None) -> httpx.HTTPStatusError:
    # Construct fresh objects: original requests contain authorization headers,
    # and error response bodies or redirect locations can contain private data.
    safe_request = httpx.Request(method, url)
    safe_response = httpx.Response(status, request=safe_request)
    error = httpx.HTTPStatusError(f"openrouter_http_{status}", request=safe_request, response=safe_response)
    category = diagnostics.get("http_diagnostic") if isinstance(diagnostics, dict) else None
    error._btl_http_diagnostic = category if type(category) is str and category in HTTP_DIAGNOSTICS else "unknown"
    code = diagnostics.get("api_error_code") if isinstance(diagnostics, dict) else None
    if type(code) is int and 400 <= code <= 599:
        error._btl_api_error_code = code
    return error


def _unique_object(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    result = {}
    for key, value in pairs:
        if key in result:
            raise ValueError("duplicate_json_key")
        result[key] = value
    return result


def _reject_constant(value: str) -> Any:
    raise ValueError("invalid_json_constant")


def _finite_float(value: str) -> float:
    parsed = float(value)
    if not math.isfinite(parsed):
        raise ValueError("invalid_json_number")
    return parsed


def _error_diagnostics(content: bytes) -> dict[str, int | str]:
    """Classify a bounded error envelope without retaining any provider text.

    Malformed, oversized, unknown, or future messages stay unknown. The label
    reports a documented provider message class, not an independent diagnosis
    of the underlying cause. Numeric error codes remain distinct from status.
    """
    result: dict[str, int | str] = {"http_diagnostic": "unknown"}
    if not content or len(content) > _MAX_ERROR_JSON_BYTES:
        return result
    try:
        raw = json.loads(content, parse_constant=_reject_constant, parse_float=_finite_float,
                         object_pairs_hook=_unique_object)
    except (ValueError, UnicodeError, TypeError, RecursionError):
        return result
    error = raw.get("error") if isinstance(raw, dict) else None
    if not isinstance(error, dict):
        return result
    code = error.get("code")
    if type(code) is int and 400 <= code <= 599:
        result["api_error_code"] = code
    message = error.get("message")
    if isinstance(message, str):
        for prefix, category in _ERROR_PREFIXES:
            if message.startswith(prefix):
                result["http_diagnostic"] = category
                break
    return result


def _request_json(method: str, url: str, *, payload: dict[str, Any] | None,
                  timeout_seconds: float, transport: httpx.BaseTransport | None) -> dict[str, Any] | None:
    key = _credential()
    # Check again after loading the key, so exact secret echoes that did not
    # match generic token patterns are rejected before any dispatch.
    if payload is not None and canonical_json(_sanitized(payload)) != canonical_json(payload):
        raise ProviderFailure("credential_or_header_in_request")
    headers = {"Authorization": "Bearer " + key, "Content-Type": "application/json"}
    if method == "POST":
        headers["X-OpenRouter-Metadata"] = "enabled"
    failure = None
    response = None
    try:
        with httpx.Client(transport=transport, timeout=timeout_seconds, verify=True,
                          follow_redirects=False, trust_env=False) as client:
            response = client.request(method, url, headers=headers,
                                      content=canonical_json(payload).encode("utf-8") if payload is not None else None)
    except httpx.TimeoutException:
        failure = "timeout"
    except httpx.TransportError:
        failure = "connection"
    except Exception:
        failure = "other"
    # Raise outside the except suite: even __context__ must not retain a
    # caught HTTP exception whose request could contain a credential.
    if failure == "timeout":
        raise httpx.TimeoutException("openrouter_timeout")
    if failure == "connection":
        raise httpx.TransportError("openrouter_connection_error")
    if failure is not None or response is None:
        raise ProviderFailure("openrouter_transport_failure")
    if not 200 <= response.status_code < 300:
        raise _http_error(response.status_code, method, url,
                          diagnostics=_error_diagnostics(response.content))
    if not response.content:
        return None
    malformed = False
    raw = None
    try:
        raw = json.loads(response.content, parse_constant=_reject_constant, parse_float=_finite_float,
                         object_pairs_hook=_unique_object)
    except (ValueError, UnicodeError, TypeError, RecursionError):
        malformed = True
    if malformed or not isinstance(raw, dict):
        raise ProviderFailure("openrouter_invalid_json")
    if raw.get("error") is not None:
        error = raw["error"]
        code = error.get("code") if isinstance(error, dict) else None
        if type(code) is int and 400 <= code <= 599:
            raise _http_error(code, method, url, diagnostics=_error_diagnostics(response.content))
        raise ProviderFailure("openrouter_api_error")
    # Successful completion evidence remains intact for PinnedProvider's
    # existing sanitization, action classification and immutable raw logging.
    return raw


def _valid_messages(messages: Any) -> bool:
    if not isinstance(messages, list) or not messages:
        return False
    for message in messages:
        if (not isinstance(message, dict) or set(message) - _MESSAGE_FIELDS
                or not isinstance(message.get("role"), str)
                or message["role"] not in {"system", "user", "assistant", "tool"}
                or not isinstance(message.get("content"), (str, type(None)))):
            return False
        for field in ("name", "tool_call_id"):
            if field in message and not isinstance(message[field], str):
                return False
        if "tool_calls" in message:
            calls = message["tool_calls"]
            if not isinstance(calls, list):
                return False
            for call in calls:
                if (not isinstance(call, dict) or set(call) != {"id", "type", "function"}
                        or call.get("type") != "function" or not isinstance(call.get("id"), str)):
                    return False
                function = call["function"]
                if (not isinstance(function, dict) or set(function) != {"name", "arguments"}
                        or not isinstance(function["name"], str)
                        or function["name"] not in {"inspect", "commit", "read_handoff"}
                        or not isinstance(function["arguments"], str)):
                    return False
    return True


def _valid_parallel_control(payload: dict[str, Any]) -> bool:
    # No-tool readback must omit the inapplicable control, while every tool
    # decision/continuation still explicitly disables parallel calls.
    if "tools" in payload:
        return payload.get("parallel_tool_calls") is False
    return "parallel_tool_calls" not in payload


def _valid_tools(payload: dict[str, Any]) -> bool:
    if "tools" not in payload:
        return "tool_choice" not in payload
    tools = payload["tools"]
    if not isinstance(tools, list) or not tools or payload.get("tool_choice") != "auto":
        return False
    names = []
    for tool in tools:
        if not isinstance(tool, dict) or set(tool) != {"type", "function"} or tool["type"] != "function":
            return False
        function = tool["function"]
        if (not isinstance(function, dict) or set(function) - {"name", "description", "strict", "parameters"}
                or not isinstance(function.get("name"), str) or function["name"] not in {"inspect", "commit"}
                or not isinstance(function.get("parameters"), dict)):
            return False
        if "description" in function and not isinstance(function["description"], str):
            return False
        if "strict" in function and type(function["strict"]) is not bool:
            return False
        names.append(function["name"])
    return len(set(names)) == len(names)


class OpenRouterFreeTransport:
    """One HTTP attempt for an exact free model and provider route.

    The default constructor is inert. Supplying an httpx.MockTransport is the
    supported test seam; no caller-supplied URL, headers, client or TLS settings
    can redirect credentials. Caller owns budget/rate controls and retries.
    """

    def __init__(self, model: str, provider_route: str, *, timeout_seconds: float = 60.0,
                 transport: httpx.BaseTransport | None = None):
        if not isinstance(model, str) or _MODEL.fullmatch(model) is None:
            raise ProviderFailure("free_model_required")
        if not isinstance(provider_route, str) or _ROUTE.fullmatch(provider_route) is None:
            raise ProviderFailure("invalid_provider_route")
        self.model, self.provider_route = model, provider_route
        self.timeout_seconds = _timeout(timeout_seconds)
        self._transport = transport

    def __call__(self, payload: dict[str, Any]) -> dict[str, Any] | None:
        if not isinstance(payload, dict) or set(payload) - _PAYLOAD_FIELDS:
            raise ProviderFailure("free_request_field_forbidden")
        if (payload.get("model") != self.model or not isinstance(payload.get("model"), str)
                or _MODEL.fullmatch(payload["model"]) is None):
            raise ProviderFailure("free_request_model_mismatch")
        pin = payload.get("provider")
        valid_pin = (isinstance(pin, dict) and set(pin) == {"only", "allow_fallbacks", "require_parameters", "max_price"}
                     and pin.get("only") == [self.provider_route] and pin.get("allow_fallbacks") is False
                     and pin.get("require_parameters") is True)
        prices = pin.get("max_price") if isinstance(pin, dict) else None
        if (not valid_pin or not isinstance(prices, dict) or set(prices) != _PRICE_FIELDS
                or any(type(value) not in (int, float) or value != 0 for value in prices.values())):
            raise ProviderFailure("free_request_provider_pin_invalid")
        if (not _valid_parallel_control(payload)
                or type(payload.get("max_tokens")) is not int or payload["max_tokens"] <= 0):
            raise ProviderFailure("free_request_parameters_invalid")
        temperature = payload.get("temperature", 0)
        if type(temperature) not in (int, float) or not 0 <= temperature <= 2:
            raise ProviderFailure("free_request_parameters_invalid")
        if "reasoning" in payload:
            reasoning = payload["reasoning"]
            if not isinstance(reasoning, dict) or set(reasoning) - {"effort", "max_tokens", "exclude", "enabled"}:
                raise ProviderFailure("free_request_parameters_invalid")
            if any(type(reasoning[key]) is not bool for key in ("exclude", "enabled") if key in reasoning):
                raise ProviderFailure("free_request_parameters_invalid")
            if "max_tokens" in reasoning and (type(reasoning["max_tokens"]) is not int or reasoning["max_tokens"] <= 0):
                raise ProviderFailure("free_request_parameters_invalid")
            if "effort" in reasoning and (not isinstance(reasoning["effort"], str)
                    or reasoning["effort"] not in {"none", "minimal", "low", "medium", "high", "xhigh"}):
                raise ProviderFailure("free_request_parameters_invalid")
        if not _valid_messages(payload.get("messages")) or not _valid_tools(payload):
            raise ProviderFailure("free_request_content_forbidden")
        canonical_json(payload)
        return _request_json("POST", _CHAT_URL, payload=payload, timeout_seconds=self.timeout_seconds, transport=self._transport)


class OpenRouterPaidTransport:
    """One strictly pinned paid smoke HTTP attempt; caller owns durable limits.

    Construction is inert and does not establish spending authorization. The
    execution harness must enforce the approved cumulative dollar/attempt caps,
    account hard limit and smoke-only stage before each dispatch. This adapter
    performs no retries, fallbacks, price inference or model substitution.
    """

    def __init__(self, model: str, provider_route: str, *, timeout_seconds: float = 60.0,
                 transport: httpx.BaseTransport | None = None):
        if model != PAID_MODEL or provider_route != PAID_PROVIDER_ROUTE:
            raise ProviderFailure("paid_transport_pin_invalid")
        self.model, self.provider_route = model, provider_route
        self.timeout_seconds = _timeout(timeout_seconds)
        self._transport = transport

    def __call__(self, payload: dict[str, Any]) -> dict[str, Any] | None:
        if not isinstance(payload, dict) or set(payload) - (_PAYLOAD_FIELDS - {"reasoning"}):
            raise ProviderFailure("paid_request_field_forbidden")
        if payload.get("model") != self.model:
            raise ProviderFailure("paid_request_model_mismatch")
        pin = payload.get("provider")
        valid_pin = (isinstance(pin, dict) and set(pin) == {"only", "allow_fallbacks", "require_parameters", "max_price"}
                     and pin.get("only") == [self.provider_route] and pin.get("allow_fallbacks") is False
                     and pin.get("require_parameters") is True)
        prices = pin.get("max_price") if isinstance(pin, dict) else None
        if (not valid_pin or not isinstance(prices, dict) or set(prices) != _PRICE_FIELDS
                or any(type(value) not in (int, float) or value != PAID_MAX_PRICE[key]
                       for key, value in prices.items())):
            raise ProviderFailure("paid_request_provider_pin_invalid")
        if (not _valid_parallel_control(payload)
                or type(payload.get("max_tokens")) is not int or payload["max_tokens"] != 512
                or type(payload.get("temperature")) not in (int, float) or payload["temperature"] != 0):
            raise ProviderFailure("paid_request_parameters_invalid")
        if not _valid_messages(payload.get("messages")) or not _valid_tools(payload):
            raise ProviderFailure("paid_request_content_forbidden")
        canonical_json(payload)
        return _request_json("POST", _CHAT_URL, payload=payload, timeout_seconds=self.timeout_seconds, transport=self._transport)


def paid_account_preflight(*, transport: httpx.BaseTransport | None = None,
                           timeout_seconds: float = 60.0) -> dict[str, Any]:
    """Read current-key USD limits, never infer authorization or account funds.

    No key name, identifier, headers, credential or arbitrary response content
    leaves this function. Unlimited/exhausted/resetting limits are reported as
    evidence for the caller to reject; this function does not enable execution.
    Missing optional budget fields are None, not invented absence of limits.
    """
    raw = _request_json("GET", _KEY_URL, payload=None, timeout_seconds=_timeout(timeout_seconds), transport=transport)
    invalid = "openrouter_paid_account_metadata_invalid"
    data = raw.get("data") if isinstance(raw, dict) else None
    if not isinstance(data, dict) or not {"limit", "limit_remaining", "usage", "limit_reset"} <= set(data):
        raise ProviderFailure(invalid)

    def number(value: Any, *, nullable: bool = False, nonnegative: bool = True) -> int | float | None:
        if value is None and nullable:
            return None
        try:
            valid = (type(value) in (int, float) and math.isfinite(value)
                     and (not nonnegative or value >= 0))
        except (OverflowError, ValueError):
            valid = False
        if not valid:
            raise ProviderFailure(invalid)
        return value

    def reset(value: Any) -> str | None:
        if value is not None and (not isinstance(value, str) or value not in {"daily", "weekly", "monthly"}):
            raise ProviderFailure(invalid)
        return value

    def budget(value: Any) -> dict[str, Any]:
        fields = {"scope", "limit_usd", "spend_usd", "remaining_usd", "reset_interval", "include_byok"}
        if (not isinstance(value, dict) or not fields <= set(value)
                or not isinstance(value["scope"], str)
                or value["scope"] not in {"workspace_default_member", "workspace_default_key", "member", "api_key", "workspace", "key_limit"}
                or type(value["include_byok"]) is not bool):
            raise ProviderFailure(invalid)
        return {"scope": value["scope"], "limit_usd": number(value["limit_usd"]),
                "spend_usd": number(value["spend_usd"]),
                "remaining_usd": number(value["remaining_usd"], nonnegative=False),
                "reset_interval": reset(value["reset_interval"]), "include_byok": value["include_byok"]}

    limit = number(data["limit"], nullable=True)
    remaining = number(data["limit_remaining"], nullable=True, nonnegative=False)
    if (limit is None) != (remaining is None) or (limit is not None and remaining > limit):
        raise ProviderFailure(invalid)
    include_byok = data.get("include_byok_in_limit")
    if include_byok is not None and type(include_byok) is not bool:
        raise ProviderFailure(invalid)
    budgets = data.get("budgets")
    if budgets is not None and not isinstance(budgets, list):
        raise ProviderFailure(invalid)
    effective = data.get("effective_budget")
    return {"key_hard_limit_usd": limit, "key_limit_remaining_usd": remaining,
            "key_usage_usd": number(data["usage"]), "key_limit_reset": reset(data["limit_reset"]),
            "include_byok_in_limit": include_byok,
            "budgets": None if budgets is None else [budget(value) for value in budgets],
            "effective_budget": None if effective is None else budget(effective)}


def free_account_preflight(*, transport: httpx.BaseTransport | None = None,
                           timeout_seconds: float = 60.0) -> dict[str, Any]:
    """Read only the current key; return minimal validated execution evidence.

    ``is_free_tier`` does not determine request allowance. The explicit daily
    counts are required. A null key limit is unlimited, never a zero hard cap.
    No account or key settings are changed, and no model request is performed.
    """
    raw = _request_json("GET", _KEY_URL, payload=None, timeout_seconds=_timeout(timeout_seconds), transport=transport)
    data = raw.get("data") if isinstance(raw, dict) else None
    if not isinstance(data, dict) or "limit" not in data:
        raise ProviderFailure("invalid_free_account_evidence")
    limit = data["limit"]
    if limit is not None:
        if type(limit) not in (int, float) or limit < 0 or (type(limit) is float and not math.isfinite(limit)):
            raise ProviderFailure("invalid_free_account_evidence")
    counts = data.get("free_model_daily_requests")
    if (not isinstance(counts, dict) or not {"used", "limit", "remaining"}.issubset(counts)
            or any(type(counts[key]) is not int or counts[key] < 0 for key in ("used", "limit", "remaining"))
            or counts["used"] + counts["remaining"] != counts["limit"]):
        raise ProviderFailure("invalid_free_account_evidence")
    return {"zero_hard_limit": limit is not None and limit == 0,
            "free_model_daily_requests": {key: counts[key] for key in ("used", "limit", "remaining")}}
