"""Turn checked work into files people can use: an HTML brief pack, one Markdown
file per brief for writers, and a review sheet for title and description changes."""

from __future__ import annotations

import base64
import csv
import html
from pathlib import Path

from .load import norm_url
from .text import slug

LOGO = Path(__file__).resolve().parents[2] / "assets" / "logo.png"

CSS = """
:root{--primary:#C1FF72;--primary-t40:#DBFFB5;--primary-s40:#5F8036;--secondary-t60:#DFE2FF;--secondary-s50:#424563;
--accent:#FE80DA;--accent-t60:#FFD1EF;--accent-s50:#632E54;--neutral:#DAE1D4;--neutral-t60:#F0F3EE;--neutral-t80:#F8F9F6;
--contrast:#141F06;--contrast-t30:#515A47;--contrast-t50:#7F8678;
--font-header:"Inter Tight",system-ui,sans-serif;--font-title:"Inter",system-ui,sans-serif;--font-para:"Open Sans",system-ui,sans-serif}
*{box-sizing:border-box}
body{margin:0;background:var(--neutral-t80);color:var(--contrast);font:400 16px/1.6 var(--font-para)}
header{background:var(--contrast);color:#fff;padding:40px 24px}
.wrap{max-width:920px;margin:0 auto;padding:0 24px}
header .wrap{display:flex;gap:20px;align-items:center;padding:0}
header img{width:64px;height:64px;flex:none}
header .mark{font:700 14px var(--font-title);letter-spacing:.14em;text-transform:uppercase;color:var(--primary)}
h1{font:700 clamp(28px,5vw,44px)/1.1 var(--font-header);margin:6px 0 4px}
header p{margin:0;color:var(--neutral)}
h2{font:700 28px/1.2 var(--font-header);margin:0 0 10px}
h3{font:600 13px var(--font-title);letter-spacing:.08em;text-transform:uppercase;color:var(--contrast-t30);margin:26px 0 8px}
main{padding:32px 0 56px}
.card{background:#fff;border:1px solid var(--neutral);border-radius:16px;padding:28px;margin:0 0 24px}
.chips{display:flex;flex-wrap:wrap;gap:8px;margin:0 0 6px}
.chip{font:600 12px var(--font-title);padding:4px 12px;border-radius:999px;background:var(--neutral-t60)}
.chip.intent{background:var(--secondary-t60);color:var(--secondary-s50)}
.chip.new{background:var(--accent-t60);color:var(--accent-s50)}
.chip.refresh{background:var(--primary-t40);color:#34481B}
.facts{display:grid;grid-template-columns:repeat(auto-fit,minmax(150px,1fr));gap:12px;margin:16px 0 4px}
.fact{background:var(--neutral-t80);border-radius:12px;padding:12px 14px}
.fact b{display:block;font:700 22px var(--font-header)}
.fact span{font-size:13px;color:var(--contrast-t30)}
.scroll{overflow-x:auto}
table{border-collapse:collapse;width:100%;font-size:14px}
th{font:600 12px var(--font-title);text-align:left;color:var(--contrast-t30);padding:8px 10px;border-bottom:2px solid var(--neutral)}
td{padding:8px 10px;border-bottom:1px solid var(--neutral-t60);vertical-align:top}
td.n,th.n{text-align:right;font-variant-numeric:tabular-nums;white-space:nowrap}
.serp{border-left:4px solid var(--primary);background:var(--neutral-t80);border-radius:0 12px 12px 0;padding:12px 16px}
.serp .t{font:600 18px var(--font-title)}
.serp small,.muted{color:var(--contrast-t50);font-size:13px}
ol,ul{padding-left:22px;margin:6px 0}
li{margin:4px 0}
a{color:var(--primary-s40);overflow-wrap:anywhere}
footer{color:var(--contrast-t50);font-size:13px;padding:0 0 40px}
@media print{body{background:#fff}.card{break-inside:avoid-page;border-color:#ccc}.brief{break-before:page}}
"""


def esc(x) -> str:
    return html.escape("" if x is None else str(x))


def num(x) -> str:
    if x is None:
        return "n/a"
    return f"{int(x):,}" if float(x).is_integer() else f"{x:,.1f}"


