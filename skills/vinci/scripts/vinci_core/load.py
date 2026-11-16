"""Work out what each export is and turn it into standard records.

Four kinds of file are recognized by their column names:
  keywords    keyword research exports (Semrush, Ahrefs, Keyword Planner, Search Console queries)
  crawl       site crawl exports with titles (Screaming Frog, Sitebulb, or any URL + title sheet)
  gsc_pages   Search Console pages export (clicks, impressions, CTR, position per page)
  page_query  page and query pairs (Search Console API, Looker Studio, Search Analytics for Sheets)
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field

from .fileio import Table, read_tables

ALIASES: dict[str, list[str]] = {
    "keyword": ["keyword", "keywords", "query", "queries", "top queries", "search term", "search terms",
                "keyword text", "search query"],
    "volume": ["search volume", "volume", "avg. monthly searches", "avg monthly searches",
               "monthly searches", "search vol", "search vol.", "sv", "msv"],
    "difficulty": ["keyword difficulty", "kd", "kd %", "kd%", "difficulty", "seo difficulty"],
    "cpc": ["cpc", "cpc (usd)", "cpc usd"],
    "intent": ["intent", "intents", "search intent", "keyword intents"],
    "position": ["position", "current position", "avg. position", "average position", "avg position", "rank"],
    "kw_url": ["url", "current url", "ranking url", "landing page"],
    "url": ["address", "url", "page url", "page", "top pages", "pages", "landing page"],
    "title": ["title 1", "title", "page title", "meta title", "seo title"],
    "description": ["meta description 1", "meta description", "description"],
    "h1": ["h1-1", "h1 1", "h1"],
    "status": ["status code", "http status code", "status"],
    "indexability": ["indexability"],
    "content_type": ["content type", "content"],
    "clicks": ["clicks", "url clicks"],
    "impressions": ["impressions"],
    "ctr": ["ctr", "url ctr", "site ctr"],
}
KNOWN_HEADERS = {a for names in ALIASES.values() for a in names}


@dataclass
class Loaded:
    keywords: list[dict] = field(default_factory=list)
    demand_type: str | None = None  # "search volume" or "impressions"
    pages: list[dict] = field(default_factory=list)
    gsc_pages: dict[str, dict] = field(default_factory=dict)  # by normalized URL
    page_queries: dict[str, list[dict]] = field(default_factory=dict)
    files: list[dict] = field(default_factory=list)
    notes: list[str] = field(default_factory=list)


def parse_number(value: str) -> tuple[float | None, bool]:
    """Return (number, was_a_range). Understands 1,234 and 1.2K and '1K – 10K'."""
    s = str(value or "").strip().replace("–", "-").replace("—", "-")
    if not s or s.lower() in {"-", "n/a", "na", "null", "none", "--"}:
        return None, False
    was_range = False
    m = re.match(r"^([\d.,]+\s*[kKmM]?)\s*-\s*([\d.,]+\s*[kKmM]?)$", s)
    if m:
        s, was_range = m.group(1), True
    s = s.replace("%", "").replace("<", "").replace(">", "").replace("$", "").strip()
    mult = 1.0
    if s[-1:].lower() == "k":
        mult, s = 1_000.0, s[:-1]
    elif s[-1:].lower() == "m":
        mult, s = 1_000_000.0, s[:-1]
    try:
        return float(s.replace(",", "").strip()) * mult, was_range
    except ValueError:
        return None, False


def norm_url(u: str) -> str:
    """A join key for URLs: no protocol, no www, no fragment, no trailing slash, lower case."""
    u = re.sub(r"#.*$", "", str(u or "").strip())
    u = re.sub(r"^https?://", "", u, flags=re.I)
    u = re.sub(r"^www\.", "", u, flags=re.I)
    return u.rstrip("/").lower()


def _col(table: Table, field_name: str) -> str | None:
    for alias in ALIASES[field_name]:
        if alias in table.headers:
            return alias
    return None


def detect_kind(table: Table) -> str | None:
    has = lambda f: _col(table, f) is not None  # noqa: E731
    if has("keyword") and has("volume"):
        return "keywords"
    if has("title") and has("url"):
        return "crawl"
    if has("keyword") and has("url") and has("clicks"):
        return "page_query"
    if has("url") and (has("clicks") or has("impressions")):
        return "gsc_pages"
    if has("keyword"):
        return "keywords"
    return None


def _num(row: dict, col: str | None) -> float | None:
    return parse_number(row.get(col, ""))[0] if col else None


def _load_keywords(table: Table, out: Loaded) -> int:
    kw, vol, imp = _col(table, "keyword"), _col(table, "volume"), _col(table, "impressions")
    demand_col = vol or imp
    demand_type = "search volume" if vol else ("impressions" if imp else None)
    if demand_type and out.demand_type and demand_type != out.demand_type:
        out.notes.append(f"{table.name}: uses {demand_type} while other files use {out.demand_type}; "
                         "the two are not comparable, so this file was skipped")
        return 0
    out.demand_type = out.demand_type or demand_type
    ranges = 0
    n = 0
    for row in table.rows:
        text = re.sub(r"\s+", " ", row.get(kw, "")).strip()
        if not text:
            continue
        demand, was_range = parse_number(row.get(demand_col, "")) if demand_col else (None, False)
        ranges += was_range
        out.keywords.append({
            "keyword": text,
            "demand": demand,
            "difficulty": _num(row, _col(table, "difficulty")),
            "cpc": _num(row, _col(table, "cpc")),
            "intent_from_export": row.get(_col(table, "intent") or "", "").strip() or None,
            "position": _num(row, _col(table, "position")),
            "url": row.get(_col(table, "kw_url") or "", "").strip() or None,
        })
        n += 1
    if ranges:
        out.notes.append(f"{table.name}: {ranges} volume value(s) were ranges (for example 1K - 10K); "
                         "the low end of each range was used")
    if demand_type is None:
        out.notes.append(f"{table.name}: no search volume column, so keywords from this file have no demand number")
    return n


def _load_crawl(table: Table, out: Loaded) -> int:
    url, status = _col(table, "url"), _col(table, "status")
    ctype, index = _col(table, "content_type"), _col(table, "indexability")
    skipped = {"not HTML": 0, "not status 200": 0, "non-indexable": 0}
    n = 0
    for row in table.rows:
        address = row.get(url, "").strip()
        if not address:
            continue
        if ctype and row.get(ctype, "") and "html" not in row[ctype].lower():
            skipped["not HTML"] += 1
            continue
        if status and row.get(status, "") and row[status].strip()[:3] != "200":
            skipped["not status 200"] += 1
            continue
        if index and row.get(index, "").strip().lower().startswith("non"):
            skipped["non-indexable"] += 1
            continue
        out.pages.append({
            "url": address,
            "title": row.get(_col(table, "title") or "", "").strip(),
            "description": row.get(_col(table, "description") or "", "").strip(),
            "h1": row.get(_col(table, "h1") or "", "").strip(),
        })
        n += 1
    parts = [f"{v} {k}" for k, v in skipped.items() if v]
    if parts:
        out.notes.append(f"{table.name}: left out {', '.join(parts)} page(s)")
    if not _col(table, "description"):
        out.notes.append(f"{table.name}: no meta description column, so descriptions could not be checked")
    return n


def _metrics(row: dict, table: Table) -> dict:
    ctr = _num(row, _col(table, "ctr"))
    clicks, imps = _num(row, _col(table, "clicks")), _num(row, _col(table, "impressions"))
    if clicks is not None and imps:
        ctr = round(100.0 * clicks / imps, 2)  # recompute so the unit is always percent
    whole = lambda x: int(x) if x is not None and float(x).is_integer() else x  # noqa: E731
    return {"clicks": whole(clicks), "impressions": whole(imps), "ctr_pct": ctr,
            "position": _num(row, _col(table, "position"))}


def _load_gsc_pages(table: Table, out: Loaded) -> int:
    url = _col(table, "url")
    n = 0
    for row in table.rows:
        key = norm_url(row.get(url, ""))
        if key:
            out.gsc_pages[key] = _metrics(row, table)
            n += 1
    return n


def _load_page_query(table: Table, out: Loaded) -> int:
    url, kw = _col(table, "url"), _col(table, "keyword")
    n = 0
    for row in table.rows:
        key, query = norm_url(row.get(url, "")), row.get(kw, "").strip()
        if key and query:
            out.page_queries.setdefault(key, []).append({"query": query, **_metrics(row, table)})
            n += 1
    return n


LOADERS = {"keywords": _load_keywords, "crawl": _load_crawl,
           "gsc_pages": _load_gsc_pages, "page_query": _load_page_query}
KIND_LABEL = {"keywords": "keyword list", "crawl": "site crawl",
              "gsc_pages": "Search Console pages", "page_query": "page and query pairs"}


def load(paths: list) -> Loaded:
    tables, problems = read_tables(paths, KNOWN_HEADERS)
    out = Loaded(notes=list(problems))
    for table in tables:
        kind = detect_kind(table)
        if kind is None:
            shown = ", ".join(table.headers[:8])
            out.files.append({"file": table.name, "read_as": "not recognized", "rows": 0})
            out.notes.append(f"{table.name}: not recognized. Columns seen: {shown}")
            continue
        rows = LOADERS[kind](table, out)
        out.files.append({"file": table.name, "read_as": KIND_LABEL[kind], "rows": rows})
        out.notes.extend(f"{table.name}: {n}" for n in table.notes)
    return out
