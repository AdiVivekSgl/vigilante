from dev_vigilante import change_detection
from dev_vigilante.tests import factories


def _snapshot(artifacts):
    return {"artifacts": {a.key: a.to_dict() for a in artifacts}}


def test_added_removed_modified():
    field_a = factories.custom_field(fieldname="a")
    field_b = factories.custom_field(fieldname="b")
    field_a_changed = factories.custom_field(fieldname="a", mandatory=True)

    previous = _snapshot([field_a, field_b])
    current = _snapshot([field_a_changed])  # b removed, a modified

    result = change_detection.diff(previous, current)
    assert result["summary"] == {"added": 0, "removed": 1, "modified": 1}
    assert result["removed"][0]["name"].endswith("/ b")
    assert result["modified"][0]["name"].endswith("/ a")
    assert "mandatory" in result["modified"][0]["changed_fields"]


def test_added_when_no_previous():
    field_a = factories.custom_field(fieldname="a")
    result = change_detection.diff(None, _snapshot([field_a]))
    assert result["summary"]["added"] == 1
    assert result["summary"]["removed"] == 0


def test_no_changes_between_identical_snapshots():
    a = factories.custom_field()
    snap = _snapshot([a])
    result = change_detection.diff(snap, snap)
    assert change_detection.is_empty(result)


def test_highlights_new_fields_and_changed_scripts():
    cf = factories.custom_field(fieldname="new_one")
    cs = factories.client_script()
    cs_changed = factories.client_script(enabled=False)

    previous = _snapshot([cs])
    current = _snapshot([cf, cs_changed])

    result = change_detection.diff(previous, current)
    assert cf.fields["fieldname"] in " ".join(result["highlights"]["new_fields"]) or \
        cf.name in result["highlights"]["new_fields"]
    assert cs.name in result["highlights"]["changed_scripts"]
