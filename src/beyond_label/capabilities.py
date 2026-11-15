"""Capability validation and explicitly invoked anonymous public catalog check.

The validator is pure. Its separate fetch helper reads only a fixed public HTTPS
URL, without credentials or environment settings; imports perform no I/O.
Neither function edits requests or authorizes execution. A compatible catalog entry is not proof of live delivery,
account policy, billing, or the cause of an earlier HTTP error. In particular,
false-valued controls remain required capabilities rather than being omitted.

Contracts: https://openrouter.ai/docs/guides/routing/provider-selection and
https://openrouter.ai/api/v1/models/openai/gpt-4.1-mini/endpoints . The model
endpoint prices are per token; request max_price prompt/completion values are
per million tokens. Missing request/image prices are unknown, never zero.
"""
from __future__ import annotations

from collections.abc import Mapping
from decimal import Decimal, InvalidOperation
import json
import math

import httpx


MODEL = "openai/gpt-4.1-mini"
MODEL_NAME = "OpenAI: GPT-4.1 Mini"
PROVIDER = "OpenAI"
PROVIDER_ROUTE = "openai"
REQUIRED_PARAMETERS = ("max_tokens", "parallel_tool_calls", "temperature", "tool_choice", "tools")
_ENDPOINT_NAMES = {"OpenAI | openai/gpt-4.1-mini", "OpenAI | openai/gpt-4.1-mini-2025-04-14"}
_PRICE_CEILINGS = {"prompt": Decimal("0.0000004"), "completion": Decimal("0.0000016"),
                   "request": Decimal("0"), "image": Decimal("0")}
PUBLIC_ENDPOINT_URL = "https://openrouter.ai/api/v1/models/openai/gpt-4.1-mini/endpoints"
MAX_METADATA_BYTES = 1_048_576


def _locked_configuration(config: object) -> bool:
    if not isinstance(config, Mapping):
        return False
    exact = {"model": MODEL, "provider": PROVIDER, "provider_route": PROVIDER_ROUTE,
             "require_parameters": True, "allow_fallbacks": False,
             "parallel_tool_calls": False, "tool_choice": "auto", "reasoning": None}
    if any(key not in config or type(config[key]) is not type(value) or config[key] != value
           for key, value in exact.items()):
        return False
    if (type(config.get("temperature")) not in (int, float) or config["temperature"] != 0
            or type(config.get("max_output_tokens")) is not int or config["max_output_tokens"] != 512):
        return False
    prices = config.get("max_price")
    expected = {"prompt": .4, "completion": 1.6, "request": 0, "image": 0}
    return (isinstance(prices, Mapping) and set(prices) == set(expected)
            and all(type(prices[key]) in (int, float) and prices[key] == value
                    for key, value in expected.items()))


def _price(value: object) -> Decimal | None:
    if type(value) not in (str, int, float):
        return None
    # A catalog numeric value is short. Do not echo arbitrary text or process
    # unbounded numeric strings as diagnostic output.
    try:
        encoded = str(value)
        if len(encoded) > 128:
            return None
        amount = Decimal(encoded)
        return amount if amount.is_finite() and amount >= 0 else None
    except (InvalidOperation, ValueError, OverflowError):
        return None


def _candidate(endpoint: Mapping, index: int) -> dict:
    unknown, blockers = [], []
    status = endpoint.get("status")
    available = type(status) is int and status == 0
    if type(status) is not int:
        unknown.append("status")
    elif not available:
        blockers.append("endpoint_unavailable")

    parameters = endpoint.get("supported_parameters")
    valid_parameters = (isinstance(parameters, list)
                        and all(isinstance(value, str) and value for value in parameters))
    missing = sorted(set(REQUIRED_PARAMETERS) - set(parameters)) if valid_parameters else []
    if not valid_parameters:
        unknown.append("supported_parameters")
    elif missing:
        blockers.append("missing_required_parameters")

    choices = endpoint.get("supports_tool_choice")
    auto = choices.get("auto") if isinstance(choices, Mapping) else None
    if type(auto) is not bool:
        unknown.append("supports_tool_choice.auto")
    elif not auto:
        blockers.append("auto_tool_choice_unsupported")

    output_limit = endpoint.get("max_completion_tokens")
    if type(output_limit) is not int or output_limit <= 0:
        unknown.append("max_completion_tokens")
    elif output_limit < 512:
        blockers.append("output_limit_below_request")

    prices = endpoint.get("pricing")
    price_checks = {}
    for field, ceiling in _PRICE_CEILINGS.items():
        observed = _price(prices.get(field)) if isinstance(prices, Mapping) else None
        within = observed <= ceiling if observed is not None else None
        if observed is None:
            unknown.append("pricing." + field)
        elif not within:
            blockers.append("price_ceiling_exceeded:" + field)
        price_checks[field] = {"observed_usd": str(observed) if observed is not None else None,
                               "ceiling_usd": str(ceiling),
                               "unit": "per_token" if field in {"prompt", "completion"} else "per_unit",
                               "within_ceiling": within}
    if unknown:
        blockers.append("metadata_incomplete")
    return {"endpoint_index": index, "available_status_verified": available,
            "missing_parameters": missing, "unknown_fields": sorted(unknown),
            "price_checks": price_checks, "blockers": sorted(blockers),
            "compatible": not blockers}


