"""REST source: reads a remote site's metadata over the Frappe REST API.

Strictly read-only: the client can only issue ``GET`` requests — there is no code path
that sends POST/PUT/PATCH/DELETE. Pair it with an API user that has Read-only roles so
the server enforces the same guarantee.

Standard library only (``urllib``), so the CLI installs without extra dependencies.
"""

from __future__ import annotations

import json
import urllib.error
import urllib.parse
import urllib.request

from dev_vigilante.sources.base import (
    AccessDenied,
    AuthenticationFailed,
    NotAvailable,
    Source,
    SourceError,
)

PAGE_SIZE = 500
TIMEOUT = 60
_LOCAL_HOSTS = {"localhost", "127.0.0.1", "::1"}


class _SameHostRedirects(urllib.request.HTTPRedirectHandler):
    """Follow redirects only within the same host and never downgrade to http.

    urllib copies request headers onto the redirected request, so an unrestricted
    redirect would hand the API token to whichever host the server points at.
    """

    def redirect_request(self, req, fp, code, msg, headers, newurl):
        old = urllib.parse.urlparse(req.full_url)
        new = urllib.parse.urlparse(newurl)
        if new.hostname != old.hostname or (old.scheme == "https" and new.scheme != "https"):
            raise SourceError(f"Refusing to follow redirect to {new.scheme}://{new.hostname}")
        return super().redirect_request(req, fp, code, msg, headers, newurl)


class RestClient:
    """Minimal GET-only Frappe REST client with token authentication."""

    def __init__(self, base_url: str, api_key: str, api_secret: str, opener=None):
        base_url = (base_url or "").strip().rstrip("/")
        parsed = urllib.parse.urlparse(base_url)
        if parsed.scheme not in ("http", "https") or not parsed.netloc:
            raise ValueError(f"FRAPPE_URL must look like https://your-site.example.com (got {base_url!r}).")
        if parsed.scheme == "http" and parsed.hostname not in _LOCAL_HOSTS:
            # The token would travel in clear text.
            raise ValueError("FRAPPE_URL must use https:// for non-local sites.")
        if parsed.path not in ("", "/"):
            raise ValueError("FRAPPE_URL must be just the site address, without a path like /app.")
        if not api_key or not api_secret:
            raise ValueError("FRAPPE_API_KEY and FRAPPE_API_SECRET must both be set.")

        self.base_url = base_url
        self.host = parsed.hostname
        self._headers = {
            "Authorization": f"token {api_key}:{api_secret}",
            "Accept": "application/json",
        }
        self._opener = opener or urllib.request.build_opener(_SameHostRedirects)

    # The only request primitive. Deliberately GET-only.
    def _get(self, path: str, params: dict | None = None) -> dict:
        url = f"{self.base_url}{path}"
        if params:
            url += "?" + urllib.parse.urlencode(params)
        request = urllib.request.Request(url, headers=self._headers, method="GET")
        try:
            with self._opener.open(request, timeout=TIMEOUT) as response:
                return json.loads(response.read().decode("utf-8") or "{}")
        except urllib.error.HTTPError as exc:
            if exc.code == 401:
                raise AuthenticationFailed("API key/secret rejected (HTTP 401).") from exc
            if exc.code == 403:
                raise AccessDenied(path) from exc
            if exc.code == 404:
                raise NotAvailable(path) from exc
            raise SourceError(f"HTTP {exc.code} for {path}") from exc
        except urllib.error.URLError as exc:
            raise SourceError(f"Could not reach {self.base_url}: {exc.reason}") from exc

    def list(self, doctype, fields, filters=None, order_by=None, limit=None) -> list[dict]:
        """All rows of ``doctype`` (paged), or at most ``limit`` rows."""
        path = "/api/resource/" + urllib.parse.quote(doctype)
        page = min(limit, PAGE_SIZE) if limit else PAGE_SIZE
        params = {"fields": json.dumps(fields), "limit_page_length": page}
        if filters:
            params["filters"] = json.dumps(filters)
        if order_by:
            params["order_by"] = order_by

        rows: list[dict] = []
        start = 0
        while True:
            params["limit_start"] = start
            batch = self._get(path, params).get("data") or []
            rows.extend(batch)
            if len(batch) < page or (limit and len(rows) >= limit):
                return rows[:limit] if limit else rows
            start += page

    def doc(self, doctype: str, name: str) -> dict:
        path = "/api/resource/{}/{}".format(
            urllib.parse.quote(doctype), urllib.parse.quote(name, safe="")
        )
        return self._get(path).get("data") or {}

    def method(self, dotted_path: str, params: dict | None = None):
        return self._get(f"/api/method/{dotted_path}", params).get("message")


class RestSource(Source):
    kind = "rest"

    def __init__(self, client: RestClient):
        self.client = client

    def site_name(self) -> str | None:
        return self.client.host

    def get_all(self, doctype, fields, filters=None, order_by=None):
        return self.client.list(doctype, fields, filters=filters, order_by=order_by)

    def get_doc(self, doctype, name):
        return self.client.doc(doctype, name)

    def system_info(self) -> dict:
        info: dict = {}
        try:
            versions = self.client.method("frappe.utils.change_log.get_versions") or {}
        except SourceError:
            versions = {}
        if versions:
            info["app_versions"] = {
                app: (data or {}).get("version") for app, data in sorted(versions.items())
            }
            info["installed_apps"] = sorted(versions)
            info["versions"] = {
                app: info["app_versions"].get(app) for app in ("frappe", "erpnext")
            }
        return info

    def logged_user(self) -> str | None:
        return self.client.method("frappe.auth.get_logged_user")