def _logo_tag() -> str:
    if not LOGO.exists():
        return ""
    data = base64.b64encode(LOGO.read_bytes()).decode("ascii")
    return f'<img alt="Vinci" src="data:image/png;base64,{data}">'


def _page(title: str, subtitle: str, body: str) -> str:
    fonts = ("https://fonts.googleapis.com/css2?family=Inter+Tight:wght@700&family=Inter:wght@600"
             "&family=Open+Sans:wght@400;600&display=swap")
    return (f'<!doctype html><html lang="en"><head><meta charset="utf-8">'
            f'<meta name="viewport" content="width=device-width,initial-scale=1"><title>{esc(title)}</title>'
            f'<link rel="stylesheet" href="{fonts}"><style>{CSS}</style></head><body>'
            f'<header><div class="wrap">{_logo_tag()}<div><div class="mark">Vinci</div>'
            f'<h1>{esc(title)}</h1><p>{esc(subtitle)}</p></div></div></header>'
            f'<main><div class="wrap">{body}</div></main>'
            f'<footer><div class="wrap">Made with Vinci. Numbers come from the uploaded exports; '
            f'the writing is drafted by Claude and checked against them.</div></footer></body></html>')


def _list(items, ordered=False) -> str:
    tag = "ol" if ordered else "ul"
    return f"<{tag}>" + "".join(f"<li>{esc(i)}</li>" for i in items) + f"</{tag}>" if items else ""


