"""Census over the whole corpus (corpus.md §4: statements tier 1 or 2).

Static: reads the code, renders nothing, so it is safe to run while the
studio is busy. Uses the same tiers as the studio (server/code/census.py)
and the same API names as the engine worker.

Run:  .venv/Scripts/python -u -m studio.tests.census_run [--lines]
Report: studio/tests/tmp/census_report.json
"""

from __future__ import annotations

import ast
import json
import sys
from collections import Counter, defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

from studio.server.code.census import classify  # noqa: E402
from studio.tests.corpus_run import group_of  # noqa: E402

TMP = ROOT / "studio" / "tests" / "tmp"
REPO = ["test_scene.py", "pythagoras.py", "order_matters.py", "gradient_descent.py", "eola_preview.py"]


def corpus_files() -> list[str]:
    out = list(REPO)
    for d in ("studio/tests/corpus/awkward", "studio/tests/corpus/gallery", "tools/fixtures"):
        out += sorted(f"{d}/{p.name}" for p in (ROOT / d).glob("*.py"))
    return out


def kind_of(text: str) -> str:
    """A rough label for a tier-3 line, for the report."""
    t = text.strip()
    if "always_redraw" in t:
        return "always_redraw"
    if "add_updater" in t or "remove_updater" in t:
        return "updater"
    if "lambda" in t:
        return "lambda"
    if t.startswith("def "):
        return "nested def"
    if t.startswith(("for ", "while ")):
        return "loop"
    if t.startswith(("if ", "elif ", "else")) or " if " in t:
        return "condition"
    if t.startswith(("try", "except", "finally", "with ")):
        return "try/with"
    return "other"


def api_names() -> set[str]:
    from studio.server.engine.runtime import api_names as names
    return set(names())


def run(show_lines: bool) -> dict:
    api = api_names()
    groups: dict[str, Counter] = defaultdict(Counter)
    kinds: Counter = Counter()
    examples: dict[str, list] = defaultdict(list)
    files = []
    for rel in corpus_files():
        src = (ROOT / rel).read_text(encoding="utf-8")
        try:
            tree = ast.parse(src)
        except SyntaxError:
            files.append({"file": rel, "error": "does not parse"})
            continue
        c = classify(tree, api)
        lines = src.splitlines()
        g = group_of(rel)
        groups[g].update(c.tiers)
        t3 = []
        for ln, tier in sorted(c.lines.items()):
            if tier != 3:
                continue
            text = lines[ln - 1].strip()
            k = kind_of(text)
            kinds[k] += 1
            t3.append({"line": ln, "kind": k, "text": text[:120]})
            if len(examples[k]) < 8:
                examples[k].append(f"{Path(rel).name}:{ln}: {text[:100]}")
        files.append({"file": rel, "group": g, "tiers": {str(t): c.tiers[t] for t in (1, 2, 3)},
                      "tier3": t3})
    total = Counter()
    for c in groups.values():
        total.update(c)

    def share(c: Counter) -> dict:
        n = sum(c[t] for t in (1, 2, 3)) or 1
        return {"statements": n, "t1": round(100 * c[1] / n, 1), "t2": round(100 * c[2] / n, 1),
                "t3": round(100 * c[3] / n, 1), "t12": round(100 * (c[1] + c[2]) / n, 1)}

    report = {"groups": {g: share(c) for g, c in sorted(groups.items())}, "all": share(total),
              "tier3_kinds": dict(kinds.most_common()), "examples": examples, "files": files}
    TMP.mkdir(parents=True, exist_ok=True)
    (TMP / "census_report.json").write_text(json.dumps(report, indent=1), encoding="utf-8")
    for g, s in report["groups"].items():
        print(f"{g:9} {s['statements']:5} statements  tier 1-2 {s['t12']:5}%  (t1 {s['t1']}%, t3 {s['t3']}%)")
    s = report["all"]
    print(f"{'ALL':9} {s['statements']:5} statements  tier 1-2 {s['t12']:5}%  (t1 {s['t1']}%, t3 {s['t3']}%)")
    print("tier 3:", ", ".join(f"{k} {v}" for k, v in kinds.most_common()))
    if show_lines:
        for f in files:
            for x in f.get("tier3", []):
                print(f"  {Path(f['file']).name}:{x['line']} [{x['kind']}] {x['text']}")
    return report


if __name__ == "__main__":
    run("--lines" in sys.argv)
