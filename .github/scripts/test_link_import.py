#!/usr/bin/env python3
"""Tests for link_import.py. DNS and the network are always faked: no live requests.

Run: python3 -m unittest discover -s .github/scripts -p 'test_*.py'
"""

import http.server
import os
import socket
import ssl
import sys
import threading
import time
import unittest
import urllib.parse
from unittest import mock

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import link_import as li  # noqa: E402


def resolver(table):
    """Fake DNS: host name -> list of addresses."""
    return lambda host: table[host]


class FakeResponse:
    """Stands in for http.client.HTTPResponse, the network boundary."""

    def __init__(self, status=200, headers=None, body=b""):
        self.status = status
        self.headers = {"Content-Type": "text/html; charset=utf-8", **(headers or {})}
        self.body = body

    def getheader(self, name, default=None):
        return self.headers.get(name, default)

    def read1(self, size):
        chunk, self.body = self.body[:size], self.body[size:]
        return chunk

    def settimeout(self, seconds):
        pass

    def close(self):
        pass


def server(pages):
    """Fake web: (host, path) -> FakeResponse. Records every connection."""
    def sender(parts, ip, timeout=None, on_socket=None):
        sender.calls.append((parts.hostname, ip, parts.path))
        return pages[(parts.hostname, parts.path)]
    sender.calls = []
    return sender


def no_network(parts, ip, timeout=None, on_socket=None):
    raise AssertionError(f"must not connect to {parts.hostname} at {ip}")