def render_briefs(clusters: dict, briefs: dict, out_dir: Path) -> list[Path]:
    by_id = {c["id"]: c for c in clusters["clusters"]}
    demand = clusters["demand_type"]
    demand_label = {"search volume": "Monthly searches", "impressions": "Impressions"}.get(demand, "Demand")
    client = briefs.get("client") or ""
    items = briefs["briefs"]
    rows = "".join(
        f'<tr><td class="n">{i}</td><td><a href="#b{b["cluster_id"]}">{esc(b["working_title"])}</a><br>'
        f'<span class="muted">{esc(by_id[b["cluster_id"]]["primary_keyword"])}</span></td>'
        f'<td class="n">{num(by_id[b["cluster_id"]]["total_demand"])}</td>'
        f'<td class="n">{by_id[b["cluster_id"]]["keyword_count"]}</td>'
        f'<td>{esc(by_id[b["cluster_id"]]["intent"])}</td><td>{esc(by_id[b["cluster_id"]]["action"])}</td></tr>'
        for i, b in enumerate(items, 1))
    body = [f'<section class="card"><h2>What to write, in order</h2><div class="scroll"><table><tr><th class="n">#</th>'
            f'<th>Piece</th><th class="n">{demand_label}</th><th class="n">Keywords</th><th>Intent</th>'
            f'<th>Action</th></tr>{rows}</table></div></section>']
    written = []
    briefs_dir = out_dir / "briefs"
    briefs_dir.mkdir(parents=True, exist_ok=True)
    for i, b in enumerate(items, 1):
        c = by_id[b["cluster_id"]]
        targets = {t.lower() for t in b.get("target_keywords", [])}
        kw_rows = "".join(
            f'<tr><td>{esc(k["keyword"])}</td><td class="n">{num(k["demand"])}</td>'
            f'<td class="n">{num(k["difficulty"])}</td><td class="n">{num(k["position"])}</td></tr>'
            for k in c["keywords"] if k["keyword"].lower() in targets)
        existing = c.get("existing_page")
        action_class = "refresh" if existing else "new"
        existing_html = (f'<h3>Existing page to refresh</h3><p><a href="{esc(existing["url"])}">{esc(existing["url"])}</a>'
                         f'<br><span class="muted">Chosen because of {esc(existing["matched_by"])}.</span></p>'
                         if existing else "")
        outline = "".join(f'<li><b>{esc(o.get("heading"))}</b>'
                          + (f'<br><span class="muted">{esc(o["notes"])}</span>' if o.get("notes") else "") + "</li>"
                          for o in b.get("outline", []))
        links = [l.get("url") if isinstance(l, dict) else l for l in b.get("internal_links", [])]
        link_html = ("<ul>" + "".join(f'<li><a href="{esc(u)}">{esc(u)}</a></li>' for u in links) + "</ul>") if links else ""
        section = lambda title, content: f"<h3>{title}</h3>{content}" if content else ""  # noqa: E731
        para = lambda key: f"<p>{esc(b[key])}</p>" if b.get(key) else ""  # noqa: E731
        desc = b.get("meta_description", "")
        body.append(
            f'<section class="card brief" id="b{c["id"]}"><div class="chips"><span class="chip">Brief {i}</span>'
            f'<span class="chip intent">{esc(c["intent"])}</span>'
            f'<span class="chip {action_class}">{esc(c["action"])}</span></div>'
            f'<h2>{esc(b["working_title"])}</h2>'
            f'<div class="facts"><div class="fact"><b>{num(c["total_demand"])}</b><span>{demand_label}, whole topic</span></div>'
            f'<div class="fact"><b>{c["keyword_count"]}</b><span>Keywords in this topic</span></div>'
            f'<div class="fact"><b>{num(c["average_difficulty"])}</b><span>Average difficulty</span></div></div>'
            + section("Why this piece", para("summary"))
            + section("What the searcher wants", para("search_intent"))
            + section("Who it is for", para("audience"))
            + section("Angle", para("angle"))
            + existing_html
            + f'<h3>Search result preview</h3><div class="serp"><div class="t">{esc(b["working_title"])}</div>'
              f'<div>{esc(desc)}</div><small>Title {len(b["working_title"])} characters'
              f'{", description " + str(len(desc)) + " characters" if desc else ""}</small></div>'
            + f'<h3>Target keywords</h3><div class="scroll"><table><tr><th>Keyword</th><th class="n">{demand_label}</th>'
              f'<th class="n">Difficulty</th><th class="n">Current position</th></tr>{kw_rows}</table></div>'
            + section("Questions to answer", _list(b.get("questions_to_answer", [])))
            + section("Outline", f"<ol>{outline}</ol>" if outline else "")
            + section("Link to these pages", link_html)
            + section("Notes for the writer", para("writer_notes"))
            + "</section>")
        md = [f"# {b['working_title']}", "",
              f"**Primary keyword:** {c['primary_keyword']}  ",
              f"**{demand_label} (whole topic):** {num(c['total_demand'])}  ",
              f"**Intent:** {c['intent']}  ", f"**Action:** {c['action']}"
              + (f" ({existing['url']})" if existing else ""), ""]
        for title, key in [("Why this piece", "summary"), ("What the searcher wants", "search_intent"),
                           ("Who it is for", "audience"), ("Angle", "angle")]:
            if b.get(key):
                md += [f"## {title}", "", b[key], ""]
        md += ["## Search result preview", "", f"- Title ({len(b['working_title'])} characters): {b['working_title']}"]
        if desc:
            md.append(f"- Description ({len(desc)} characters): {desc}")
        md += ["", "## Target keywords", "", f"| Keyword | {demand_label} | Difficulty | Current position |",
               "|---|---:|---:|---:|"]
        md += [f"| {k['keyword']} | {num(k['demand'])} | {num(k['difficulty'])} | {num(k['position'])} |"
               for k in c["keywords"] if k["keyword"].lower() in targets]
        if b.get("questions_to_answer"):
            md += ["", "## Questions to answer", ""] + [f"- {q}" for q in b["questions_to_answer"]]
        if b.get("outline"):
            md += ["", "## Outline", ""]
            for j, o in enumerate(b["outline"], 1):
                md.append(f"{j}. **{o.get('heading')}**" + (f": {o['notes']}" if o.get("notes") else ""))
        if links:
            md += ["", "## Link to these pages", ""] + [f"- {u}" for u in links]
        if b.get("writer_notes"):
            md += ["", "## Notes for the writer", "", b["writer_notes"]]
        path = briefs_dir / f"{i:02d}-{slug(c['primary_keyword'])}.md"
        path.write_text("\n".join(md) + "\n", encoding="utf-8")
        written.append(path)
    notes = clusters.get("notes", [])
    if notes:
        body.append('<section class="card"><h2>About the data</h2>' + _list(notes) + "</section>")
    subtitle = f"Content briefs{' for ' + client if client else ''}: {len(items)} pieces from {num(clusters['totals']['keywords'])} keywords"
    report = out_dir / "briefs.html"
    report.write_text(_page("Content briefs", subtitle, "".join(body)), encoding="utf-8")
    return [report] + written


