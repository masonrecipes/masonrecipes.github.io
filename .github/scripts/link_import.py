#!/usr/bin/env python3
"""
Read a recipe from a submitted link: fetch the page safely, then pull ingredients and
steps from its schema.org Recipe JSON-LD, or fall back to its visible text for the
model. Nothing here runs page scripts; the page is only parsed as text.

Fetch rules: http/https on default ports only; every hop's host is resolved first and
refused unless all its addresses are public; the socket connects to the vetted address
(so DNS cannot change between check and connect); short timeouts, a byte cap and a
redirect limit apply.
"""

import html
import http.client
import ipaddress
import json
import re
import socket
import ssl
import threading
import time
import urllib.parse
from html.parser import HTMLParser

MAX_BYTES = 2 * 1024 * 1024
MAX_REDIRECTS = 5
DEFAULT_PORTS = {"http": 80, "https": 443}
HTML_TYPES = ("text/html", "application/xhtml+xml")
TIMEOUT = 10  # seconds per socket operation
DEADLINE = 20  # seconds for the whole fetch, all hops
MAX_PAGE_TEXT = 40_000
USER_AGENT = "MasonRecipesBot/1.0 (+https://masonrecipes.github.io)"
CHALLENGE_PAGE = re.compile(r"<title>\s*Just a moment\.\.\.\s*</title>|/cdn-cgi/challenge-platform/", re.I)


class FetchError(Exception):
    """The page could not be read safely. The message is a fixed reason code."""


# --- Safe fetch ------------------------------------------------------------------


def resolve(host):
    """Every address the host resolves to, as strings."""
    try:
        infos = socket.getaddrinfo(host, None, type=socket.SOCK_STREAM)
    except (socket.gaierror, UnicodeError):
        raise FetchError("link-fetch-failed") from None
    return sorted({info[4][0] for info in infos})


def public_address(addresses):
    """Return the first address if every one is public, else refuse."""
    if not addresses:
        raise FetchError("link-fetch-failed")
    for value in addresses:
        ip = ipaddress.ip_address(value.split("%", 1)[0])
        # is_global excludes private, loopback, link-local (169.254.169.254 metadata),
        # shared, reserved and IPv4-mapped ranges, but not multicast.
        if not ip.is_global or ip.is_multicast:
            raise FetchError("link-refused-address")
    return addresses[0]


def check_url(url):
    """Split a URL we are willing to fetch, or refuse it."""
    if re.search(r"[\s\x00-\x1f\x7f]", url):
        raise FetchError("link-refused-url")
    try:
        parts = urllib.parse.urlsplit(url)
        port = parts.port
    except ValueError:
        raise FetchError("link-refused-url") from None
    scheme = parts.scheme.lower()
    if (scheme not in DEFAULT_PORTS or not parts.hostname or parts.username
            or parts.password or port not in (None, DEFAULT_PORTS[scheme])):
        raise FetchError("link-refused-url")
    return parts


class _PinnedHTTP(http.client.HTTPConnection):
    def __init__(self, host, ip, on_socket=None, **kwargs):
        super().__init__(host, **kwargs)
        self._ip, self._on_socket = ip, on_socket or (lambda sock: None)

    def connect(self):
        self.sock = socket.create_connection((self._ip, self.port), self.timeout)
        self._on_socket(self.sock)


class _PinnedHTTPS(http.client.HTTPSConnection):
    def __init__(self, host, ip, on_socket=None, **kwargs):
        super().__init__(host, context=ssl.create_default_context(), **kwargs)
        self._ip, self._on_socket = ip, on_socket or (lambda sock: None)

    def connect(self):
        sock = socket.create_connection((self._ip, self.port), self.timeout)
        # Certificate and SNI are checked against the real host name.
        self.sock = self._context.wrap_socket(sock, server_hostname=self.host,
                                              do_handshake_on_connect=False)
        self._on_socket(self.sock)
        self.sock.do_handshake()


