"""Group keywords into topics a writer can cover in one piece.

Method: keywords are taken from highest to lowest demand. Each one joins the
existing group whose lead keyword shares enough meaningful words with it
(Jaccard overlap at or above the threshold); otherwise it starts a new group.
The lead keyword is therefore always the highest-demand keyword in its group.

This is word overlap, not search-result overlap: synonyms are not merged
automatically. Use merges to join groups a human knows belong together.
"""

from __future__ import annotations

from collections import Counter, defaultdict

from .load import Loaded, norm_url
from .audit import find_brand_suffix
from .text import classify_intent, core_tokens, is_question, tokens

THRESHOLDS = {
    "cluster_word_overlap": 0.5,
    "page_match_word_coverage": 0.75,
    "brief_queue_size": 15,
}


def _r1(x: float | None) -> float | None:
    return None if x is None else round(float(x), 1)


def _intish(x: float | None):
    if x is None:
        return None
    return int(x) if float(x).is_integer() else round(float(x), 1)


def dedupe(keywords: list[dict]) -> tuple[list[dict], int]:
    best: dict[str, dict] = {}
    for k in keywords:
        key = k["keyword"].lower()
        if key not in best or (k["demand"] or 0) > (best[key]["demand"] or 0):
            best[key] = k
    return list(best.values()), len(keywords) - len(best)


def group(keywords: list[dict], threshold: float) -> list[list[dict]]:
    order = sorted(keywords, key=lambda k: (-(k["demand"] or 0), k["keyword"].lower()))
    groups: list[list[dict]] = []
    lead_tokens: list[frozenset] = []
    index: dict[str, set[int]] = defaultdict(set)
    for k in order:
        t = k["tokens"]
        best, best_score = None, 0.0
        for gid in sorted({g for tok in t for g in index[tok]}):
            lead = lead_tokens[gid]
            score = len(t & lead) / len(t | lead)
            if score > best_score:
                best, best_score = gid, score
        if best is not None and best_score >= threshold:
            groups[best].append(k)
        else:
            groups.append([k])
            lead_tokens.append(t)
            for tok in t:
                index[tok].add(len(groups) - 1)
    return groups


def apply_merges(groups: list[list[dict]], merges: list[tuple[str, str]]) -> tuple[list[list[dict]], list[str]]:
    notes = []
    for a, b in merges:
        find = lambda kw: next((i for i, g in enumerate(groups)  # noqa: E731
                                if any(k["keyword"].lower() == kw.lower() for k in g)), None)
        ia, ib = find(a), find(b)
        if ia is None or ib is None:
            notes.append(f"merge skipped: '{a if ia is None else b}' is not in the keyword list")
            continue
        if ia != ib:
            groups[ia].extend(groups[ib])
            del groups[ib]
    return groups, notes


def _match_page(lead: frozenset, pages: list[dict]) -> dict | None:
    """Best existing page for a topic, judged by words shared with its title, H1 and URL."""
    best, best_cov = None, 0.0
    for p in pages:
        cov = len(lead & p["tokens"]) / len(lead) if lead else 0.0
        if cov > best_cov or (cov == best_cov and best and len(p["title"]) < len(best["title"])):
            best, best_cov = p, cov
    if best and best_cov >= THRESHOLDS["page_match_word_coverage"]:
        return {"url": best["url"], "title": best["title"],
                "matched_by": "words shared with the page title, H1 or URL (a suggestion, confirm it)"}
    return None


