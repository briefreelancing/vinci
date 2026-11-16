"""Check page titles and meta descriptions and build a rewrite queue.

Length limits are rules of thumb for what search results usually show; they
are listed in the output so they can be questioned. Click rate is judged
against this site's own pages at similar positions, never an outside curve.
"""

from __future__ import annotations

import statistics
from collections import Counter

from .load import Loaded, norm_url
from .text import core_tokens, tokens

THRESHOLDS = {
    "title_min_chars": 30,
    "title_max_chars": 60,
    "description_min_chars": 70,
    "description_max_chars": 155,
    "low_ctr_min_impressions": 100,
    "low_ctr_min_pages_in_band": 5,
    "low_ctr_share_of_band_median": 0.5,
    "brand_suffix_min_share_pct": 50,
    "rewrite_queue_size": 40,
}
BANDS = [(1, 3.5, "positions 1 to 3"), (3.5, 6.5, "positions 4 to 6"),
         (6.5, 10.5, "positions 7 to 10"), (10.5, 20.5, "positions 11 to 20")]
SEPARATORS = [" | ", " - ", " – ", " — ", " · ", " : "]
ISSUE_TEXT = {
    "title_missing": "No title",
    "title_too_long": "Title is likely to be cut off in search results",
    "title_too_short": "Title is short and may undersell the page",
    "title_duplicate": "Same title as another page",
    "description_missing": "No meta description",
    "description_too_long": "Description is likely to be cut off",
    "description_too_short": "Description is short",
    "description_duplicate": "Same description as another page",
    "low_click_rate": "Click rate is low for where it ranks, compared with this site's other pages",
    "title_misses_top_query": "Title does not contain the page's top search query",
    "title_misses_target_keyword": "Title does not contain the target keyword from the keyword plan",
}


def _suffix(title: str) -> str | None:
    cut = max(((title.rfind(sep), sep) for sep in SEPARATORS), key=lambda x: x[0])
    return title[cut[0]:] if cut[0] > 0 else None


def find_brand_suffix(titles: list[str]) -> dict | None:
    titled = [t for t in titles if t]
    counts = Counter(s for s in (_suffix(t) for t in titled) if s)
    if not counts:
        return None
    text, n = counts.most_common(1)[0]
    share = round(100.0 * n / len(titled), 1)
    if share >= THRESHOLDS["brand_suffix_min_share_pct"]:
        return {"text": text, "share_of_titles_pct": share}
    return None


def _band(position: float | None) -> str | None:
    if position is None:
        return None
    return next((name for lo, hi, name in BANDS if lo <= position < hi), None)


def build(loaded: Loaded, clusters: dict | None = None, queue_size: int | None = None) -> dict:
    T = THRESHOLDS
    queue_size = queue_size or T["rewrite_queue_size"]
    has_desc = any(p["description"] for p in loaded.pages)
    title_counts = Counter(p["title"].lower() for p in loaded.pages if p["title"])
    desc_counts = Counter(p["description"].lower() for p in loaded.pages if p["description"])
    targets = {}
    for c in (clusters or {}).get("clusters", []):
        if c.get("existing_page"):
            targets.setdefault(norm_url(c["existing_page"]["url"]), c["primary_keyword"])

    # This site's own typical click rate at each position band.
    band_ctrs: dict[str, list[float]] = {}
    for p in loaded.pages:
        m = loaded.gsc_pages.get(norm_url(p["url"]))
        if m and m["ctr_pct"] is not None and (m["impressions"] or 0) >= T["low_ctr_min_impressions"]:
            b = _band(m["position"])
            if b:
                band_ctrs.setdefault(b, []).append(m["ctr_pct"])
    band_median = {b: round(statistics.median(v), 2) for b, v in band_ctrs.items()
                   if len(v) >= T["low_ctr_min_pages_in_band"]}

    pages = []
    for p in loaded.pages:
        key = norm_url(p["url"])
        m = loaded.gsc_pages.get(key)
        issues = []
        tl, dl = len(p["title"]), len(p["description"])
        if not p["title"]:
            issues.append("title_missing")
        else:
            if tl > T["title_max_chars"]:
                issues.append("title_too_long")
            elif tl < T["title_min_chars"]:
                issues.append("title_too_short")
            if title_counts[p["title"].lower()] > 1:
                issues.append("title_duplicate")
        if has_desc:
            if not p["description"]:
                issues.append("description_missing")
            else:
                if dl > T["description_max_chars"]:
                    issues.append("description_too_long")
                elif dl < T["description_min_chars"]:
                    issues.append("description_too_short")
                if desc_counts[p["description"].lower()] > 1:
                    issues.append("description_duplicate")
        band = _band(m["position"]) if m else None
        if (m and band in band_median and m["ctr_pct"] is not None
                and (m["impressions"] or 0) >= T["low_ctr_min_impressions"]
                and m["ctr_pct"] < T["low_ctr_share_of_band_median"] * band_median[band]):
            issues.append("low_click_rate")
        queries = sorted(loaded.page_queries.get(key, []),
                         key=lambda q: (-(q["impressions"] or 0), q["query"]))[:5]
        title_tokens = tokens(p["title"])
        if queries and p["title"] and not tokens(queries[0]["query"]) <= title_tokens:
            issues.append("title_misses_top_query")
        target = targets.get(key)
        if target and p["title"] and not core_tokens(target) <= title_tokens:
            issues.append("title_misses_target_keyword")
        pages.append({
            "url": p["url"], "title": p["title"], "title_chars": tl,
            "description": p["description"], "description_chars": dl, "h1": p["h1"],
            "issues": issues, "issue_text": [ISSUE_TEXT[i] for i in issues],
            "search_console": ({**m, "position_band": band,
                                "band_median_ctr_pct": band_median.get(band)} if m else None),
            "top_queries": queries, "target_keyword": target,
        })

    flagged = [p for p in pages if p["issues"]]
    flagged.sort(key=lambda p: (-((p["search_console"] or {}).get("impressions") or 0),
                                -len(p["issues"]), p["url"]))
    notes = []
    if not loaded.gsc_pages:
        notes.append("no Search Console pages export, so pages are ordered by number of issues, not by "
                     "impressions, and click rate could not be checked")
    elif not band_median:
        notes.append("too few pages with enough impressions to judge click rate against this site's own pages")
    if not loaded.page_queries:
        notes.append("no page and query pairs, so titles could not be checked against each page's top query")
    if not has_desc:
        notes.append("no meta descriptions in the crawl, so description checks were skipped")
    matched = sum(1 for p in pages if p["search_console"])
    return {
        "totals": {"pages_checked": len(pages), "pages_with_issues": len(flagged),
                   "pages_matched_to_search_console": matched,
                   "issue_counts": dict(Counter(i for p in pages for i in p["issues"]).most_common())},
        "brand_suffix": find_brand_suffix([p["title"] for p in pages]),
        "site_click_rate_by_position": band_median,
        "rewrite_queue": [p["url"] for p in flagged[:queue_size]],
        "pages": pages,
        "thresholds": dict(T, rewrite_queue_size=queue_size),
        "notes": notes,
    }