def send(parts, ip, timeout=TIMEOUT, on_socket=None):
    """GET the URL from the vetted address. Returns an http.client response.
    `on_socket` receives the socket used for I/O as soon as it is connected."""
    cls = _PinnedHTTPS if parts.scheme.lower() == "https" else _PinnedHTTP
    conn = cls(parts.hostname, ip, on_socket=on_socket, port=parts.port, timeout=timeout)
    path = urllib.parse.urlunsplit(("", "", parts.path or "/", parts.query, ""))
    conn.request("GET", path, headers={
        "User-Agent": USER_AGENT,
        "Accept": "text/html,application/xhtml+xml",
        "Accept-Encoding": "identity",
    })
    sock = conn.sock
    response = conn.getresponse()
    response.settimeout = sock.settimeout
    return response


def remaining(deadline):
    """Seconds left for the next socket wait, never more than TIMEOUT."""
    left = deadline - time.monotonic()
    if left <= 0:
        raise FetchError("link-fetch-failed")
    return min(TIMEOUT, left)


def read_capped(response, deadline):
    length = response.getheader("Content-Length")
    if length and length.isdigit() and int(length) > MAX_BYTES:
        raise FetchError("link-too-large")
    chunks, total = [], 0
    while True:
        response.settimeout(remaining(deadline))
        chunk = response.read1(64 * 1024)
        if not chunk:
            break
        total += len(chunk)
        if total > MAX_BYTES:
            raise FetchError("link-too-large")
        chunks.append(chunk)
    remaining(deadline)
    return b"".join(chunks)


def is_challenge(response, deadline):
    """A bot wall (Cloudflare's managed challenge and the like) that no plain fetch gets
    past, so the submitter is asked for the text instead. Mirrored in the Worker."""
    if response.status not in (403, 503):
        return False
    if "challenge" in (response.getheader("cf-mitigated") or "").lower():
        return True
    try:
        body = read_capped(response, deadline)
    except FetchError:
        return False
    return bool(CHALLENGE_PAGE.search(body.decode("utf-8", errors="replace")))


def fetch_page(url, resolver=resolve, sender=send):
    """Return the HTML of a public web page as text, or raise FetchError."""
    try:
        return _fetch(url, resolver, sender)
    except (OSError, http.client.HTTPException):
        # Timeouts, resets, TLS failures and malformed responses.
        raise FetchError("link-fetch-failed") from None


def _fetch(url, resolver, sender):
    deadline = time.monotonic() + DEADLINE
    opened = []

    def expire():
        for sock in opened:
            try:
                sock.shutdown(socket.SHUT_RDWR)
            except OSError:
                pass

    watchdog = threading.Timer(DEADLINE, expire)
    watchdog.daemon = True
    watchdog.start()
    try:
        return _fetch_within(url, resolver, sender, deadline, opened.append)
    finally:
        watchdog.cancel()


def _fetch_within(url, resolver, sender, deadline, on_socket):
    for hop in range(MAX_REDIRECTS + 1):
        timeout = remaining(deadline)
        # Every hop is checked again: scheme, port, DNS and address.
        parts = check_url(url)
        ip = public_address(resolver(parts.hostname))
        response = sender(parts, ip, timeout, on_socket)
        remaining(deadline)
        if response.status not in (301, 302, 303, 307, 308):
            break
        if hop == MAX_REDIRECTS:
            raise FetchError("link-too-many-redirects")
        location = response.getheader("Location")
        response.close()
        if not location:
            raise FetchError("link-fetch-failed")
        url = urllib.parse.urljoin(url, location)
    if is_challenge(response, deadline):
        raise FetchError("link-blocked")
    if response.status != 200:
        raise FetchError("link-fetch-failed")
    kind = (response.getheader("Content-Type") or "").split(";")[0].strip().lower()
    if kind not in HTML_TYPES:
        raise FetchError("link-not-html")
    # Accept-Encoding: identity is sent; anything else is not decoded, only refused.
    if (response.getheader("Content-Encoding") or "identity").lower() != "identity":
        raise FetchError("link-fetch-failed")
    body = read_capped(response, deadline)
    charset = re.search(r"charset=([\w-]+)", response.getheader("Content-Type") or "")
    try:
        return body.decode(charset.group(1) if charset else "utf-8", errors="replace")
    except LookupError:
        return body.decode("utf-8", errors="replace")