def build(loaded: Loaded, brand_terms: list[str], threshold: float | None = None,
          merges: list[tuple[str, str]] | None = None, queue_size: int | None = None) -> dict:
    threshold = threshold if threshold is not None else THRESHOLDS["cluster_word_overlap"]
    queue_size = queue_size or THRESHOLDS["brief_queue_size"]
    keywords, dupes = dedupe(loaded.keywords)
    for k in keywords:
        k["tokens"] = tokens(k["keyword"])
        k["intent"], k["intent_source"] = classify_intent(k["keyword"], k["intent_from_export"], brand_terms)
    groups, notes = apply_merges(group(keywords, threshold), merges or [])
    suffix = (find_brand_suffix([p["title"] for p in loaded.pages]) or {}).get("text", "")
    bare = lambda t: t[: -len(suffix)] if suffix and t.endswith(suffix) else t  # noqa: E731
    pages = [{**p, "tokens": tokens(" ".join([bare(p["title"]), p["h1"],
                                              p["url"].split("//")[-1].partition("/")[2]]))}
             for p in loaded.pages]
    by_url = {norm_url(p["url"]): p for p in loaded.pages}

    clusters = []
    for g in groups:
        g.sort(key=lambda k: (-(k["demand"] or 0), k["keyword"].lower()))
        total = sum(k["demand"] or 0 for k in g)
        weights = Counter()
        for k in g:
            weights[k["intent"]] += (k["demand"] or 0) if total else 1
        denom = sum(weights.values()) or 1
        mix = {i: _r1(100.0 * w / denom) for i, w in sorted(weights.items(), key=lambda x: (-x[1], x[0]))}
        diffs = [k["difficulty"] for k in g if k["difficulty"] is not None]
        ranked = [k for k in g if k["position"] is not None and k["url"]]
        existing = None
        if ranked:
            top = min(ranked, key=lambda k: k["position"])
            page = by_url.get(norm_url(top["url"]))
            existing = {"url": top["url"], "title": page["title"] if page else None,
                        "matched_by": "the URL already ranking for this topic in the keyword export",
                        "best_position": _r1(top["position"])}
        elif pages:
            existing = _match_page(core_tokens(g[0]["keyword"]), pages)
        lead_tokens = g[0]["tokens"]
        extra = Counter(tok for k in g[1:] for tok in k["tokens"] - lead_tokens)
        clusters.append({
            "primary_keyword": g[0]["keyword"],
            "total_demand": _intish(total),
            "keyword_count": len(g),
            "intent": next(iter(mix)),
            "intent_mix_pct": mix,
            "average_difficulty": _r1(sum(diffs) / len(diffs)) if diffs else None,
            "action": "refresh existing page" if existing else "new page",
            "existing_page": existing,
            "questions": [k["keyword"] for k in g if is_question(k["keyword"])],
            "common_modifiers": [tok for tok, _ in extra.most_common(8)],
            "keywords": [{"keyword": k["keyword"], "demand": _intish(k["demand"]),
                          "difficulty": _r1(k["difficulty"]), "intent": k["intent"],
                          "intent_source": k["intent_source"], "position": _r1(k["position"]),
                          "url": k["url"]} for k in g],
        })
    clusters.sort(key=lambda c: (-(c["total_demand"] or 0), c["primary_keyword"].lower()))
    for i, c in enumerate(clusters, 1):
        c["id"] = i
    rule_based = sum(1 for k in keywords if k["intent_source"] != "export")
    if rule_based:
        notes.append(f"{rule_based} of {len(keywords)} keywords had no intent in the export; intent was set by "
                     "simple word rules, or left unclassified when no rule matched")
    if dupes:
        notes.append(f"{dupes} duplicate keyword(s) removed; the highest demand value was kept")
    return {
        "demand_type": loaded.demand_type or "none",
        "totals": {"keywords": len(keywords), "clusters": len(clusters),
                   "total_demand": _intish(sum(k["demand"] or 0 for k in keywords)),
                   "refresh_existing_page": sum(1 for c in clusters if c["existing_page"]),
                   "new_page": sum(1 for c in clusters if not c["existing_page"])},
        "brief_queue": [c["id"] for c in clusters[:queue_size]],
        "clusters": clusters,
        "site_urls": [p["url"] for p in loaded.pages],
        "thresholds": dict(THRESHOLDS, cluster_word_overlap=threshold, brief_queue_size=queue_size),
        "notes": notes,
    }
