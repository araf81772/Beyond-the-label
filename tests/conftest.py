"""Every experiment test is offline, including transport tests using local mocks."""
import socket
import pytest
from beyond_label import environment


@pytest.fixture(scope="session", autouse=True)
def isolate_session_credentials(tmp_path_factory):
    """Protect collection-independent module/session fixtures as well as tests."""
    with pytest.MonkeyPatch.context() as patch:
        patch.setattr(environment, "ENV_PATH", tmp_path_factory.mktemp("credentials") / ".env")
        for name in environment.CREDENTIAL_NAMES:
            patch.delenv(name, raising=False)
        yield


@pytest.fixture(autouse=True)
def isolate_credentials(monkeypatch, tmp_path, isolate_session_credentials):
    """Tests use temporary fixtures, never the user's real local key."""
    monkeypatch.setattr(environment, "ENV_PATH", tmp_path / ".env")
    for name in environment.CREDENTIAL_NAMES:
        monkeypatch.delenv(name, raising=False)


@pytest.fixture(autouse=True)
def prohibit_network(monkeypatch):
    def forbidden(*args, **kwargs):
        raise AssertionError("Network access is forbidden in the offline test suite")
    monkeypatch.setattr(socket.socket, "connect", forbidden)
    monkeypatch.setattr(socket, "create_connection", forbidden)