# --- Page parsing ----------------------------------------------------------------


SKIP_TAGS = {"script", "style", "noscript", "template", "svg", "head", "iframe", "object"}
BLOCK_TAGS = {"p", "div", "br", "li", "tr", "h1", "h2", "h3", "h4", "h5", "h6", "section",
              "article", "header", "footer", "nav", "ul", "ol", "table", "blockquote"}


class _PageParser(HTMLParser):
    """Collect JSON-LD blocks and visible text. Scripts are read as data, never run."""

    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.json_ld, self.text = [], []
        self._ld = None
        self._skip = 0

    def handle_starttag(self, tag, attrs):
        if tag == "script" and (dict(attrs).get("type") or "").strip().lower() == "application/ld+json":
            self._ld = []
        if tag in SKIP_TAGS:
            self._skip += 1
        elif tag in BLOCK_TAGS:
            self.text.append("\n")

    def handle_endtag(self, tag):
        if tag == "script" and self._ld is not None:
            self.json_ld.append("".join(self._ld))
            self._ld = None
        if tag in SKIP_TAGS:
            self._skip = max(0, self._skip - 1)
        elif tag in BLOCK_TAGS:
            self.text.append("\n")

    def handle_data(self, data):
        if self._ld is not None:
            self._ld.append(data)
        elif not self._skip:
            self.text.append(data)


def parse_page(page):
    parser = _PageParser()
    parser.feed(page)
    parser.close()
    return parser


def plain(value):
    """Schema.org strings often carry HTML entities or tags; keep only the text."""
    if not isinstance(value, str):
        return ""
    return " ".join(re.sub(r"<[^>]*>", " ", html.unescape(value)).split())


def _is_recipe(node):
    kind = node.get("@type")
    kinds = kind if isinstance(kind, list) else [kind]
    return any(isinstance(k, str) and k.rsplit("/", 1)[-1] == "Recipe" for k in kinds)


def find_recipe(node, depth=0):
    """Depth-first search for the first schema.org Recipe object: top level, @graph,
    arrays, mainEntity and other nesting."""
    if depth > 8:
        return None
    if isinstance(node, list):
        for item in node:
            found = find_recipe(item, depth + 1)
            if found:
                return found
    elif isinstance(node, dict):
        if _is_recipe(node):
            return node
        for value in node.values():
            found = find_recipe(value, depth + 1)
            if found:
                return found
    return None


def _steps(value, out, depth=0):
    """Flatten recipeInstructions: text, HowToStep, HowToSection (name then its
    steps), lists."""
    if depth > 6:
        return
    if isinstance(value, str):
        # One string may hold every step, split by lines or paragraphs.
        for line in re.split(r"\n+|<br\s*/?>|</p>", html.unescape(value)):
            if plain(line):
                out.append(plain(line))
    elif isinstance(value, list):
        for item in value:
            _steps(item, out, depth + 1)
    elif isinstance(value, dict):
        children = value.get("itemListElement")
        if children is not None:
            if plain(value.get("name")):
                out.append(plain(value["name"]) + ":")
            _steps(children, out, depth + 1)
        elif plain(value.get("text")):
            out.append(plain(value["text"]))


def recipe_from_json_ld(page):
    """Return (ingredients, steps) text from the page's Recipe JSON-LD, or None."""
    for block in parse_page(page).json_ld:
        try:
            recipe = find_recipe(json.loads(block))
        except json.JSONDecodeError:
            continue
        if not recipe:
            continue
        raw = recipe.get("recipeIngredient") or []
        raw = raw if isinstance(raw, list) else [raw]
        ingredients = [plain(item) for item in raw if plain(item)]
        steps = []
        _steps(recipe.get("recipeInstructions"), steps)
        if ingredients and steps:
            return "\n".join(ingredients), "\n".join(steps)
    return None


def visible_text(page):
    """The page's readable text for the model, one block per line, capped in size."""
    lines = (" ".join(line.split()) for line in "".join(parse_page(page).text).splitlines())
    return "\n".join(line for line in lines if line)[:MAX_PAGE_TEXT]
