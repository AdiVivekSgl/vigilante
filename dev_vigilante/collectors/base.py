"""Collector base class and shared run context.

Collectors are strictly read-only against ERP metadata: they may only read via
``frappe.get_all`` / ``frappe.get_doc`` / ``frappe.get_meta`` / SELECT queries.
"""

from __future__ import annotations

from dev_vigilante.artifact import Artifact

# Apps considered "vanilla". Artifacts owned by these are excluded unless the
# settings opt in via ``include_standard_apps``.
STANDARD_APPS = {"frappe", "erpnext"}

# This app's own module(s) are tooling, not customizations of the ERP; never capture them.
SELF_APP = "dev_vigilante"


class CollectorContext:
    """Shared, read-only context handed to every collector during a run.

    Attributes:
        scope: dict from ``VigilanteSettings.get_scope()`` (include/exclude modules,
            include_standard_apps, include_raw_source).
        app_by_module: mapping of module name -> owning app name.
        standard_modules: set of module names owned by standard apps.
    """

    def __init__(self, scope: dict, app_by_module: dict[str, str]):
        self.scope = scope or {}
        self.app_by_module = app_by_module or {}
        self.standard_modules = {
            module
            for module, app in self.app_by_module.items()
            if app in STANDARD_APPS
        }
        self.self_modules = {
            module for module, app in self.app_by_module.items() if app == SELF_APP
        }

    # --- scope helpers ----------------------------------------------------------

    def app_for_module(self, module: str | None) -> str | None:
        return self.app_by_module.get(module) if module else None

    def is_module_in_scope(self, module: str | None) -> bool:
        """Whether artifacts in ``module`` should be captured given the settings."""
        include = self.scope.get("include_modules") or []
        exclude = self.scope.get("exclude_modules") or []
        include_standard = self.scope.get("include_standard_apps")

        if module:
            if module in self.self_modules:
                return False
            if exclude and module in exclude:
                return False
            if include and module not in include:
                return False
            if not include_standard and module in self.standard_modules:
                return False
        return True

    def is_doctype_in_scope(self, module: str | None, custom: bool) -> bool:
        """Whether a DocType is a customization worth capturing.

        UI-created (``custom``) DocTypes count wherever they live, including standard
        modules like "Stock". Non-custom DocTypes count only when shipped by a
        non-standard app; stock Frappe/ERPNext DocTypes are never customizations, so
        ``include_standard_apps`` does not pull them in.
        """
        include = self.scope.get("include_modules") or []
        exclude = self.scope.get("exclude_modules") or []

        if module in self.self_modules:
            return False
        if exclude and module in exclude:
            return False
        if include and module not in include:
            return False
        if custom:
            return True
        return bool(module) and module not in self.standard_modules

    @property
    def include_raw_source(self) -> bool:
        return bool(self.scope.get("include_raw_source", True))


class BaseCollector:
    """Base class for all collectors.

    Subclasses set ``key``, ``label`` and ``order`` and implement ``collect``.
    """

    key: str = ""
    label: str = ""
    #: lower runs earlier; keeps snapshot section ordering deterministic.
    order: int = 100

    def __init__(self, context: CollectorContext):
        self.context = context

    def collect(self) -> list[Artifact]:  # pragma: no cover - interface
        raise NotImplementedError

    # convenience passthroughs
    def in_scope(self, module: str | None) -> bool:
        return self.context.is_module_in_scope(module)
