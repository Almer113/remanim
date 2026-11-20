"""Review after Phase 5: server and engine fixes that need no rendering."""

import asyncio

import pytest
from aiohttp import web
from aiohttp.test_utils import make_mocked_request

from studio.server import app


async def _ok(req):
    return web.Response(text="ok")


def _call(path, host, headers=None, cookies=None):
    h = {"Host": host, **(headers or {})}
    if cookies:
        h["Cookie"] = "; ".join(f"{k}={v}" for k, v in cookies.items())
    req = make_mocked_request("GET", path, headers=h)
    return asyncio.run(app.local_only(req, _ok))


@pytest.fixture
def tailnet(monkeypatch):
    monkeypatch.setattr(app, "TRUSTED_HOSTS", {"box.tail.ts.net"})
    monkeypatch.setattr(app, "ACCESS_TOKEN", "s3cret-token")


def test_local_host_needs_no_token(tailnet):
    assert _call("/api/files", "127.0.0.1:8770").text == "ok"


def test_a_proxied_request_is_never_local(tailnet):
    # review after Phase 6: through `tailscale serve` a peer could send
    # "Host: localhost"; a proxy's headers mark it as another machine
    for h in ({"X-Forwarded-For": "100.64.0.7"}, {"Tailscale-User-Login": "x@y"}, {"Forwarded": "for=1.2.3.4"}):
        with pytest.raises(web.HTTPForbidden) as e:
            _call("/api/files", "localhost:8770", headers=h)
        assert "token" in e.value.text
    assert _call("/api/files", "localhost:8770", headers={"X-Forwarded-For": "100.64.0.7"},
                 cookies={app.TOKEN_COOKIE: "s3cret-token"}).text == "ok"
    ask = {"type": "claude.ask", "prompt": "hi"}
    assert app.gate(ask, "localhost:8770", via_proxy=True)["available"] is False
    assert app.gate({"type": "export.reveal"}, "127.0.0.1:8770", via_proxy=True)["type"] == "error"


def test_tailnet_host_without_token_is_refused(tailnet):
    with pytest.raises(web.HTTPForbidden) as e:
        _call("/api/files", "box.tail.ts.net:8770")
    assert "token" in e.value.text
    with pytest.raises(web.HTTPForbidden):
        _call("/api/files", "box.tail.ts.net:8770", cookies={app.TOKEN_COOKIE: "wrong"})


def test_tailnet_token_link_sets_cookie_and_drops_it_from_the_url(tailnet):
    with pytest.raises(web.HTTPFound) as e:
        _call("/?token=s3cret-token&x=1", "box.tail.ts.net:8770")
    assert "token" not in str(e.value.location) and "x=1" in str(e.value.location)
    assert e.value.cookies[app.TOKEN_COOKIE].value == "s3cret-token"
    assert _call("/api/files", "box.tail.ts.net:8770", cookies={app.TOKEN_COOKIE: "s3cret-token"}).text == "ok"


def test_no_token_configured_means_no_remote_access(monkeypatch):
    monkeypatch.setattr(app, "TRUSTED_HOSTS", {"box.tail.ts.net"})
    monkeypatch.setattr(app, "ACCESS_TOKEN", "")
    with pytest.raises(web.HTTPForbidden):
        _call("/?token=", "box.tail.ts.net:8770")


def test_origin_must_be_the_request_host(tailnet):
    # a page on plain localhost may not drive the tailnet name, nor the reverse
    assert not app._same_server("http://localhost:8770", "box.tail.ts.net:8770")
    assert not app._same_server("https://box.tail.ts.net:8770", "127.0.0.1:8770")
    assert app._same_server("https://box.tail.ts.net:8770", "box.tail.ts.net:8770")
    assert app._same_server("http://localhost:8770", "127.0.0.1:8770")


def test_vite_origin_only_with_dev_flag():
    assert app.DEV_ORIGINS == set()
    with pytest.raises(web.HTTPForbidden):
        _call("/api/files", "127.0.0.1:8770", headers={"Origin": "http://localhost:5173"})


def test_latex_detail_drops_special_markers(tmp_path):
    from studio.server.engine.runtime import _latex_detail
    log = tmp_path / "x.log"
    log.write_text("! Undefined control sequence.\n"
                   "<argument> ...\\special {dvisvgm:raw <g id='unique000'>}a^2 + \\badcommand\n",
                   encoding="utf-8")
    got = _latex_detail(f"error converting to dvi. See log file: {log}")
    assert "special" not in got and "badcommand" in got


def test_matching_transform_key_map_given_positionally():
    # in a fresh process: the engine's patches are global
    import subprocess
    import sys
    code = "\n".join([
        "from studio.server.engine import runtime; runtime.install()",
        "from manim import Square, Circle, TransformMatchingShapes",
        "t = TransformMatchingShapes(Square(), Circle(), False, False, {'a': 'b'})",
        "print(t._studio_key_map)"])
    out = subprocess.run([sys.executable, "-c", code], capture_output=True, text=True, timeout=120,
                         cwd=str(app.ROOT))
    assert out.returncode == 0, out.stderr[-800:]
    assert "{'a': 'b'}" in out.stdout


def test_latex_missing_is_named(tmp_path, monkeypatch):
    import shutil
    from studio.server.engine.runtime import _latex_detail
    monkeypatch.setattr(shutil, "which", lambda name: None)
    got = _latex_detail(f"latex error converting to dvi. See log file: {tmp_path / 'never.log'}")
    assert got and "isn't installed" in got
