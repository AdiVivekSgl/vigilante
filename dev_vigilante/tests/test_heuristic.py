from dev_vigilante.summarizers import heuristic
from dev_vigilante.tests import factories


def test_custom_field_summary_mentions_field_and_doctype():
    a = factories.custom_field()
    summary = heuristic.summarize(a)
    assert "Dispatch Priority" in summary
    assert "Sales Order" in summary
    assert summary.endswith(".")


def test_custom_field_flags_rendered():
    a = factories.custom_field(mandatory=True, read_only=True)
    summary = heuristic.summarize(a)
    assert "mandatory" in summary
    assert "read-only" in summary


def test_fetch_from_rendered():
    a = factories.custom_field(fetch_from="customer.customer_name")
    assert "fetched from customer.customer_name" in heuristic.summarize(a)


def test_client_script_summary():
    a = factories.client_script()
    summary = heuristic.summarize(a)
    assert "client script" in summary.lower()
    assert "Sales Order" in summary
    assert "set_priority" in summary


def test_summary_is_deterministic():
    a = factories.custom_field()
    assert heuristic.summarize(a) == heuristic.summarize(a)


def test_unknown_collector_falls_back_to_generic():
    from dev_vigilante.artifact import Artifact

    a = Artifact(collector="reports", type="Report", name="Sales Register", key="report::x")
    assert heuristic.summarize(a) == "Report: Sales Register."
