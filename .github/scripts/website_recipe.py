#!/usr/bin/env python3
"""
Turn a website recipe-submission issue into a recipe page for captain review.

The model only normalizes text and picks one of the existing categories through a
strict JSON schema. It runs behind the submission Worker's /draft endpoint
(submit-worker/src/index.js), which holds the instructions and schema and accepts
only this workflow's GitHub OIDC token. The model gets no tools, no repository token
and no secrets. This code
chooses the path, folder and tags, renders the Markdown, and updates navigation and
the Authors page. Every failure exits non-zero with a fixed reason code so the
workflow can comment on the issue and leave it open for manual handling.
"""

import collections
import json
import os
import re
import sys
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import link_import  # noqa: E402
import recipe_style  # noqa: E402
from create_recipe import sanitize_filename  # noqa: E402
from update_mkdocs import add_recipe_to_nav  # noqa: E402

MARKER = "## Website recipe submission"
TITLE_PREFIX = "[Website submission]"

# Category name -> (folder, tags). Mirrors create_recipe.py, update_mkdocs.py and
# CATEGORIES in submit-worker/src/index.js (the model's schema enum).
CATEGORIES = {
    "Appetizers & Dips": ("appetizers_and_dips", ["appetizers", "dips"]),
    "Main Courses": ("main_courses", ["main-course", "entree"]),
    "Sides & Soups": ("sides_and_soups", ["sides", "soups"]),
    "Desserts": ("desserts", ["desserts", "sweets"]),
    "Beverages": ("beverages", ["beverages", "drinks"]),
    "Sauces & Condiments": ("sauces_and_condiments", ["sauces", "condiments"]),
    "Breakfast": ("breakfast", ["breakfast"]),
    "Breads & Extras": ("breads_and_extras", ["breads", "baking"]),
}

# Mirrors MAX_LENGTHS in submit-worker/src/index.js.
MAX_LENGTHS = {
    "Recipe Name": 120,
    "Ingredients": 12_000,
    "Recipe": 12_000,
    "Submitted By": 80,
    "Source link": 2_048,
}
REQUIRED = ["Recipe Name", "Ingredients", "Recipe", "Submitted By"]
OPTIONAL = ["Source link"]

MODEL_NAME = "gpt-5.6-luna"
# The keys of the Worker's strict recipe schema. The Worker validates the output
# against the schema; validate_output() checks it again here.
OUTPUT_KEYS = {"title", "category", "steps", "notes", "warnings"}
# A page-text-only import also returns the ingredient lines copied from the page.
PAGE_OUTPUT_KEYS = OUTPUT_KEYS | {"ingredients"}
PAGE_INGREDIENTS_NOTE = "Ingredients extracted from page text - check against the source."
# Fixed reasons the Worker returns; anything else is reported as a request failure.
WORKER_REASONS = {"model-refused", "model-incomplete", "model-invalid-output", "model-request-failed"}


class IntakeError(Exception):
    """A submission that must be handled by a person. The message is a fixed reason."""

    site = ""  # the linked page's host, for a failure comment naming it


# --- Issue parsing -----------------------------------------------------------


def parse_issue(title, body):
    """Return the submitted fields from a website issue, or raise IntakeError."""
    if not (title or "").startswith(TITLE_PREFIX):
        raise IntakeError("not-website-issue")
    body = (body or "").replace("\r\n", "\n")
    if not body.startswith(MARKER + "\n"):
        raise IntakeError("not-website-issue")

    fields = {}
    # Each field is "### Heading", a blank line, then a text fence longer than any
    # backtick run in the value (see fenced() in submit-worker/src/index.js).
    pattern = re.compile(
        r"^### (?P<heading>[^\n]+)\n\n(?P<fence>`{3,})text\n(?P<value>.*?)\n(?P=fence)$",
        re.MULTILINE | re.DOTALL,
    )
    for match in pattern.finditer(body):
        heading = match.group("heading").strip()
        if heading not in REQUIRED + OPTIONAL or heading in fields:
            raise IntakeError("unexpected-issue-format")
        fields[heading] = match.group("value").strip()

    for heading in REQUIRED:
        if heading not in fields:
            raise IntakeError("unexpected-issue-format")
    if not fields["Recipe Name"]:
        raise IntakeError("missing-required-field")
    # With a link, ingredients and steps may be left for link import to fill.
    if not (fields["Ingredients"] and fields["Recipe"]) and not source_link(fields):
        raise IntakeError("missing-required-field")
    for heading, value in fields.items():
        if len(value) > MAX_LENGTHS[heading]:
            raise IntakeError("field-too-long")
    return fields


