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
    f.write_text("short", encoding="ascii")
    assert access_token(str(f)) != "short"  # a damaged file gets a new token
    assert access_token(None) != access_token(None)


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
