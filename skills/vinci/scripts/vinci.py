#!/usr/bin/env python3
"""Vinci command line.

    vinci.py analyze <exports...> --out vinci_out [--client NAME] [--brand-terms "a,b"]
    vinci.py check-briefs   --out vinci_out
    vinci.py render-briefs  --out vinci_out
    vinci.py check-rewrites --out vinci_out
    vinci.py render-rewrites --out vinci_out

analyze reads whatever was uploaded. A keyword list gives clusters.json (for briefs);
a site crawl gives title_audit.json (for title and description rewrites); both together
also link each topic to the page that should carry it.
"""

from __future__ import annotations

import argparse
import csv
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from vinci_core import audit, check, cluster, render  # noqa: E402
from vinci_core.load import load  # noqa: E402


def _write(path: Path, data: dict) -> None:
    path.write_text(json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8")


def _read(path: Path, what: str) -> dict:
    if not path.exists():
        sys.exit(f"Missing {path}. {what}")
    return json.loads(path.read_text(encoding="utf-8"))


def cmd_analyze(a) -> int:
    out = Path(a.out)
    out.mkdir(parents=True, exist_ok=True)
    loaded = load(a.inputs)
    brand = [t.strip() for t in (a.brand_terms or "").split(",") if t.strip()]
    merges = []
    for m in a.merge or []:
        if "=" not in m:
            sys.exit(f'--merge needs "keyword a=keyword b", got: {m}')
        left, right = m.split("=", 1)
        merges.append((left.strip(), right.strip()))
    summary = {"client": a.client or "", "files": loaded.files, "notes": loaded.notes, "produced": []}
    clusters = None
    if loaded.keywords:
        clusters = cluster.build(loaded, brand, a.overlap, merges, a.briefs)
        clusters["client"] = a.client or ""
        _write(out / "clusters.json", clusters)
        with (out / "keyword_clusters.csv").open("w", newline="", encoding="utf-8-sig") as f:
            w = csv.writer(f)
            w.writerow(["cluster_id", "primary_keyword", "keyword", "demand", "difficulty", "intent",
                        "position", "url", "action"])
            for c in clusters["clusters"]:
                for k in c["keywords"]:
                    w.writerow([c["id"], c["primary_keyword"], k["keyword"], k["demand"], k["difficulty"],
                                k["intent"], k["position"], k["url"], c["action"]])
        summary["produced"] += ["clusters.json", "keyword_clusters.csv"]
        summary["keywords"] = clusters["totals"]
    if loaded.pages:
        result = audit.build(loaded, clusters, a.rewrites)
        result["client"] = a.client or ""
        _write(out / "title_audit.json", result)
        summary["produced"].append("title_audit.json")
        summary["titles"] = result["totals"]
    if not summary["produced"]:
        summary["notes"].append("nothing to analyze: upload a keyword list, a site crawl, or both")
    _write(out / "summary.json", summary)
    print(json.dumps(summary, indent=2, ensure_ascii=False))
    return 0 if summary["produced"] else 1


def _report(errors: list[str], warnings: list[str]) -> int:
    for w in warnings:
        print(f"warning: {w}")
    for e in errors:
        print(f"ERROR: {e}")
    print(f"{len(errors)} error(s), {len(warnings)} warning(s)")
    return 1 if errors else 0


def _briefs(a):
    out = Path(a.out)
    return (out, _read(out / "clusters.json", "Run analyze with a keyword list first."),
            _read(out / "briefs.json", "Write briefs.json from templates/briefs_template.json first."))


def _rewrites(a):
    out = Path(a.out)
    return (out, _read(out / "title_audit.json", "Run analyze with a site crawl first."),
            _read(out / "rewrites.json", "Write rewrites.json from templates/rewrites_template.json first."))


def cmd_check_briefs(a) -> int:
    _, clusters, briefs = _briefs(a)
    return _report(*check.check_briefs(clusters, briefs))


def cmd_render_briefs(a) -> int:
    out, clusters, briefs = _briefs(a)
    errors, warnings = check.check_briefs(clusters, briefs)
    if _report(errors, warnings):
        print("Not rendered. Fix the errors above, then run again.")
        return 1
    briefs.setdefault("client", clusters.get("client", ""))
    for p in render.render_briefs(clusters, briefs, out):
        print(f"wrote {p}")
    return 0


def cmd_check_rewrites(a) -> int:
    _, result, rewrites = _rewrites(a)
    return _report(*check.check_rewrites(result, rewrites))


def cmd_render_rewrites(a) -> int:
    out, result, rewrites = _rewrites(a)
    errors, warnings = check.check_rewrites(result, rewrites)
    if _report(errors, warnings):
        print("Not rendered. Fix the errors above, then run again.")
        return 1
    paths = render.render_rewrites(result, rewrites, out)
    for p in paths:
        print(f"wrote {p}")
    if not any(str(p).endswith(".xlsx") for p in paths):
        print("openpyxl is not installed, so only the CSV was written (pip install openpyxl for the Excel sheet)")
    return 0


def main() -> int:
    ap = argparse.ArgumentParser(prog="vinci", description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest="cmd", required=True)
    an = sub.add_parser("analyze", help="read exports and calculate")
    an.add_argument("inputs", nargs="+", help="files, folders or zips")
    an.add_argument("--out", default="vinci_out")
    an.add_argument("--client", default="")
    an.add_argument("--brand-terms", default="", help='comma separated, for example "acme,acme co"')
    an.add_argument("--overlap", type=float, default=None, help="word overlap needed to share a cluster (default 0.5)")
    an.add_argument("--merge", action="append", help='join two clusters: "keyword a=keyword b" (repeatable)')
    an.add_argument("--briefs", type=int, default=None, help="how many clusters go in the brief queue (default 15)")
    an.add_argument("--rewrites", type=int, default=None, help="how many pages go in the rewrite queue (default 40)")
    an.set_defaults(fn=cmd_analyze)
    for name, fn in [("check-briefs", cmd_check_briefs), ("render-briefs", cmd_render_briefs),
                     ("check-rewrites", cmd_check_rewrites), ("render-rewrites", cmd_render_rewrites)]:
        p = sub.add_parser(name)
        p.add_argument("--out", default="vinci_out")
        p.set_defaults(fn=fn)
    a = ap.parse_args()
    return a.fn(a)


if __name__ == "__main__":
    sys.exit(main())