def source_link(fields):
    """The raw submitted link, or empty when none was given."""
    value = fields.get("Source link", "").strip()
    return "" if value.lower() == "not provided" else value


# --- Link import ------------------------------------------------------------------


def import_link(fields, fetch):
    """Fill missing ingredients and steps from the linked page. Returns how."""
    try:
        page = fetch(source_link(fields))
    except link_import.FetchError as error:
        failure = IntakeError(str(error))
        failure.site = urllib.parse.urlsplit(source_link(fields)).hostname or ""
        raise failure from None
    found = link_import.recipe_from_json_ld(page)
    if found:
        fields["Ingredients"] = fields["Ingredients"] or found[0]
        fields["Recipe"] = fields["Recipe"] or found[1]
        # Same limits as typed text, so a huge page cannot flood the model.
        if any(len(fields[k]) > MAX_LENGTHS[k] for k in ("Ingredients", "Recipe")):
            raise IntakeError("field-too-long")
        return "schema.org Recipe data"
    # No recipe data: the model reads the page text, as untrusted data.
    fields["Page text"] = link_import.visible_text(page)
    if not fields["Page text"]:
        raise IntakeError("link-no-recipe")
    return "page text, read by the model"


# --- Deterministic checks of optional fields -----------------------------------

NAME_RE = re.compile(r"[^\W\d_]+(?:[ .'\-]{1,2}[^\W\d_]+)*\.?")


def clean_submitter(raw, warnings):
    """Return a publishable contributor name, or None when absent or unsafe."""
    name = " ".join((raw or "").split())
    if not name or name.lower() == "not provided":
        return None
    # ponytail: conservative charset keeps the name safe in YAML, tags and the
    # Authors include list; widen it only if real names get rejected.
    if len(name) > MAX_LENGTHS["Submitted By"] or not NAME_RE.fullmatch(name):
        warnings.append(
            "The submitted name contains characters the site cannot publish safely, "
            "so attribution was left out. Check the issue and credit by hand if wanted."
        )
        return None
    return name


def check_source(raw, warnings, review_notes):
    """Return an https URL to credit, or None. http is flagged, anything else rejected."""
    value = (raw or "").strip()
    if not value or value.lower() == "not provided":
        return None
    try:
        parts = urllib.parse.urlsplit(value)
        port = parts.port  # raises ValueError on a malformed port
    except ValueError:
        parts, port = None, None
    valid = (
        parts is not None
        and parts.scheme.lower() in ("http", "https")
        and parts.hostname
        and "." in parts.hostname
        and re.fullmatch(r"[a-z0-9.-]+", parts.hostname)
        and not parts.username
        and not parts.password
        and not re.search(r"[\s\x00-\x1f\x7f]", value)
    )
    if not valid:
        warnings.append("The source link was not a valid web address, so it was left out.")
        return None
    netloc = parts.hostname.lower() + (f":{port}" if port else "")
    # Safe normalization only: lowercase scheme and host, percent-encode characters
    # that could end a Markdown link or YAML string.
    unsafe = "()<>\"'`\\[]{}|^ "
    rest = urllib.parse.urlunsplit(("", "", parts.path, parts.query, parts.fragment))
    rest = "".join(urllib.parse.quote(c) if c in unsafe else c for c in rest)
    url = f"{parts.scheme.lower()}://{netloc}{rest}"
    if parts.scheme.lower() == "http":
        review_notes.append(
            "The source link uses plain http, so it was not added to the page. "
            f"Review it and add it by hand if it is trustworthy: `{url}`"
        )
        return None
    return url