REVIEW_COLUMNS = ["Priority", "URL", "Current title", "Chars", "New title", "Chars", "Current description", "Chars",
                  "New description", "Chars", "What was wrong", "Why this change", "Impressions", "Click rate %",
                  "Position", "Target keyword", "Approved? (yes / no / edit)", "Reviewer notes"]


def render_rewrites(audit: dict, rewrites: dict, out_dir: Path) -> list[Path]:
    pages = {norm_url(p["url"]): p for p in audit["pages"]}
    order = {norm_url(u): i for i, u in enumerate(audit["rewrite_queue"])}
    items = sorted(rewrites["rewrites"], key=lambda r: order.get(norm_url(r["url"]), len(order)))
    table = []
    for i, r in enumerate(items, 1):
        p = pages[norm_url(r["url"])]
        sc = p.get("search_console") or {}
        new_title, new_desc = r.get("new_title", "").strip(), r.get("new_description", "").strip()
        table.append([i, p["url"], p["title"], p["title_chars"], new_title or "(keep current)",
                      len(new_title) if new_title else "", p["description"],
                      p["description_chars"], new_desc or "(keep current)", len(new_desc) if new_desc else "",
                      "; ".join(p["issue_text"]), r.get("reason", ""), sc.get("impressions", ""),
                      sc.get("ctr_pct", ""), sc.get("position", ""),
                      p.get("target_keyword") or (p["top_queries"][0]["query"] if p.get("top_queries") else ""),
                      "", ""])
    out_dir.mkdir(parents=True, exist_ok=True)
    written = []
    csv_path = out_dir / "title_review.csv"
    with csv_path.open("w", newline="", encoding="utf-8-sig") as f:
        w = csv.writer(f)
        w.writerow(REVIEW_COLUMNS)
        w.writerows([["" if v is None else v for v in row] for row in table])
    written.append(csv_path)
    try:
        from openpyxl import Workbook
        from openpyxl.styles import Alignment, Font, PatternFill
        from openpyxl.utils import get_column_letter
    except ImportError:
        return written
    wb = Workbook()
    ws = wb.active
    ws.title = "Title review"
    ws.append(REVIEW_COLUMNS)
    for row in table:
        ws.append(["" if v is None else v for v in row])
    widths = [8, 38, 42, 7, 42, 7, 48, 7, 48, 7, 36, 40, 12, 12, 10, 24, 22, 30]
    for i, wdt in enumerate(widths, 1):
        ws.column_dimensions[get_column_letter(i)].width = wdt
        cell = ws.cell(row=1, column=i)
        cell.font = Font(bold=True, color="C1FF72")
        cell.fill = PatternFill("solid", fgColor="141F06")
        cell.alignment = Alignment(wrap_text=True, vertical="center")
    new_fill, approve_fill = PatternFill("solid", fgColor="E8FFD1"), PatternFill("solid", fgColor="FFE8F7")
    for row in ws.iter_rows(min_row=2):
        for cell in row:
            cell.alignment = Alignment(wrap_text=True, vertical="top")
        row[4].fill = row[8].fill = new_fill
        row[16].fill = approve_fill
    ws.freeze_panes = "C2"
    ws.row_dimensions[1].height = 34
    info = wb.create_sheet("Read me")
    T = audit["thresholds"]
    lines = [
        "How to use this sheet",
        "Green columns are the proposed new title and description. Pink is for your decision.",
        "Write yes, no or edit in the Approved column. If you edit, change the green cell directly.",
        f"Titles are kept to {T['title_max_chars']} characters and descriptions to {T['description_max_chars']} "
        "so search results are unlikely to cut them off. These limits are rules of thumb.",
        "Pages are listed in priority order: most impressions first when Search Console data was provided.",
        "Click rate is compared with this site's own pages at similar positions, not with an outside benchmark.",
        "", "About the data"] + list(audit.get("notes", []))
    for line in lines:
        info.append([line])
    info.column_dimensions["A"].width = 120
    info["A1"].font = Font(bold=True, size=14)
    xlsx_path = out_dir / "title_review.xlsx"
    wb.save(xlsx_path)
    written.append(xlsx_path)
    return written
