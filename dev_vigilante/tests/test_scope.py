from dev_vigilante.collectors.base import CollectorContext

_APPS = {
    "Stock": "erpnext",
    "Core": "frappe",
    "Logistics": "acme_custom",
    "Dev Vigilante": "dev_vigilante",
}


def _ctx(**scope):
    return CollectorContext(scope, _APPS)


def test_ui_custom_doctype_in_standard_module_is_captured():
    assert _ctx().is_doctype_in_scope("Stock", custom=True)


def test_standard_doctypes_are_never_captured():
    assert not _ctx().is_doctype_in_scope("Stock", custom=False)
    assert not _ctx(include_standard_apps=True).is_doctype_in_scope("Core", custom=False)


def test_custom_app_doctypes_are_captured():
    assert _ctx().is_doctype_in_scope("Logistics", custom=False)


def test_own_app_is_excluded_everywhere():
    ctx = _ctx(include_standard_apps=True)
    assert not ctx.is_doctype_in_scope("Dev Vigilante", custom=False)
    assert not ctx.is_module_in_scope("Dev Vigilante")


def test_exclude_list_wins_over_custom_flag():
    assert not _ctx(exclude_modules=["Stock"]).is_doctype_in_scope("Stock", custom=True)


def test_include_list_restricts_scope():
    ctx = _ctx(include_modules=["Logistics"])
    assert ctx.is_doctype_in_scope("Logistics", custom=False)
    assert not ctx.is_doctype_in_scope("Stock", custom=True)
