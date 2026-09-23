from dev_vigilante import dependency, search_index
from dev_vigilante.exporters.markdown_exporter import MarkdownExporter
from dev_vigilante.exporters.zip_exporter import build_all_files, build_zip_bytes
from dev_vigilante.tests import factories


def _snapshot():
    artifacts = {a.key: a.to_dict() for a in [factories.custom_field(), factories.client_script()]}
    return {
        "meta": {"counts": {"custom_fields": 1, "client_scripts": 1, "total": 2}},
        "collectors": [
            {"key": "custom_fields", "label": "Custom Fields", "count": 1},
            {"key": "client_scripts", "label": "Client Scripts", "count": 1},
        ],
        "artifacts": artifacts,
        "dependency_graph": dependency.build_dependency_graph(artifacts),
        "search_index": search_index.build_search_index(artifacts),
        "changes": {"summary": {"added": 2, "removed": 0, "modified": 0}, "added": [], "removed": [], "modified": []},
    }


def test_markdown_produces_expected_pages():
    files = MarkdownExporter().build_files(_snapshot())
    assert "README.md" in files
    assert "custom_fields/Sales-Order.md" in files
    assert "scripts/client/SO-Dispatch.md" in files
    assert "# Custom Fields — Sales Order" in files["custom_fields/Sales-Order.md"]


def test_all_files_include_json_and_search():
    files = build_all_files(_snapshot())
    assert "snapshot.json" in files
    assert "search.json" in files
    assert "dependency/dependency_graph.json" in files


def test_zip_is_deterministic():
    snap = _snapshot()
    assert build_zip_bytes(snap) == build_zip_bytes(snap)


def test_zip_contains_root_folder():
    import io
    import zipfile

    data = build_zip_bytes(_snapshot())
    with zipfile.ZipFile(io.BytesIO(data)) as zf:
        names = zf.namelist()
    assert any(n.startswith("developer_snapshot/") for n in names)
    assert "developer_snapshot/README.md" in names


def test_markdown_only_omits_json_and_its_links():
    files = build_all_files(_snapshot(), "Markdown only")
    assert "README.md" in files
    assert not any(p.endswith(".json") for p in files)
    assert "snapshot.json" not in files["README.md"]


def test_json_only_omits_markdown():
    files = build_all_files(_snapshot(), "JSON only")
    assert "snapshot.json" in files
    assert not any(p.endswith(".md") for p in files)


def test_colliding_names_get_distinct_pages():
    artifacts = {
        a.key: a.to_dict()
        for a in [factories.client_script(name="SO/Dispatch"), factories.client_script(name="SO Dispatch")]
    }
    files = MarkdownExporter().build_files({"meta": {}, "artifacts": artifacts})
    pages = [p for p in files if p.startswith("scripts/client/")]
    assert len(pages) == 2


def test_write_folder_removes_stale_files(tmp_path):
    from dev_vigilante.exporters.zip_exporter import write_folder

    root = write_folder({"README.md": "a", "scripts/old.md": "b"}, str(tmp_path))
    (tmp_path / "developer_snapshot" / ".git").mkdir()
    (tmp_path / "developer_snapshot" / ".git" / "HEAD").write_text("ref")
    write_folder({"README.md": "c"}, str(tmp_path))

    snap = tmp_path / "developer_snapshot"
    assert (snap / "README.md").read_text() == "c"
    assert not (snap / "scripts").exists()
    assert (snap / ".git" / "HEAD").exists()
    assert root.endswith("developer_snapshot")


def test_write_folder_requires_absolute_path():
    import pytest

    from dev_vigilante.exporters.zip_exporter import write_folder

    with pytest.raises(ValueError):
        write_folder({"README.md": "a"}, "relative/dir")