# --- Model call ----------------------------------------------------------------


def model_input(fields):
    data = {
        "recipe_name": fields["Recipe Name"],
        "ingredients": fields["Ingredients"],
        "recipe": fields["Recipe"],
    }
    if fields.get("Page text"):
        data["page_text"] = fields["Page text"]
    return data


def call_model(fields, draft_url, token):
    """Ask the Worker's /draft endpoint to draft the recipe. Returns the parsed object."""
    request = urllib.request.Request(
        draft_url,
        # Name and source never reach the model; code renders both.
        data=json.dumps(model_input(fields), ensure_ascii=False).encode("utf-8"),
        # Cloudflare bans urllib's default User-Agent with a 403 (error 1010).
        headers={"Authorization": f"Bearer {token}", "Content-Type": "application/json",
                 "User-Agent": link_import.USER_AGENT},
        method="POST",
    )
    try:
        with urllib.request.urlopen(request, timeout=180) as response:
            return json.load(response)
    except urllib.error.HTTPError as error:
        print(f"Draft request failed with HTTP {error.code}", file=sys.stderr)
        if error.code == 403:
            raise IntakeError("draft-endpoint-unavailable") from None
        try:
            reason = json.load(error).get("error")
        except (ValueError, AttributeError):
            reason = None
        known = isinstance(reason, str) and reason in WORKER_REASONS
        raise IntakeError(reason if known else "model-request-failed") from None
    except (urllib.error.URLError, TimeoutError, json.JSONDecodeError):
        raise IntakeError("model-request-failed") from None


# --- Output validation -----------------------------------------------------------

HTML_TAG_RE = re.compile(r"</?[A-Za-z!?]")
FRONT_MATTER_RE = re.compile(r"^\s*(---|\.\.\.)\s*$", re.MULTILINE)
LIST_MARKER_RE = re.compile(r"^\s*(?:\d+[.)]|[-*•])\s+", re.MULTILINE)
UNICODE_FRACTIONS = {
    "¼": " 1/4", "½": " 1/2", "¾": " 3/4", "⅓": " 1/3", "⅔": " 2/3", "⅛": " 1/8",
    "⅜": " 3/8", "⅝": " 5/8", "⅞": " 7/8", "⅕": " 1/5", "⅙": " 1/6", "⅚": " 5/6",
}
NUMBER_RE = re.compile(r"\d+(?:[./]\d+)?")
NOTE_REF_RE = re.compile(r"\bnotes?\s+\d+", re.IGNORECASE)
INGREDIENT_MARKER_RE = re.compile(r"^\s*(?:[-*•]|\d+[.)])\s+")
INGREDIENT_HEADING_RE = re.compile(r"^\s*(?:#{1,6}\s+)?([^\d][^:]*?):\s*$")
BARE_HEADING_RE = re.compile(r"(?:#{1,6}\s+)?([^\d:]{1,40})")
LEADING_INGREDIENTS_RE = re.compile(r"(?:#{1,6}\s+)?ingredients:?", re.IGNORECASE)


def numbers(text):
    """Multiset of numeric tokens, ignoring list numbering, "note N" references and unicode fraction spelling."""
    text = NOTE_REF_RE.sub("", LIST_MARKER_RE.sub("", text))
    text = text.translate(str.maketrans(UNICODE_FRACTIONS))
    text = text.replace("⁄", "/")  # fraction slash
    return collections.Counter(NUMBER_RE.findall(text))


def ingredient_heading(line, following):
    """The subgroup heading a line names, or None when it is an ingredient line."""
    if INGREDIENT_MARKER_RE.match(line):
        return None
    match = INGREDIENT_HEADING_RE.fullmatch(line)
    if match:
        return match.group(1)
    # A short digit-free line is a heading when list items or "For the ..." mark it as one.
    match = BARE_HEADING_RE.fullmatch(line)
    if match and following and len(match.group(1).split()) <= 5 and (
            INGREDIENT_MARKER_RE.match(following) or line.lower().startswith("for ")):
        return match.group(1)
    return None


