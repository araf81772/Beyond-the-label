"""Free-route serialization fixtures; no account or inference requests."""
import pytest

from beyond_label.provider import ProviderFailure, ProviderSettings, serialize_request
from beyond_label.schemas import Request


def settings(**changes):
    values = dict(model="vendor/fixed:free", provider="Vendor", provider_route="vendor",
                  provider_identity_source="openrouter_metadata", require_parameters=True,
                  free_only=True, reasoning={"enabled": False})
    values.update(changes)
    return ProviderSettings(**values)


def test_free_price_caps_are_in_the_logged_payload():
    payload = serialize_request(Request(messages=[]), settings())
    assert payload["provider"] == {"only": ["vendor"], "allow_fallbacks": False,
        "require_parameters": True, "max_price": {"prompt": 0, "completion": 0, "request": 0, "image": 0}}


@pytest.mark.parametrize("changes", [{"model": "vendor/paid"}, {"model": "openrouter/auto:free"},
    {"provider_route": None}, {"require_parameters": False}, {"provider_identity_source": "provider"}])
def test_free_route_requires_fixed_free_model_and_strict_identity(changes):
    with pytest.raises(ProviderFailure, match="invalid_free_provider_settings"):
        serialize_request(Request(messages=[]), settings(**changes))
