"""Gatekeeper: nothing is rendered until the written work agrees with the calculated data.

Errors block the render. Warnings are shown but do not block.
The number check proves a number exists in the data for that topic. It cannot
prove the number is attached to the right claim, so read the result once.
"""

from __future__ import annotations

import re

from .load import norm_url
from .text import core_tokens, tokens

FACT_FIELDS = ("summary", "search_intent")  # fields where every number must trace to the data


def _numbers_in(obj) -> set[float]:
    found: set[float] = set()
    if isinstance(obj, bool):
        return found
    if isinstance(obj, (int, float)):
        found.add(round(float(obj), 1))
    elif isinstance(obj, dict):
        for v in obj.values():
            found |= _numbers_in(v)
    elif isinstance(obj, list):
        for v in obj:
            found |= _numbers_in(v)
    return found


def untraceable_numbers(text: str, allowed: set[float], ignore_phrases: list[str]) -> list[str]:
    cleaned = str(text or "")
    for phrase in sorted(ignore_phrases, key=len, reverse=True):
        cleaned = re.sub(re.escape(phrase), " ", cleaned, flags=re.I)
    cleaned = re.sub(r"https?://\S+", " ", cleaned)
    bad = []
    for raw in re.findall(r"(?<![\w.])\d[\d,]*(?:\.\d+)?", cleaned):
        try:
            value = round(float(raw.replace(",", "")), 1)
        except ValueError:
            continue
        if value not in allowed:
            bad.append(raw)
    return bad


def check_briefs(clusters: dict, briefs: dict, title_max: int = 60,
                 desc_min: int = 70, desc_max: int = 155) -> tuple[list[str], list[str]]:
    errors, warnings = [], []
    by_id = {c["id"]: c for c in clusters["clusters"]}
    site = {norm_url(u) for u in clusters.get("site_urls", [])}
    file_numbers = _numbers_in(clusters["totals"])
    seen = set()
    items = briefs.get("briefs", [])
    if not items:
        errors.append("no briefs found: the file needs a 'briefs' list")
    for n, b in enumerate(items, 1):
        cid = b.get("cluster_id")
        tag = f"brief {n} (cluster {cid})"
        c = by_id.get(cid)
        if c is None:
            errors.append(f"{tag}: cluster_id is not in clusters.json")
            continue
        if cid in seen:
            errors.append(f"{tag}: this cluster already has a brief")
        seen.add(cid)
        if str(b.get("primary_keyword", "")).strip().lower() != c["primary_keyword"].lower():
            errors.append(f"{tag}: primary_keyword must be '{c['primary_keyword']}'")
        known = {k["keyword"].lower() for k in c["keywords"]}
        for kw in b.get("target_keywords", []):
            if kw.strip().lower() not in known:
                errors.append(f"{tag}: target keyword '{kw}' is not in this cluster")
        if not b.get("target_keywords"):
            errors.append(f"{tag}: list at least one target keyword")
        title = str(b.get("working_title", "")).strip()
        if not title:
            errors.append(f"{tag}: working_title is missing")
        elif len(title) > title_max:
            errors.append(f"{tag}: working_title is {len(title)} characters; the limit is {title_max}")
        desc = str(b.get("meta_description", "")).strip()
        if len(desc) > desc_max:
            errors.append(f"{tag}: meta_description is {len(desc)} characters; the limit is {desc_max}")
        elif desc and len(desc) < desc_min:
            warnings.append(f"{tag}: meta_description is {len(desc)} characters; aim for at least {desc_min}")
        for link in b.get("internal_links", []):
            url = link.get("url", "") if isinstance(link, dict) else link
            if not site:
                errors.append(f"{tag}: internal link '{url}' cannot be verified without a site crawl; remove it")
            elif norm_url(url) not in site:
                errors.append(f"{tag}: internal link '{url}' is not a page in the crawl")
        if len(b.get("outline", [])) < 3:
            warnings.append(f"{tag}: the outline has fewer than 3 headings")
        allowed = _numbers_in(c) | file_numbers
        phrases = [k["keyword"] for k in c["keywords"]]
        for field in FACT_FIELDS:
            for raw in untraceable_numbers(b.get(field, ""), allowed, phrases):
                errors.append(f"{tag}: the number {raw} in '{field}' is not in the data for this cluster")
    return errors, warnings