def ingredient_groups(ingredients):
    """Use submitted ingredient lines and subgroup headings, normalized only by recipe style."""
    groups, warnings = [], []
    heading, items = "", []

    def finish_group():
        if items:
            groups.append({"heading": heading, "items": list(items)})

    lines = [line.strip() for line in ingredients.splitlines() if line.strip()]
    if lines and LEADING_INGREDIENTS_RE.fullmatch(lines[0]):
        lines = lines[1:]
    for index, line in enumerate(lines):
        found = ingredient_heading(line, lines[index + 1] if index + 1 < len(lines) else "")
        if found:
            finish_group()
            heading, items = recipe_style.normalize_title(found.strip()), []
            continue
        item = INGREDIENT_MARKER_RE.sub("", line)
        item = recipe_style.normalize_ingredient(item)
        if recipe_style.is_first_person(item):
            warnings.append(f"First-person ingredient line to review: {item}")
        items.append(item)
    finish_group()
    return groups, warnings


def from_page(fields):
    """Whether the model must copy the ingredient lines from page text."""
    return bool(fields.get("Page text")) and not fields["Ingredients"]


def validate_output(output, fields):
    """Return a cleaned recipe dict, or raise IntakeError. Never trusts the model."""
    keys = PAGE_OUTPUT_KEYS if from_page(fields) else OUTPUT_KEYS
    if not isinstance(output, dict) or set(output) != keys:
        raise IntakeError("model-invalid-output")
    if output["category"] not in CATEGORIES:
        raise IntakeError("model-invalid-output")

    def text_list(value):
        if not isinstance(value, list) or not all(isinstance(v, str) for v in value):
            raise IntakeError("model-invalid-output")
        return [" ".join(v.split()) for v in value if v.strip()]

    title = output["title"]
    if not isinstance(title, str):
        raise IntakeError("model-invalid-output")
    title = recipe_style.normalize_title(" ".join(title.split()))
    if not title or len(title) > MAX_LENGTHS["Recipe Name"]:
        raise IntakeError("model-invalid-output")

    ingredients = fields["Ingredients"]
    if from_page(fields):
        ingredients = "\n".join(text_list(output["ingredients"]))
        # Copied lines may carry only numbers the page itself shows.
        if numbers(ingredients) - numbers(fields["Page text"]):
            raise IntakeError("model-changed-quantities")
    groups, first_person = ingredient_groups(ingredients)
    steps = [recipe_style.normalize_text(step) for step in text_list(output["steps"])]
    notes = [recipe_style.normalize_text(note) for note in text_list(output["notes"])]
    warnings = text_list(output["warnings"]) + first_person
    if not groups or not steps:
        raise IntakeError("model-empty-recipe")

    published = [title] + [g["heading"] for g in groups]
    published += [i for g in groups for i in g["items"]] + steps + notes
    joined = "\n".join(published)
    if HTML_TAG_RE.search(joined) or FRONT_MATTER_RE.search(joined):
        raise IntakeError("model-unsafe-markup")

    model_text = "\n".join(steps + notes)
    submitted = fields["Recipe"]
    if fields.get("Page text"):
        if numbers(title) - numbers(fields["Recipe Name"] + "\n" + fields["Page text"]):
            raise IntakeError("model-changed-quantities")
        # A page carries other numbers (menus, comments), so every model-written
        # number must appear in the submitted steps or page text at least as often.
        if numbers(model_text) - numbers(submitted + "\n" + fields["Page text"]):
            raise IntakeError("model-changed-quantities")
    elif numbers(title) != numbers(fields["Recipe Name"]) or numbers(model_text) != numbers(submitted):
        raise IntakeError("model-changed-quantities")

    return {
        "title": title,
        "category": output["category"],
        "groups": groups,
        "steps": steps,
        "notes": notes,
        "warnings": warnings,
    }


# --- Rendering -------------------------------------------------------------------

