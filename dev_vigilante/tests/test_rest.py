import io
import json
import urllib.error
import urllib.parse

import pytest

from dev_vigilante.sources.base import AccessDenied, AuthenticationFailed, NotAvailable
from dev_vigilante.sources.rest import RestClient, SourceError, _SameHostRedirects


class _Response(io.BytesIO):
    def __enter__(self):
        return self

    def __exit__(self, *exc):
        return False


class FakeOpener:
    """Records requests; replies from a list of (status, payload) per call."""

    def __init__(self, replies):
        self.replies = list(replies)
        self.requests = []

    def open(self, request, timeout=None):
        self.requests.append(request)
        status, payload = self.replies.pop(0)
        if status != 200:
            raise urllib.error.HTTPError(request.full_url, status, "err", {}, None)
        return _Response(json.dumps(payload).encode())


def _client(replies):
    opener = FakeOpener(replies)
    return RestClient("https://erp.example.com/", "k", "s", opener=opener), opener


def test_rejects_bad_urls_and_plain_http():
    with pytest.raises(ValueError):
        RestClient("erp.example.com", "k", "s")
    with pytest.raises(ValueError):
        RestClient("http://erp.example.com", "k", "s")
    with pytest.raises(ValueError):
        RestClient("https://erp.example.com/app", "k", "s")
    with pytest.raises(ValueError):
        RestClient("https://erp.example.com", "k", "")
    RestClient("http://localhost:8000", "k", "s")  # local dev is fine


def test_sends_token_and_only_get():
    client, opener = _client([(200, {"data": []})])
    client.list("Custom Field", ["name"])
    request = opener.requests[0]
    assert request.get_method() == "GET"
    assert request.get_header("Authorization") == "token k:s"
    assert request.full_url.startswith("https://erp.example.com/api/resource/Custom%20Field?")


def test_client_has_no_write_methods():
    for name in ("post", "put", "patch", "delete", "insert", "update", "save"):
        assert not hasattr(RestClient, name)


def test_pagination_collects_all_pages(monkeypatch):
    monkeypatch.setattr("dev_vigilante.sources.rest.PAGE_SIZE", 2)
    client, opener = _client(
        [(200, {"data": [{"name": "a"}, {"name": "b"}]}), (200, {"data": [{"name": "c"}]})]
    )
    rows = client.list("Client Script", ["name"])
    assert [r["name"] for r in rows] == ["a", "b", "c"]
    starts = [urllib.parse.parse_qs(urllib.parse.urlparse(r.full_url).query)["limit_start"] for r in opener.requests]
    assert starts == [["0"], ["2"]]


def test_limit_stops_after_first_page():
    client, opener = _client([(200, {"data": [{"name": "a"}]})])
    assert client.list("DocType", ["name"], limit=1) == [{"name": "a"}]
    assert len(opener.requests) == 1


@pytest.mark.parametrize(
    "status, exc", [(401, AuthenticationFailed), (403, AccessDenied), (404, NotAvailable), (500, SourceError)]
)
def test_http_errors_map_to_source_errors(status, exc):
    client, _ = _client([(status, {})])
    with pytest.raises(exc):
        client.list("Server Script", ["name"])


def test_doc_names_are_escaped():
    client, opener = _client([(200, {"data": {"name": "A/B"}})])
    client.doc("DocType", "A/B")
    assert opener.requests[0].full_url.endswith("/api/resource/DocType/A%2FB")


def test_redirects_to_other_hosts_are_refused():
    import urllib.request

    handler = _SameHostRedirects()
    req = urllib.request.Request("https://erp.example.com/api/resource/User")
    with pytest.raises(SourceError):
        handler.redirect_request(req, None, 302, "Found", {}, "https://evil.example.net/x")
    with pytest.raises(SourceError):
        handler.redirect_request(req, None, 302, "Found", {}, "http://erp.example.com/x")
    assert handler.redirect_request(req, None, 302, "Found", {}, "https://erp.example.com/y")
