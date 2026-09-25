#!/usr/bin/env python3
"""Deterministic formatter for the recipe style described in recipe-style.json."""

import collections
import json
import re
from pathlib import Path


REPO = Path(__file__).resolve().parents[2]
STYLE = json.loads((REPO / "recipe-style.json").read_text(encoding="utf-8"))
UNICODE_FRACTIONS = {
    "¼": " 1/4", "½": " 1/2", "¾": " 3/4", "⅓": " 1/3", "⅔": " 2/3", "⅛": " 1/8",
    "⅜": " 3/8", "⅝": " 5/8", "⅞": " 7/8", "⅕": " 1/5", "⅙": " 1/6", "⅚": " 5/6",
}
NUMBER_RE = re.compile(r"\d+(?:[./]\d+)?")
LIST_MARKER_RE = re.compile(r"^\s*(?:\d+[.)]|[-*•])\s+", re.MULTILINE)
WORD_RE = re.compile(r"[A-Za-z]+(?:[’'][A-Za-z]+)?")
PREPARATIONS = tuple(STYLE["ingredient_line"]["preparation_words"])


def numbers(text):
    """Return numeric tokens in a JSON-friendly multiset, ignoring list markers."""
    text = LIST_MARKER_RE.sub("", text)
    text = text.translate(str.maketrans(UNICODE_FRACTIONS)).replace("⁄", "/")
    return dict(sorted(collections.Counter(NUMBER_RE.findall(text)).items()))


def normalize_title(value):
    """Return the JSON-defined title case without removing punctuation."""
    value = _restore_spelling(" ".join(value.split()))
    words = list(WORD_RE.finditer(value))
    if not words:
        return value
    minor_words = set(STYLE["title"]["minor_words"])
    positions = {match.start(): index for index, match in enumerate(words)}

    def replace(match):
        word = match.group(0)
        lowered = word.lower()
        index = positions[match.start()]
        if (match.start() > 0 and value[match.start() - 1] == "/") or \
                (match.end() < len(value) and value[match.end()] == "/"):
            return lowered
        if lowered in minor_words and index not in (0, len(words) - 1):
            return lowered
        return lowered[:1].upper() + lowered[1:]

    return WORD_RE.sub(replace, value)


def _unit_pattern():
    aliases = sorted({alias for unit in STYLE["units"].values() for alias in unit["aliases"]},
                     key=len, reverse=True)
    return re.compile(r"\b(" + "|".join(re.escape(alias) for alias in aliases) + r")\.?(?![\w-])", re.I)


UNIT_PATTERN = _unit_pattern()


def _style_unit(match, text):
    alias = match.group(1).lower()
    unit = next(spec for spec in STYLE["units"].values() if alias in spec["aliases"])
    preceding = text[:match.start()]
    quantity = re.search(r"([\d¼½¾⅓⅔⅛⅜⅝⅞]+(?:\s+[\d¼½¾⅓⅔⅛⅜⅝⅞/.-]+)?)\s*$", preceding)
    if unit["canonical"] != unit["plural"] and quantity:
        singular = quantity.group(1) in {"1", *STYLE["fractions"]["accepted"]}
        return unit["canonical"] if singular else unit["plural"]
    return unit["canonical"]


def _restore_spelling(value):
    for incorrect, corrected in STYLE["spelling"].items():
        value = re.sub(r"(?<!\w)" + re.escape(incorrect) + r"(?!\w)", corrected, value, flags=re.I)
    return value


def normalize_ingredient(value):
    """Normalize units, capitalization and clear trailing preparation wording."""
    before = value
    # Preserve attempted Markdown control text for render_recipe() to escape visibly.
    if re.match(r"\s*(?:[#>{\[!`]|\d+[.)]\s+)", value):
        return value
    value = " ".join(value.strip().split()).lower()
    value = UNIT_PATTERN.sub(lambda match: _style_unit(match, value), value)
    value = re.sub(r"\b(Tbsp|tsp)\s+of\s+", r"\1 ", value)
    value = _restore_spelling(value)
    preparation = "|".join(PREPARATIONS)
    value = re.sub(r"(?<![,])\s+(" + preparation + r")$", r", \1", value)
    if numbers(before) != numbers(value):
        raise ValueError("recipe formatting must not change numbers")
    return value


def normalize_text(value):
    """Normalize style-owned units and spelling without changing sentence case."""
    before = value
    value = UNIT_PATTERN.sub(lambda match: _style_unit(match, value), value)
    value = re.sub(r"\b(Tbsp|tsp)\s+of\s+", r"\1 ", value)
    value = _restore_spelling(value)
    if numbers(before) != numbers(value):
        raise ValueError("recipe formatting must not change numbers")
    return value


def normalize_markdown(text):
    """Normalize recipe headings, titles and ingredient-list layout without changing numbers."""
    before = text
    lines = text.splitlines()
    in_ingredients = False
    for index, line in enumerate(lines):
        heading = re.fullmatch(r"(#{1,6})\s+(.+?)\s*", line)
        if heading:
            level, value = heading.groups()
            lowered = value.casefold()
            if level == "#":
                lines[index] = f"# {normalize_title(value)}"
            elif level == "##" and lowered in STYLE["headings"]:
                lines[index] = f"## {STYLE['headings'][lowered]}"
            elif level == "###" and in_ingredients:
                lines[index] = f"### {normalize_title(value)}"
            if level == "##":
                in_ingredients = lowered == "ingredients"
            continue
        if in_ingredients:
            item = re.fullmatch(r"(\s*-\s+)(.+?)\s*", line)
            if item:
                lines[index] = item.group(1) + normalize_ingredient(item.group(2))
                continue
        if not line.lstrip().startswith("!["):
            lines[index] = normalize_text(line)
    result = "\n".join(lines) + ("\n" if text.endswith("\n") else "")
    if numbers(before) != numbers(result):
        raise ValueError("recipe formatting must not change numbers")
    return result
