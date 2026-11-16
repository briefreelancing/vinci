"""Small text helpers: tokens, a light stemmer, intent rules, question detection."""

from __future__ import annotations

import re

STOPWORDS = {
    "a", "an", "the", "and", "or", "of", "for", "to", "in", "on", "at", "by", "with", "from", "is", "are",
    "be", "do", "does", "can", "i", "my", "me", "you", "your", "it", "this", "that", "how", "what", "why",
    "when", "where", "who", "which", "should", "will", "vs", "versus", "make", "making", "much", "many",
}
QUESTION_STARTS = {"how", "what", "why", "when", "where", "who", "which", "can", "does", "do", "is",
                   "are", "should", "will"}

# Checked in this order; the first rule that matches wins.
INTENT_RULES: list[tuple[str, set[str]]] = [
    ("local", {"near", "nearby", "nearest", "open now", "delivery"}),
    ("transactional", {"buy", "order", "price", "prices", "pricing", "cost", "costs", "cheap", "deal", "deals",
                       "coupon", "discount", "sale", "hire", "quote", "book", "booking", "shop", "purchase"}),
    ("commercial", {"best", "top", "review", "reviews", "compare", "comparison", "alternative", "alternatives",
                    "vs", "versus"}),
    ("informational", {"how", "what", "why", "when", "who", "which", "guide", "tutorial", "tips", "ideas",
                       "examples", "example", "meaning", "definition", "recipe", "recipes", "learn"}),
]
EXPORT_INTENTS = {"informational", "commercial", "transactional", "navigational", "local"}


def words(text: str) -> list[str]:
    return re.findall(r"[^\W_]+", str(text or "").lower(), flags=re.UNICODE)


def stem(word: str) -> str:
    """Fold plurals only. Deliberately light: it must never merge unrelated words."""
    if len(word) > 4 and word.endswith("ies"):
        return word[:-3] + "y"
    if len(word) > 4 and word.endswith(("xes", "ches", "shes", "sses")):
        return word[:-2]
    if len(word) > 3 and word.endswith("s") and not word.endswith(("ss", "us", "is")):
        return word[:-1]
    return word


def tokens(text: str) -> frozenset[str]:
    """Meaningful stemmed words. Falls back to all words if only stopwords remain."""
    ws = words(text)
    kept = [stem(w) for w in ws if w not in STOPWORDS]
    return frozenset(kept or [stem(w) for w in ws])


MODIFIERS = frozenset({"near", "nearby", "nearest", "best", "top", "online"})


def core_tokens(text: str) -> frozenset[str]:
    """Tokens without search modifiers such as 'near me' or 'best', which rarely belong in a title."""
    t = tokens(text)
    return (t - MODIFIERS) or t


def is_question(keyword: str) -> bool:
    ws = words(keyword)
    return bool(ws) and ws[0] in QUESTION_STARTS


def classify_intent(keyword: str, from_export: str | None, brand_terms: list[str]) -> tuple[str, str]:
    """Return (intent, source). Source says whether it came from the export or from a word rule."""
    if from_export:
        first = re.split(r"[,/;|]", from_export)[0].strip().lower()
        if first in EXPORT_INTENTS:
            return first, "export"
    lowered = " " + " ".join(words(keyword)) + " "
    for term in brand_terms:
        if term and f" {' '.join(words(term))} " in lowered:
            return "navigational", "brand term"
    for intent, cues in INTENT_RULES:
        if any(f" {cue} " in lowered for cue in cues):
            return intent, "word rule"
    return "unclassified", "no rule matched"


def slug(text: str, limit: int = 50) -> str:
    return "-".join(words(text))[:limit].strip("-") or "untitled"
