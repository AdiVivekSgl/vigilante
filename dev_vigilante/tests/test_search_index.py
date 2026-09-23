from dev_vigilante import search_index
from dev_vigilante.tests import factories


def _artifacts(items):
    return {a.key: a.to_dict() for a in items}


def test_entries_sorted_by_key():
    a = factories.custom_field(fieldname="zeta")
    b = factories.custom_field(fieldname="alpha")
    index = search_index.build_search_index(_artifacts([a, b]))
    keys = [e["key"] for e in index["entries"]]
    assert keys == sorted(keys)
    assert index["count"] == 2


def test_keywords_and_doctype_populated():
    a = factories.custom_field()
    index = search_index.build_search_index(_artifacts([a]))
    entry = index["entries"][0]
    assert entry["doctype"] == "Sales Order"
    assert "dispatch_priority" in entry["keywords"]
    assert "order" in entry["keywords"]  # tokenized from "Sales Order"


def test_dependencies_flattened():
    a = factories.client_script()
    index = search_index.build_search_index(_artifacts([a]))
    assert "Sales Order" in index["entries"][0]["dependencies"]