def md_text(value):
    """Escape text so it renders literally: no links, images, HTML, code, attribute
    lists or block markers. `[`, `{` and `<` are the doors; the rest stays readable."""
    value = re.sub(r"([\\`*_{}\[\]])", r"\\\1", value).replace("<", "&lt;")
    value = re.sub(r"^([#>+-])", r"\\\1", value)
    return re.sub(r"^(\d+)([.)])", r"\1\\\2", value)


def yaml_str(value):
    """A double-quoted YAML scalar. Inputs are already single-line and printable."""
    return '"' + value.replace("\\", "\\\\").replace('"', '\\"') + '"'


def nav_title(title):
    """A plain navigation label that is safe as an unquoted YAML key in mkdocs.yml."""
    label = re.sub(r"[^\w &',./()-]", "", title)
    label = " ".join(label.split()).lstrip("&',./()- ")
    return label or "Untitled Recipe"


def render_recipe(recipe, submitter, source):
    """Render the recipe page from validated data."""
    _, category_tags = CATEGORIES[recipe["category"]]
    lines = ["---", "tags:"]
    lines += [f"  - {tag}" for tag in category_tags]
    if submitter:
        lines.append(f"  - {yaml_str('By ' + submitter)}")
    lines.append(f"author: {yaml_str(submitter)}" if submitter else "author:")
    lines.append(f"source: {yaml_str(source)}" if source else "source:")
    lines += ["---", "", f"# {md_text(recipe['title'])}", "", "## Ingredients", ""]

    for group in recipe["groups"]:
        if group["heading"]:
            lines += [f"### {md_text(group['heading'])}", ""]
        lines += [f"- {md_text(item)}" for item in group["items"]]
        lines.append("")

    lines += ["## Instructions", ""]
    lines += [f"{n}. {md_text(step)}" for n, step in enumerate(recipe["steps"], 1)]
    lines.append("")

    if recipe["notes"]:
        lines += ["## Notes", ""]
        lines += [f"- {md_text(note)}" for note in recipe["notes"]]
        lines.append("")

    if source:
        lines += [f"Source: [Original recipe]({source})", ""]
    if submitter:
        lines += [f"*Submitted by: {md_text(submitter)}*", ""]
    return "\n".join(lines)


def add_author(authors_path, submitter):
    """Add "By Name" to the Authors page include list. Returns True if it was new."""
    tag = f"By {submitter}"
    text = Path(authors_path).read_text(encoding="utf-8")
    match = re.search(r"(  include: \[\n)(.*?)(\n  \])", text, re.DOTALL)
    if not match:
        raise IntakeError("authors-page-format")
    entries = re.findall(r'^    "([^"]+)",$', match.group(2), re.MULTILINE)
    if tag in entries:
        return False
    entries = sorted(entries + [tag], key=str.lower)
    body = "\n".join(f'    "{entry}",' for entry in entries)
    Path(authors_path).write_text(text[: match.start(2)] + body + text[match.end(2) :], encoding="utf-8")
    return True


# --- Pull request body -------------------------------------------------------------


def fenced(value):
    longest = max((len(run) for run in re.findall(r"`+", value)), default=0)
    fence = "`" * max(3, longest + 1)
    return f"{fence}text\n{value}\n{fence}"


