"""Checks of the web UI's own tables that need no browser (Node runs them)."""

import shutil
import subprocess
from pathlib import Path

import pytest

WEB = Path(__file__).resolve().parents[2] / "web"


@pytest.mark.skipif(shutil.which("node") is None, reason="Node isn't installed")
def test_keymap_has_no_clashes():
    out = subprocess.run(["node", "checks/keymap_check.ts"], cwd=WEB, capture_output=True, text=True, timeout=60)
    assert out.returncode == 0, out.stdout + out.stderr


@pytest.mark.skipif(shutil.which("node") is None, reason="Node isn't installed")
def test_readme_shortcuts_match_the_keymap():
    out = subprocess.run(["node", "checks/keymap_md.ts"], cwd=WEB, capture_output=True, text=True,
                         encoding="utf-8", timeout=60)
    assert out.returncode == 0, out.stderr
    readme = (WEB.parent / "README.md").read_text(encoding="utf-8")
    begin = readme.index("-->", readme.index("<!-- keys:begin")) + 3
    table = readme[begin:readme.index("<!-- keys:end")].strip()
    assert table == out.stdout.strip(), "README shortcuts are out of date: run node web/checks/keymap_md.ts"
