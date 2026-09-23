from dev_vigilante import analysis

CLIENT_SCRIPT = """
frappe.ui.form.on('Sales Order', {
    refresh: function(frm) {
        set_priority(frm);
    },
    delivery_date: function(frm) {
        frm.set_value('dispatch_priority', 'High');
    }
});

function set_priority(frm) {
    frappe.set_route('query-report', 'Dispatch Report');
}
"""

SERVER_SCRIPT = """
def apply(doc, method=None):
    so = frappe.get_doc('Sales Order', doc.reference_name)
    frappe.db.set_value('Sales Order', so.name, 'status', 'Done')
"""


def test_form_events():
    events = analysis.extract_form_events(CLIENT_SCRIPT)
    assert "refresh" in events
    assert "delivery_date" in events


def test_js_functions():
    assert "set_priority" in analysis.extract_js_functions(CLIENT_SCRIPT)


def test_referenced_fields():
    fields = analysis.extract_referenced_fields(CLIENT_SCRIPT)
    assert "dispatch_priority" in fields


def test_referenced_reports():
    assert "Dispatch Report" in analysis.extract_referenced_reports(CLIENT_SCRIPT)


def test_py_functions_and_doctypes():
    assert "apply" in analysis.extract_py_functions(SERVER_SCRIPT)
    assert "Sales Order" in analysis.extract_py_referenced_doctypes(SERVER_SCRIPT)


def test_sql_helpers():
    sql = "SELECT name FROM `tabSales Order` WHERE status = %(status)s"
    assert "Sales Order" in analysis.extract_sql_doctypes(sql)
    assert "status" in analysis.extract_sql_filters(sql)
