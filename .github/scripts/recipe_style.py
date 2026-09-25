#!/usr/bin/env python3
"""Deterministic formatter for the recipe style described in submit-worker/recipe-style.json."""

import collections
import json
import re
from pathlib import Path


REPO = Path(__file__).resolve().parents[2]
STYLE = json.loads((REPO / "submit-worker/recipe-style.json").read_text(encoding="utf-8"))
UNICODE_FRACTIONS = {
    "¼": " 1/4", "½": " 1/2", "¾": " 3/4", "⅓": " 1/3", "⅔": " 2/3", "⅛": " 1/8",
    "⅜": " 3/8", "⅝": " 5/8", "⅞": " 7/8", "⅕": " 1/5", "⅙": " 1/6", "⅚": " 5/6",
}
NUMBER_RE = re.compile(r"\d+(?:[./]\d+)?")
LIST_MARKER_RE = re.compile(r"^\s*(?:\d+[.)]|[-*•])\s+", re.MULTILINE)
WORD_RE = re.compile(r"[A-Za-z]+(?:[’'][A-Za-z]+)?")
LINK_RE = re.compile(r"\]\([^)]*\)|https?://\S+")
QUANTITY = r"(?:\d+(?:[./]\d+)?|[¼½¾⅓⅔⅛⅜⅝⅞])"
PREPARATIONS = tuple(STYLE["ingredient_line"]["preparation_words"])
ACRONYMS = {acronym.lower(): acronym for acronym in STYLE["acronyms"]}
SPELLING = {noun.lower(): noun for noun in STYLE["proper_nouns"] + STYLE["acronyms"] + list(STYLE["spelling"].values())}
SPELLING.update(STYLE["spelling"])
FIRST_PERSON_RE = re.compile(
    r"\b(?:" + "|".join(map(re.escape, STYLE["first_person"]["rejected_in_ingredients"])) + r")\b", re.I)


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
    particles = set(STYLE["title"]["particles"])
    positions = {match.start(): index for index, match in enumerate(words)}

    def replace(match):
        word = match.group(0)
        lowered = word.lower()
        index = positions[match.start()]
        if lowered in ACRONYMS:
            return ACRONYMS[lowered]
        if _mixed_case(word) or (index > 1 and words[index - 1].group(0).lower() in particles):
            return word
        if lowered in particles and index > 0:
            return lowered
        if lowered in minor_words and index not in (0, len(words) - 1):
            return lowered
        return lowered[:1].upper() + lowered[1:]

    return WORD_RE.sub(replace, value)


def _mixed_case(word):
    return word[1:] != word[1:].lower() and word != word.upper()


def _lowercase(value):
    return re.sub(r"[A-Za-z’']+", lambda match: match.group(0) if _mixed_case(match.group(0)) else match.group(0).lower(),
                  value)


def _unit_pattern():
    aliases = sorted({alias for unit in STYLE["units"].values() for alias in unit["aliases"]},
                     key=len, reverse=True)
    return re.compile(r"\b(" + "|".join(re.escape(alias) for alias in aliases) + r")(?:\.(?=(?-i:\s+[a-z\d(\[])))?(?![\w-])", re.I)


UNIT_PATTERN = _unit_pattern()


def _style_unit(match, text):
    alias = match.group(1).lower()
    unit = next(spec for spec in STYLE["units"].values() if alias in spec["aliases"])
    preceding = text[:match.start()]
    quantity = re.search(rf"({QUANTITY}(?:\s*-?\s*{QUANTITY})?)\s*$", preceding)
    if not quantity:
        return match.group(0)
    if quantity.group(1) in {"1", *STYLE["fractions"]["singular"]}:
        return unit["canonical"]
    return unit["plural"]


def _restore_spelling(value):
    for incorrect, corrected in SPELLING.items():
        value = re.sub(r"(?<!\w)" + re.escape(incorrect) + r"(?!\w)", corrected, value, flags=re.I)
    return value


def _outside_links(value, transform):
    parts = LINK_RE.split(value)
    links = LINK_RE.findall(value) + [""]
    return "".join(transform(part) + link for part, link in zip(parts, links))


def _style_units_and_spelling(value):
    value = UNIT_PATTERN.sub(lambda match: _style_unit(match, value), value)
    return _restore_spelling(value)


def normalize_ingredient(value):
    """Normalize units, capitalization and clear trailing preparation wording."""
    before = value
    # Preserve attempted Markdown control text for render_recipe() to escape visibly.
    if re.match(r"\s*\\?(?:[#>{\[!`]|\d+\\?[.)]\s+)", value):
        return value
    value = " ".join(value.strip().split())
    value = _outside_links(value, lambda part: _style_units_and_spelling(re.sub(r"\bi\b(?!\.)", "I", _lowercase(part))))
    value = re.sub(rf"^({QUANTITY}\s+(?:Tbsp|tsp))\s+of\s+(?!(?:the|a|an|each|your)\b)", r"\1 ", value)
    if "," not in value:
        value = re.sub(r"\s+(" + "|".join(PREPARATIONS) + r")$", r", \1", value)
    if numbers(before) != numbers(value):
        raise ValueError("formatting-changed-numbers")
    return value


def is_first_person(value):
    """Return whether an ingredient line uses a first-person word that a reviewer should check."""
    return bool(FIRST_PERSON_RE.search(value))


def normalize_text(value):
    """Normalize style-owned units and spelling without changing sentence case."""
    before = value
    value = _outside_links(value, _style_units_and_spelling)
    if numbers(before) != numbers(value):
        raise ValueError("formatting-changed-numbers")
    return value


def normalize_markdown(text, first_person=None):
    """Normalize a recipe without changing numbers; collect first-person ingredient lines into first_person."""
    before = text
    lines = text.splitlines()
    in_ingredients = False
    body = 0
    if lines and lines[0] == "---":
        body = next((index + 1 for index in range(1, len(lines)) if lines[index] == "---"), len(lines))
    for index, line in enumerate(lines[body:], body):
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
                if first_person is not None and is_first_person(item.group(2)):
                    first_person.append((index + 1, line.strip()))
                lines[index] = item.group(1) + normalize_ingredient(item.group(2))
                continue
        if not line.lstrip().startswith(("![", "*Submitted by")):
            lines[index] = normalize_text(line)
    result = "\n".join(lines) + ("\n" if text.endswith("\n") else "")
    if numbers(before) != numbers(result):
        raise ValueError("formatting-changed-numbers")
    return result
