from dev_vigilante import engine
from dev_vigilante.tests.fake_source import sample_site

SCOPE = {"include_raw_source": True, "include_standard_apps": False}


def _artifacts(source, previous=None):
    return engine.run(source, SCOPE, previous_snapshot=previous)


def test_collects_expected_artifacts():
    result = _artifacts(sample_site())
    keys = set(result["snapshot"]["artifacts"])
    assert "custom-field::Sales Order::dispatch_priority" in keys
    assert "property-setter::Sales Order-po_no-reqd" in keys
    assert "property-setter::Sales Order-main-default_print_format" in keys
    assert "client-script::SO Dispatch" in keys
    assert result["errors"] == []


def test_custom_doctypes_scope():
    artifacts = _artifacts(sample_site())["snapshot"]["artifacts"]
    doctypes = {a["name"] for a in artifacts.values() if a["collector"] == "custom_doctypes"}
    # UI-created DocType in a standard module + custom-app DocType; no stock DocTypes.
    assert doctypes == {"Delivery Slot", "Truck"}
    truck = artifacts["doctype::Truck"]
    assert truck["fields"]["workflows"] == ["Truck Approval"]


def test_property_setter_summary_and_grouping():
    artifacts = _artifacts(sample_site())["snapshot"]["artifacts"]
    ps = artifacts["property-setter::Sales Order-po_no-reqd"]
    assert ps["group"] == "Sales Order"
    assert "reqd" in ps["summary"] and "po_no" in ps["summary"]
    doctype_level = artifacts["property-setter::Sales Order-main-default_print_format"]
    assert doctype_level["fields"]["target"] is None


def test_denied_collector_is_skipped_not_fatal():
    source = sample_site()
    source.denied.add("Server Script")
    result = _artifacts(source)
    assert [s["collector"] for s in result["skipped"]] == ["server_scripts"]
    assert result["errors"] == []


def test_skipped_collector_carries_previous_artifacts_forward():
    first = _artifacts(sample_site())["snapshot"]
    source = sample_site()
    source.denied.add("Client Script")
    second = _artifacts(source, previous=first)
    assert "client-script::SO Dispatch" in second["snapshot"]["artifacts"]
    assert second["changes"]["summary"] == {"added": 0, "removed": 0, "modified": 0}


def test_unreadable_module_def_captures_only_ui_doctypes():
    source = sample_site()
    source.denied.add("Module Def")
    result = _artifacts(source)
    artifacts = result["snapshot"]["artifacts"]
    doctypes = {a["name"] for a in artifacts.values() if a["collector"] == "custom_doctypes"}
    assert doctypes == {"Delivery Slot"}
    assert any(s["collector"] == "context" for s in result["skipped"])


def test_rerun_without_changes_is_empty_diff():
    first = _artifacts(sample_site())["snapshot"]
    second = _artifacts(sample_site(), previous=first)
    assert second["changes"]["summary"] == {"added": 0, "removed": 0, "modified": 0}


def test_modified_property_setter_is_detected():
    first = _artifacts(sample_site())["snapshot"]
    source = sample_site()
    source.tables["Property Setter"][0]["value"] = "0"
    second = _artifacts(source, previous=first)
    modified = second["changes"]["modified"]
    assert [m["key"] for m in modified] == ["property-setter::Sales Order-po_no-reqd"]
    assert modified[0]["changed_fields"] == ["value"]