def check_rewrites(audit: dict, rewrites: dict) -> tuple[list[str], list[str]]:
    errors, warnings = [], []
    T = audit["thresholds"]
    pages = {norm_url(p["url"]): p for p in audit["pages"]}
    suffix = (audit.get("brand_suffix") or {}).get("text")
    items = rewrites.get("rewrites", [])
    if not items:
        errors.append("no rewrites found: the file needs a 'rewrites' list")
    rewritten = {norm_url(r.get("url", "")) for r in items}
    kept_titles = {p["title"].lower() for k, p in pages.items() if k not in rewritten and p["title"]}
    kept_descs = {p["description"].lower() for k, p in pages.items() if k not in rewritten and p["description"]}
    new_titles: dict[str, str] = {}
    new_descs: dict[str, str] = {}
    for r in items:
        url = r.get("url", "")
        page = pages.get(norm_url(url))
        if page is None:
            errors.append(f"{url}: not a page in the audit")
            continue
        title = str(r.get("new_title", "")).strip()
        desc = str(r.get("new_description", "")).strip()
        if not str(r.get("reason", "")).strip():
            errors.append(f"{url}: add a reason so the reviewer knows why the change is proposed")
        if not title and not desc:
            errors.append(f"{url}: give a new_title, a new_description, or both")
        elif not title and any(i.startswith("title_") or i == "low_click_rate" for i in page["issues"]):
            warnings.append(f"{url}: the title has an issue but no new title was written")
        if title:
            if len(title) > T["title_max_chars"]:
                errors.append(f"{url}: new title is {len(title)} characters; the limit is {T['title_max_chars']}")
            elif len(title) < T["title_min_chars"]:
                warnings.append(f"{url}: new title is {len(title)} characters; aim for at least {T['title_min_chars']}")
            if title.lower() in kept_titles:
                errors.append(f"{url}: new title is already used by another page")
            if title.lower() in new_titles:
                errors.append(f"{url}: new title is the same as the one proposed for {new_titles[title.lower()]}")
            new_titles[title.lower()] = url
            if title == page["title"]:
                warnings.append(f"{url}: new title is the same as the current title")
            target = page.get("target_keyword")
            if target and not core_tokens(target) <= tokens(title) and not str(r.get("keyword_waived", "")).strip():
                errors.append(f"{url}: new title does not contain the target keyword '{target}' "
                              "(or give a reason in keyword_waived)")
            top = page["top_queries"][0]["query"] if page.get("top_queries") else None
            if top and not target and not tokens(top) <= tokens(title):
                warnings.append(f"{url}: new title does not contain the page's top query '{top}'")
            if suffix and page["title"].endswith(suffix) and not title.endswith(suffix):
                warnings.append(f"{url}: new title drops the site's usual ending '{suffix.strip()}'")
        if desc:
            if len(desc) > T["description_max_chars"]:
                errors.append(f"{url}: new description is {len(desc)} characters; "
                              f"the limit is {T['description_max_chars']}")
            elif len(desc) < T["description_min_chars"]:
                warnings.append(f"{url}: new description is {len(desc)} characters; "
                                f"aim for at least {T['description_min_chars']}")
            if desc.lower() in kept_descs:
                errors.append(f"{url}: new description is already used by another page")
            if desc.lower() in new_descs:
                errors.append(f"{url}: new description is the same as the one proposed for {new_descs[desc.lower()]}")
            new_descs[desc.lower()] = url
        elif any(i.startswith("description_") for i in page["issues"]):
            warnings.append(f"{url}: the description has an issue but no new description was written")
    return errors, warnings
