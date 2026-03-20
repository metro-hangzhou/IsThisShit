from __future__ import annotations

from qq_data_cli import app as cli_app
from qq_data_integrations.napcat.models import NapCatLoginInfo, NapCatLoginStatus
from qq_data_integrations.napcat.settings import NapCatSettings


class _BootstrapResult:
    ready = True
    attempted_start = False
    attempted_configure = False
    message = ""


class _Bootstrapper:
    def __init__(self, *_args, **_kwargs) -> None:
        pass

    def ensure_endpoint(self, _endpoint: str) -> _BootstrapResult:
        return _BootstrapResult()


class _WebUiClient:
    def __init__(self, *_args, **_kwargs) -> None:
        self.closed = False

    def close(self) -> None:
        self.closed = True


class _QuickLoginService:
    def __init__(self, _client) -> None:
        self.quick_calls: list[str | None] = []
        self.qr_calls = 0
        self.status_checks = 0

    def check_status(self) -> NapCatLoginStatus:
        self.status_checks += 1
        return NapCatLoginStatus()

    def get_login_info(self) -> NapCatLoginInfo:
        return NapCatLoginInfo(uin="3956020260", nick="wiki", online=True)

    def get_quick_login_candidates(self):
        return []

    def get_default_quick_login_uin(self) -> str | None:
        return "3956020260"

    def try_quick_login(self, *, preferred_uin=None, **_kwargs):
        self.quick_calls.append(preferred_uin)
        return NapCatLoginInfo(uin="3956020260", nick="wiki", online=True)

    def login_until_success(self, **_kwargs):
        self.qr_calls += 1
        return NapCatLoginInfo(uin="3956020260", nick="wiki", online=True)


class _QrOnlyService(_QuickLoginService):
    def try_quick_login(self, *, preferred_uin=None, **_kwargs):
        self.quick_calls.append(preferred_uin)
        return None


class _AlreadyLoggedInService(_QuickLoginService):
    def check_status(self) -> NapCatLoginStatus:
        self.status_checks += 1
        return NapCatLoginStatus(is_login=True)


def _patch_login_stack(monkeypatch, service_cls) -> None:
    settings = NapCatSettings.from_env()
    monkeypatch.setattr(NapCatSettings, "from_env", classmethod(lambda cls: settings))
    import qq_data_integrations.napcat.bootstrap as bootstrap_module
    import qq_data_integrations.napcat.login as login_module
    import qq_data_integrations.napcat.webui_client as webui_module

    monkeypatch.setattr(bootstrap_module, "NapCatBootstrapper", _Bootstrapper)
    monkeypatch.setattr(login_module, "NapCatQrLoginService", service_cls)
    monkeypatch.setattr(webui_module, "NapCatWebUiClient", _WebUiClient)


def test_cli_login_prefers_quick_login(monkeypatch, capsys) -> None:
    _patch_login_stack(monkeypatch, _QuickLoginService)

    cli_app.login(timeout=10.0, poll=1.0, refresh=False, no_quick=False, quick_uin=None)

    output = capsys.readouterr().out
    assert "QQ quick login succeeded." in output
    assert "uin=3956020260" in output
    assert "QQ login succeeded." not in output


def test_cli_login_can_skip_quick_login(monkeypatch, capsys) -> None:
    _patch_login_stack(monkeypatch, _QrOnlyService)

    cli_app.login(timeout=10.0, poll=1.0, refresh=False, no_quick=True, quick_uin=None)

    output = capsys.readouterr().out
    assert "QQ quick login succeeded." not in output
    assert "QQ login succeeded." in output


def test_cli_login_reports_existing_session_without_claiming_quick_login(monkeypatch, capsys) -> None:
    _patch_login_stack(monkeypatch, _AlreadyLoggedInService)

    cli_app.login(timeout=10.0, poll=1.0, refresh=False, no_quick=False, quick_uin=None)

    output = capsys.readouterr().out
    assert "QQ already logged in." in output
    assert "QQ quick login succeeded." not in output
    assert "quick_login_candidate=" not in output
