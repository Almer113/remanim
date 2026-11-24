"""The permanent deployment: install files, the token page, the kept token,
the hub contract's status line. No server is started."""

import json
import subprocess
import sys

import pytest
from aiohttp import web

from studio.server import app
from studio.server.__main__ import access_token
from studio.tests.unit.test_review_phase5_server import _call, tailnet  # noqa: F401 (fixture)


@pytest.mark.parametrize("path", ["/manifest.webmanifest", "/favicon.ico", "/icons/icon-192.png"])
def test_install_files_need_no_token(tailnet, path):  # noqa: F811
    # a browser fetches the manifest without cookies: installing must not need the token
    assert _call(path, "box.tail.ts.net:8770").text == "ok"


def test_install_files_still_need_a_known_host(tailnet):  # noqa: F811
    with pytest.raises(web.HTTPForbidden):
        _call("/manifest.webmanifest", "evil.example:8770")


def test_everything_else_still_needs_the_token(tailnet):  # noqa: F811
    for path in ("/api/files", "/icons/../api/files", "/frame?f=1", "/api/health"):
        with pytest.raises(web.HTTPForbidden):
            _call(path, "box.tail.ts.net:8770")
    page = _call("/", "box.tail.ts.net:8770")
    assert page.status == 403 and 'name="token"' in page.text and "s3cret" not in page.text


def test_kept_token_survives_a_restart(tmp_path):
    f = tmp_path / "data" / "access_token"
    a = access_token(str(f))
    assert len(a) >= 24 and f.read_text(encoding="ascii") == a
    assert access_token(str(f)) == a  # the next start reads the same token
    f.write_bytes(b"\xef\xbb\xbfMyOwn-Token9\r\n")  # one of your own, saved by Notepad with a BOM
    assert access_token(str(f)) == "MyOwn-Token9"
    f.write_text("   \n", encoding="ascii")  # empty: a new one
    assert len(access_token(str(f))) >= 24
    assert access_token(None) != access_token(None)


@pytest.mark.parametrize("bad", [b"short", b"has a space", "café-token".encode("utf-8"), b"\xff\xfe\x00bad"])
def test_an_unusable_token_file_stops_the_start(tmp_path, bad):
    # never replaced behind your back: the devices that know the old token would all be locked out
    f = tmp_path / "access_token"
    f.write_bytes(bad)
    with pytest.raises(SystemExit) as e:
        access_token(str(f))
    assert "access token" in str(e.value).lower() and f.read_bytes() == bad


def test_a_kept_token_is_never_printed(tmp_path, monkeypatch, capsys):
    # under the hub, stdout goes to data/server.log, which the hub shows to anyone who can open it
    from studio.server import __main__ as main_mod
    f = tmp_path / "access_token"
    f.write_text("Kept-Token-123", encoding="ascii")
    monkeypatch.setattr(main_mod, "port_free", lambda p: True)
    monkeypatch.setattr(main_mod.web, "run_app", lambda *a, **k: None)
    monkeypatch.setattr(app, "make_app", lambda: None)
    for name in ("TRUSTED_HOSTS", "ACCESS_TOKEN", "TOKEN_DAYS"):  # main() sets them: put them back after
        monkeypatch.setattr(app, name, getattr(app, name))
    monkeypatch.setattr(app, "TRUSTED_HOSTS", set(app.TRUSTED_HOSTS))
    monkeypatch.setattr(sys, "argv", ["studio.server", "--allow-host", "box.tail.ts.net", "--token-file", str(f)])
    main_mod.main()
    out = capsys.readouterr().out
    assert "Kept-Token-123" not in out and "box.tail.ts.net" in out


def test_manifest_and_icons_are_built():
    dist = app.WEB
    if not (dist / "index.html").exists():
        pytest.skip("UI not built")
    m = json.loads((dist / "manifest.webmanifest").read_text(encoding="utf-8"))
    assert m["name"] == "reManim" and m["display"] == "standalone" and m["start_url"] == "/"
    sizes = {(i["sizes"], i.get("purpose", "any")) for i in m["icons"]}
    assert {("192x192", "any"), ("512x512", "any"), ("512x512", "maskable")} <= sizes
    for i in m["icons"]:
        assert (dist / i["src"].lstrip("/")).is_file(), i
    html = (dist / "index.html").read_text(encoding="utf-8")
    assert 'rel="manifest"' in html and "apple-touch-icon" in html and "/icons/favicon.svg" in html
    for f in ("icons/favicon.svg", "icons/wordmark-dark.svg", "favicon.ico"):
        assert (dist / f).is_file(), f
    # the SVG favicon and the wordmark are reachable without the token (install files)
    assert app.INSTALL_ICON.fullmatch("/icons/favicon.svg") and app.INSTALL_ICON.fullmatch("/icons/wordmark-dark.svg")


def test_status_prints_one_json_line():
    out = subprocess.run([sys.executable, "studio/scripts/serve.py", "status"], cwd=app.ROOT,
                         capture_output=True, text=True, timeout=30)
    assert out.returncode == 0, out.stderr
    st = json.loads(out.stdout.strip().splitlines()[-1])
    assert isinstance(st["running"], bool) and "ours" in st


def _post_token(token, host="box.tail.ts.net:8770"):
    import asyncio
    from aiohttp.test_utils import make_mocked_request
    req = make_mocked_request("POST", "/", headers={"Host": host, "Origin": f"https://{host}"})

    async def post():
        return {"token": token}
    req.post = post
    return asyncio.run(app.local_only(req, lambda r: None))


def test_a_non_ascii_token_is_a_wrong_token_not_a_crash(tailnet):  # noqa: F811
    # review after Phase 7: compare_digest on a non-ASCII str raised, a 500 with a traceback
    page = _call("/?token=%C3%A9", "box.tail.ts.net:8770")
    assert page.status == 403 and 'name="token"' in page.text
    with pytest.raises(web.HTTPForbidden):
        _call("/api/files", "box.tail.ts.net:8770", cookies={app.TOKEN_COOKIE: "\u00e9t\u00e9"})
    assert not app.token_ok("\u00e9") and not app.token_ok("") and app.token_ok("s3cret-token")


def test_the_token_page_posts_the_token(tailnet):  # noqa: F811
    # the token goes in the form body, never in a URL (history, proxies)
    page = _call("/", "box.tail.ts.net:8770")
    assert 'method="post"' in page.text
    with pytest.raises(web.HTTPSeeOther) as ok:
        _post_token("s3cret-token")
    assert ok.value.location == "/" and app.TOKEN_COOKIE in ok.value.cookies
    assert "token" not in ok.value.location
    wrong = _post_token("guess")
    assert wrong.status == 403 and "isn&#39;t the token" in wrong.text and "s3cret" not in wrong.text