def validate_paid_smoke_capabilities(document: object, config: object) -> dict:
    """Return a deterministic fail-closed report; do not modify either input.

    This checks decision requirements even if the first scheduled cell is a
    no-tool readback. It cannot establish that HTTP404 was caused by a missing
    parameter: account filters, transient routing and other unknowns remain.
    Metadata must explicitly support both capabilities and price ceilings.
    The separate spending/account/smoke-only guards remain mandatory.
    """
    report = {"schema_version": 1, "classification": "public_capability_metadata_not_live_delivery",
              "requested_model": MODEL, "requested_provider": PROVIDER,
              "requested_provider_route": PROVIDER_ROUTE,
              "required_parameters": list(REQUIRED_PARAMETERS),
              "compatible": False, "blockers": [], "matching_endpoints": [],
              "execution_authorized": False, "http_404_cause_established": False,
              "request_settings_changed": False}
    if not _locked_configuration(config):
        report["blockers"] = ["invalid_locked_configuration"]
        return report
    data = document.get("data") if isinstance(document, Mapping) else None
    if (not isinstance(data, Mapping) or data.get("id") != MODEL or data.get("name") != MODEL_NAME
            or not isinstance(data.get("endpoints"), list)
            or any(not isinstance(endpoint, Mapping) for endpoint in data["endpoints"])):
        report["blockers"] = ["invalid_endpoint_document"]
        return report
    for index, endpoint in enumerate(data["endpoints"]):
        if (endpoint.get("provider_name") == PROVIDER and endpoint.get("tag") == PROVIDER_ROUTE
                and endpoint.get("model_id") == MODEL and endpoint.get("model_name") == MODEL_NAME
                and isinstance(endpoint.get("name"), str) and endpoint["name"] in _ENDPOINT_NAMES):
            report["matching_endpoints"].append(_candidate(endpoint, index))
    report["compatible"] = any(endpoint["compatible"] for endpoint in report["matching_endpoints"])
    if not report["matching_endpoints"]:
        report["blockers"] = ["pinned_endpoint_not_listed"]
    elif not report["compatible"]:
        report["blockers"] = ["no_verified_compatible_endpoint"]
    return report


def _unique_json_object(pairs: list[tuple[str, object]]) -> dict:
    result = {}
    for key, value in pairs:
        if key in result:
            raise ValueError("ambiguous_public_metadata")
        result[key] = value
    return result


def _reject_constant(value: str) -> None:
    raise ValueError("nonfinite_public_metadata")


def _finite_float(value: str) -> float:
    number = float(value)
    if not math.isfinite(number):
        raise ValueError("nonfinite_public_metadata")
    return number


def check_paid_smoke_capabilities(config: object, *, transport: httpx.BaseTransport | None = None,
                                  timeout_seconds: float = 20.0) -> dict:
    """Fetch one bounded public document anonymously and return safe checks.

    No caller-selected URL, credential loader, proxy/environment configuration,
    authenticated headers, redirects, inference or raw response logging. All
    failures return fixed classifications; exception/response text is discarded.
    An injected MockTransport supports offline tests of the actual HTTP seam.
    """
    report = validate_paid_smoke_capabilities(None, config)
    report["fetch"] = {"source": PUBLIC_ENDPOINT_URL, "status": "not_requested",
                       "http_status": None, "credentials_used": False}
    if report["blockers"] == ["invalid_locked_configuration"]:
        return report

    def fail(reason: str) -> dict:
        report["blockers"] = ["public_metadata_unavailable"]
        report["fetch"]["status"] = reason
        return report

    if type(timeout_seconds) not in (int, float) or not 0 < timeout_seconds <= 60:
        return fail("invalid_timeout")
    content = bytearray()
    try:
        with httpx.Client(transport=transport, timeout=timeout_seconds, verify=True,
                          follow_redirects=False, trust_env=False) as client:
            with client.stream("GET", PUBLIC_ENDPOINT_URL) as response:
                status = response.status_code
                report["fetch"]["http_status"] = status if type(status) is int and 100 <= status <= 599 else None
                if status != 200:
                    return fail("http_error")
                for chunk in response.iter_bytes(chunk_size=65536):
                    if len(content) + len(chunk) > MAX_METADATA_BYTES:
                        return fail("response_too_large")
                    content.extend(chunk)
    except Exception:
        return fail("transport_error")
    try:
        document = json.loads(content, object_pairs_hook=_unique_json_object,
                              parse_constant=_reject_constant, parse_float=_finite_float)
    except (ValueError, TypeError, RecursionError, OverflowError):
        return fail("invalid_json")
    result = validate_paid_smoke_capabilities(document, config)
    result["fetch"] = {**report["fetch"], "status": "received"}
    return result
