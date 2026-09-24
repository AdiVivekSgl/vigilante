"""Data sources: where collectors read ERP metadata from.

Collectors never import ``frappe`` directly; they read through a :class:`Source`. The
bench source (:mod:`dev_vigilante.sources.bench`) runs inside a Frappe site, the REST
source (:mod:`dev_vigilante.sources.rest`) runs anywhere with an API token. Both expose
the same read-only surface, so the same collectors, engine and exporters serve both.
"""

from __future__ import annotations


class SourceError(Exception):
    """Base class for expected, non-fatal read failures."""


class AccessDenied(SourceError):
    """The credentials in use may not read this DocType (HTTP 403 / PermissionError)."""


class NotAvailable(SourceError):
    """The DocType or method does not exist on this site (HTTP 404)."""


class AuthenticationFailed(Exception):
    """The credentials were rejected outright (HTTP 401). Fatal for a whole run, so it
    deliberately is *not* a :class:`SourceError`."""


class Source:
    """Read-only access to a site's metadata.

    Rows and documents are plain ``dict``s. Implementations raise :class:`AccessDenied`
    or :class:`NotAvailable` for DocTypes the collectors should skip rather than fail on.
    """

    #: short identifier recorded in snapshot meta ("bench" / "rest")
    kind: str = ""

    def site_name(self) -> str | None:  # pragma: no cover - interface
        raise NotImplementedError

    def get_all(
        self,
        doctype: str,
        fields: list[str],
        filters: dict | None = None,
        order_by: str | None = None,
    ) -> list[dict]:  # pragma: no cover - interface
        raise NotImplementedError

    def get_doc(self, doctype: str, name: str) -> dict:  # pragma: no cover - interface
        raise NotImplementedError

    def system_info(self) -> dict:  # pragma: no cover - interface
        """Versions and environment details, as much as this source can see.

        Keys (all optional): ``versions``, ``installed_apps``, ``app_versions``,
        ``site_config``, ``system_settings``, ``database``, ``platform``.
        """
        raise NotImplementedError