def pr_body(issue_number, recipe, path, submitter, author_is_new, source,
            warnings, review_notes, imported=None):
    attribution = "none"
    if submitter:
        status = "new author, added to the Authors page" if author_is_new else "existing author"
        attribution = f"By {submitter} ({status})"
    lines = [
        "## Website recipe submission",
        "",
        f"Drafted from website submission #{issue_number} by `{MODEL_NAME}` on Cloudflare "
        "Workers AI. The model rewrote the text in house style and picked the category; "
        "quantities remain unchanged. This workflow rendered the page, navigation and "
        "attribution.",
        "",
        f"- **Page:** `{path}`",
        f"- **Category:** {recipe['category']}",
        f"- **Attribution:** {attribution}",
        f"- **Source:** {'linked (https)' if source else 'none linked'}",
        f"- **Ingredients and steps:** {'read from the linked page (' + imported + ')' if imported else 'as submitted'}",
        "- **Build:** `zensical build --clean` passed before this PR was opened.",
        "",
    ]
    if review_notes or warnings:
        lines += ["## Needs review", ""]
        lines += [f"- {note}" for note in review_notes]
        if warnings:
            lines += ["", "Model and intake warnings (untrusted text, shown verbatim):", ""]
            lines += [fenced("\n".join(f"- {w}" for w in warnings)), ""]
        lines.append("")
    lines += [
        "## Review checklist",
        "",
        "- [ ] Quantities and units match the issue",
        "- [ ] Steps are complete and in order",
        "- [ ] Attribution is correct",
        "- [ ] Source link is correct and appropriate",
        "- [ ] Tags and category fit",
        "- [ ] Navigation placement is right",
        "",
        "Merging closes the issue. Closing this PR without merging leaves the issue open.",
        "",
        f"Closes #{issue_number}",
        "",
    ]
    return "\n".join(lines)


# --- Entry point -------------------------------------------------------------------


def process(issue, model, root=".", fetch=link_import.fetch_page):
    """Build the recipe files from an issue. `model(fields)` returns the raw model object.

    Returns a dict describing the change for the workflow."""
    root = Path(root)
    fields = parse_issue(issue.get("title"), issue.get("body"))
    warnings, review_notes = [], []
    submitter = clean_submitter(fields.get("Submitted By"), warnings)
    source = check_source(fields.get("Source link"), warnings, review_notes)
    imported = None
    if not (fields["Ingredients"] and fields["Recipe"]):
        imported = import_link(fields, fetch)
    if from_page(fields):
        review_notes.append(PAGE_INGREDIENTS_NOTE)

    try:
        recipe = validate_output(model(fields), fields)
    except IntakeError as error:
        # The model found no recipe in the page text: ask the submitter for the text.
        if str(error) == "model-empty-recipe" and fields.get("Page text"):
            raise IntakeError("link-no-recipe") from None
        raise
    warnings += recipe["warnings"]

    folder, _ = CATEGORIES[recipe["category"]]
    title = recipe["title"]
    filename = sanitize_filename(title)
    if list(root.glob(f"docs/recipes/*/{filename}")):
        raise IntakeError("duplicate-recipe")
    relative = f"docs/recipes/{folder}/{filename}"
    (root / "docs/recipes" / folder).mkdir(parents=True, exist_ok=True)
    (root / relative).write_text(render_recipe(recipe, submitter, source), encoding="utf-8")

    add_recipe_to_nav(str(root / "mkdocs.yml"), filename, nav_title(title), recipe["category"], folder)
    author_is_new = bool(submitter) and add_author(root / "docs/authors.md", submitter)

    return {
        "title": title,
        "path": relative,
        "body": pr_body(issue["number"], recipe, relative, submitter,
                        author_is_new, source, warnings, review_notes, imported),
    }


def main():
    out_dir = Path(os.environ["INTAKE_OUT_DIR"])
    out_dir.mkdir(parents=True, exist_ok=True)
    try:
        with open(os.environ["GITHUB_EVENT_PATH"], encoding="utf-8") as f:
            issue = json.load(f)["issue"]
        draft_url = os.environ["RECIPE_DRAFT_URL"]
        token = os.environ["RECIPE_DRAFT_TOKEN"]
        result = process(issue, lambda fields: call_model(fields, draft_url, token))
    except IntakeError as error:
        (out_dir / "failure-reason").write_text(str(error), encoding="utf-8")
        (out_dir / "failure-site").write_text(error.site, encoding="utf-8")
        print(f"Intake failed: {error}", file=sys.stderr)
        sys.exit(1)
    # Untrusted-derived text goes to files, never to GITHUB_OUTPUT or the shell.
    (out_dir / "pr-title").write_text(f"Add recipe: {result['title']}", encoding="utf-8")
    (out_dir / "pr-body.md").write_text(result["body"], encoding="utf-8")
    print(f"Created {result['path']}")


if __name__ == "__main__":
    main()