class FetchTest(unittest.TestCase):
    def assertRefused(self, reason, url, table, sender=no_network):
        with self.assertRaises(li.FetchError) as ctx:
            li.fetch_page(url, resolver=resolver(table), sender=sender)
        self.assertEqual(str(ctx.exception), reason)

    def test_public_page_is_returned(self):
        sender = server({("recipes.example", "/chili"): FakeResponse(body="<p>Chili ½ cup</p>".encode())})
        page = li.fetch_page("https://recipes.example/chili",
                             resolver=resolver({"recipes.example": ["93.184.215.14"]}), sender=sender)
        self.assertEqual(page, "<p>Chili ½ cup</p>")
        self.assertEqual(sender.calls, [("recipes.example", "93.184.215.14", "/chili")])

    def test_oversized_page_is_refused(self):
        big = b"<p>" + b"x" * (2 * 1024 * 1024) + b"</p>"
        public = {"recipes.example": ["93.184.215.14"]}
        # Streamed without a length header: refused once the running total passes the cap.
        self.assertRefused("link-too-large", "https://recipes.example/big", public,
                           server({("recipes.example", "/big"): FakeResponse(body=big)}))
        # Declared too large up front: refused before reading the body.
        declared = FakeResponse(headers={"Content-Length": str(len(big))}, body=b"")
        self.assertRefused("link-too-large", "https://recipes.example/big", public,
                           server({("recipes.example", "/big"): declared}))

    def test_redirect_to_private_ip_is_refused(self):
        sender = server({("recipes.example", "/chili"): FakeResponse(
            302, {"Location": "http://internal.example/admin"})})
        self.assertRefused("link-refused-address", "https://recipes.example/chili",
                           {"recipes.example": ["93.184.215.14"], "internal.example": ["192.168.1.1"]},
                           sender)
        self.assertEqual(sender.calls, [("recipes.example", "93.184.215.14", "/chili")])

    def test_public_redirect_is_followed(self):
        sender = server({
            ("recipes.example", "/old"): FakeResponse(301, {"Location": "/new"}),
            ("recipes.example", "/new"): FakeResponse(body=b"<p>moved</p>"),
        })
        page = li.fetch_page("http://recipes.example/old",
                             resolver=resolver({"recipes.example": ["93.184.215.14"]}), sender=sender)
        self.assertEqual(page, "<p>moved</p>")
        self.assertEqual([c[2] for c in sender.calls], ["/old", "/new"])

    def test_redirect_loop_is_cut_off(self):
        sender = server({("recipes.example", "/loop"): FakeResponse(302, {"Location": "/loop"})})
        self.assertRefused("link-too-many-redirects", "https://recipes.example/loop",
                           {"recipes.example": ["93.184.215.14"]}, sender)
        self.assertEqual(len(sender.calls), 6)  # the first request plus five redirects

    def test_error_status_non_html_and_compressed_pages_are_refused(self):
        public = {"recipes.example": ["93.184.215.14"]}
        for reason, response in (
                ("link-fetch-failed", FakeResponse(404, body=b"<p>gone</p>")),
                ("link-not-html", FakeResponse(headers={"Content-Type": "application/pdf"}, body=b"%PDF")),
                ("link-fetch-failed", FakeResponse(headers={"Content-Encoding": "gzip"}, body=b"\x1f\x8b"))):
            with self.subTest(reason=reason, headers=response.headers):
                self.assertRefused(reason, "https://recipes.example/x", public,
                                   server({("recipes.example", "/x"): response}))

    def test_network_errors_become_a_reason(self):
        def broken(parts, ip, timeout=None, on_socket=None):
            raise ConnectionResetError("reset")
        self.assertRefused("link-fetch-failed", "https://recipes.example/x",
                           {"recipes.example": ["93.184.215.14"]}, broken)

    def test_slow_drip_page_hits_the_overall_deadline(self):
        clock = [1000.0]

        class Drip(FakeResponse):
            def read1(self, size):
                clock[0] += 15  # each tiny chunk takes 15 seconds: under the socket timeout
                return b"x"

        with mock.patch("time.monotonic", lambda: clock[0]):
            self.assertRefused("link-fetch-failed", "https://recipes.example/slow",
                               {"recipes.example": ["93.184.215.14"]},
                               server({("recipes.example", "/slow"): Drip()}))
        self.assertLess(clock[0], 1000 + 60)

    def test_slow_redirect_chain_hits_the_overall_deadline(self):
        clock = [1000.0]

        def slow_redirects(parts, ip, timeout=None, on_socket=None):
            slow_redirects.calls += 1
            clock[0] += 15  # each hop takes 15 seconds: under the socket timeout
            return FakeResponse(302, {"Location": f"/hop{slow_redirects.calls}"})
        slow_redirects.calls = 0

        with mock.patch("time.monotonic", lambda: clock[0]):
            self.assertRefused("link-fetch-failed", "https://recipes.example/slow",
                               {"recipes.example": ["93.184.215.14"]}, slow_redirects)
        self.assertEqual(slow_redirects.calls, 2)

    def test_private_ip_link_is_refused(self):
        self.assertRefused("link-refused-address", "https://recipes.example/chili",
                           {"recipes.example": ["10.0.0.5"]})

    def test_only_http_and_https_on_default_ports(self):
        for url in ("ftp://recipes.example/chili", "file:///etc/passwd", "gopher://recipes.example/",
                    "https://recipes.example:8443/chili", "http://recipes.example:22/",
                    "https://user:pw@recipes.example/", "https://recipes.example/a b",
                    "https:///no-host", "https://recipes.example:99999/"):
            with self.subTest(url=url):
                # An empty DNS table fails the test with KeyError if DNS is consulted.
                self.assertRefused("link-refused-url", url, {})

    def test_loopback_link_local_metadata_and_mapped_addresses_are_refused(self):
        for addresses in (["127.0.0.1"], ["169.254.169.254"], ["::1"], ["fe80::1"],
                          ["fd00:ec2::254"], ["::ffff:10.0.0.1"], ["::ffff:169.254.169.254"],
                          ["100.64.0.1"], ["0.0.0.0"], ["239.1.2.3"], ["ff02::1"],
                          ["93.184.215.14", "192.168.1.10"]):
            with self.subTest(addresses=addresses):
                self.assertRefused("link-refused-address", "https://recipes.example/chili",
                                   {"recipes.example": addresses})


def ld_page(recipe):
    return f'<script type="application/ld+json">{recipe}</script><p>page</p>'


class JsonLdTest(unittest.TestCase):
    def test_string_and_string_list_instructions(self):
        for instructions in ('"<p>Crack the egg.</p><p>Fry 2 minutes.</p>"',
                             '"Crack the egg.\\nFry 2 minutes."',
                             '["Crack the egg.", "Fry 2 minutes."]'):
            with self.subTest(instructions=instructions):
                page = ld_page('{"@type": "Recipe", "recipeIngredient": "1 egg", '
                               f'"recipeInstructions": {instructions}}}')
                self.assertEqual(li.recipe_from_json_ld(page), ("1 egg", "Crack the egg.\nFry 2 minutes."))

    def test_visible_text_is_capped(self):
        text = li.visible_text("<p>" + "word " * 20_000 + "</p>")
        self.assertEqual(len(text), 40_000)

    def test_page_without_recipe_data(self):
        self.assertIsNone(li.recipe_from_json_ld(ld_page('{"@type": "Article", "name": "x"}')))
        self.assertIsNone(li.recipe_from_json_ld("<p>no data</p>"))


class SendTest(unittest.TestCase):
    def test_connection_goes_to_the_vetted_address_not_a_fresh_lookup(self):
        seen = {}

        class Handler(http.server.BaseHTTPRequestHandler):
            def do_GET(self):
                seen["host"], seen["path"] = self.headers["Host"], self.path
                seen["encoding"] = self.headers["Accept-Encoding"]
                self.send_response(200)
                self.send_header("Content-Type", "text/html")
                self.end_headers()
                self.wfile.write(b"<p>pinned</p>")

            def log_message(self, *args):
                pass

        httpd = http.server.HTTPServer(("127.0.0.1", 0), Handler)
        self.addCleanup(httpd.server_close)
        threading.Thread(target=httpd.handle_request, daemon=True).start()
        port = httpd.server_address[1]
        # ".invalid" never resolves, so reaching the server proves the pinned address was used.
        response = li.send(urllib.parse.urlsplit(f"http://recipe.invalid:{port}/chili?x=1#frag"), "127.0.0.1")
        self.assertEqual((response.status, response.read(100)), (200, b"<p>pinned</p>"))
        self.assertEqual(seen, {"host": f"recipe.invalid:{port}", "path": "/chili?x=1", "encoding": "identity"})

    def test_real_socket_drip_cannot_outlast_the_deadline(self):
        class Drip(http.server.BaseHTTPRequestHandler):
            def do_GET(self):
                self.send_response(200)
                self.send_header("Content-Type", "text/html")
                self.end_headers()
                try:
                    for _ in range(40):  # one byte every 0.1 s: never trips the socket timeout
                        self.wfile.write(b"x")
                        self.wfile.flush()
                        time.sleep(0.1)
                except OSError:
                    pass

            def log_message(self, *args):
                pass

        httpd = http.server.HTTPServer(("127.0.0.1", 0), Drip)
        self.addCleanup(httpd.server_close)
        threading.Thread(target=httpd.handle_request, daemon=True).start()
        port = httpd.server_address[1]

        def loopback(parts, ip, timeout=li.TIMEOUT, on_socket=None):
            return li.send(urllib.parse.urlsplit(f"http://recipe.invalid:{port}/"), "127.0.0.1",
                           timeout, on_socket)

        start = time.monotonic()
        with mock.patch.object(li, "DEADLINE", 1), mock.patch.object(li, "TIMEOUT", 0.5):
            with self.assertRaises(li.FetchError) as ctx:
                li.fetch_page("https://recipes.example/slow",
                              resolver=resolver({"recipes.example": ["93.184.215.14"]}), sender=loopback)
        self.assertEqual(str(ctx.exception), "link-fetch-failed")
        self.assertLess(time.monotonic() - start, 2)

    def test_real_socket_header_drip_cannot_outlast_the_deadline(self):
        class HeaderDrip(http.server.BaseHTTPRequestHandler):
            def do_GET(self):
                try:
                    self.wfile.write(b"HTTP/1.1 200 OK\r\nX-Slow: ")
                    for _ in range(40):  # one header byte every 0.1 s: never trips the socket timeout
                        self.wfile.write(b"x")
                        self.wfile.flush()
                        time.sleep(0.1)
                    self.wfile.write(b"\r\nContent-Type: text/html\r\nContent-Length: 9\r\n\r\n<p>ok</p>")
                except OSError:
                    pass

            def log_message(self, *args):
                pass

        httpd = http.server.HTTPServer(("127.0.0.1", 0), HeaderDrip)
        self.addCleanup(httpd.server_close)
        threading.Thread(target=httpd.handle_request, daemon=True).start()
        port = httpd.server_address[1]

        def loopback(parts, ip, timeout=li.TIMEOUT, on_socket=None):
            return li.send(urllib.parse.urlsplit(f"http://recipe.invalid:{port}/"), "127.0.0.1",
                           timeout, on_socket)

        start = time.monotonic()
        with mock.patch.object(li, "DEADLINE", 1), mock.patch.object(li, "TIMEOUT", 0.5):
            with self.assertRaises(li.FetchError) as ctx:
                li.fetch_page("https://recipes.example/slow",
                              resolver=resolver({"recipes.example": ["93.184.215.14"]}), sender=loopback)
        self.assertEqual(str(ctx.exception), "link-fetch-failed")
        self.assertLess(time.monotonic() - start, 2)

    def test_real_socket_tls_header_drip_cannot_outlast_the_deadline(self):
        # A self-signed certificate for recipe.invalid, used only by this test.
        cert = os.path.join(os.path.dirname(os.path.abspath(__file__)), "fixtures", "test_only_tls.pem")
        server_tls = ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER)
        server_tls.load_cert_chain(cert)
        listener = socket.socket()
        listener.bind(("127.0.0.1", 0))
        listener.listen(1)
        self.addCleanup(listener.close)
        port = listener.getsockname()[1]

        def header_drip():
            raw, _ = listener.accept()
            try:
                with server_tls.wrap_socket(raw, server_side=True) as conn:
                    conn.recv(4096)  # the request
                    conn.sendall(b"HTTP/1.1 200 OK\r\nX-Slow: ")
                    for _ in range(40):  # one header byte every 0.1 s: never trips the socket timeout
                        conn.sendall(b"x")
                        time.sleep(0.1)
                    conn.sendall(b"\r\nContent-Type: text/html\r\nContent-Length: 9\r\n\r\n<p>ok</p>")
            except OSError:
                pass

        threading.Thread(target=header_drip, daemon=True).start()

        def loopback(parts, ip, timeout=li.TIMEOUT, on_socket=None):
            return li.send(urllib.parse.urlsplit(f"https://recipe.invalid:{port}/"), "127.0.0.1",
                           timeout, on_socket)

        trusting = ssl.create_default_context(cafile=cert)
        start = time.monotonic()
        with mock.patch.object(li, "DEADLINE", 1), mock.patch.object(li, "TIMEOUT", 0.5), \
                mock.patch.object(li.ssl, "create_default_context", lambda: trusting):
            with self.assertRaises(li.FetchError) as ctx:
                li.fetch_page("https://recipes.example/slow",
                              resolver=resolver({"recipes.example": ["93.184.215.14"]}), sender=loopback)
        self.assertEqual(str(ctx.exception), "link-fetch-failed")
        self.assertLess(time.monotonic() - start, 2)

if __name__ == "__main__":
    unittest.main()
