import argparse
import os

import pytest

from dev_vigilante import cli
from dev_vigilante.tests.fake_source import sample_site


def _refresh(source, output, **kw):
    args = argparse.Namespace(output=str(output), no_raw_source=False, force=False, **kw)
    lines = []
    code = cli.cmd_refresh(args, source, out=lines.append)
    return code, lines


def test_first_refresh_writes_snapshot(tmp_path):
    code, lines = _refresh(sample_site(), tmp_path)
    snap = tmp_path / "developer_snapshot"
    assert code == 0
    assert (snap / "README.md").is_file()
    assert (snap / "snapshot.json").is_file()
    assert (snap / "property_setters" / "Sales-Order.md").is_file()
    assert (snap / "custom_fields" / "Sales-Order.md").is_file()
    assert any("Wrote" in line for line in lines)


def test_second_refresh_without_changes_leaves_folder_alone(tmp_path):
    _refresh(sample_site(), tmp_path)
    before = (tmp_path / "developer_snapshot" / "snapshot.json").read_bytes()
    code, lines = _refresh(sample_site(), tmp_path)
    assert code == 0
    assert any("No changes" in line for line in lines)
    assert (tmp_path / "developer_snapshot" / "snapshot.json").read_bytes() == before


def test_refresh_after_change_rewrites_and_reports(tmp_path):
    _refresh(sample_site(), tmp_path)
    source = sample_site()
    source.tables["Client Script"] = []
    code, lines = _refresh(source, tmp_path)
    assert code == 0
    assert any("-1" in line for line in lines)
    assert not (tmp_path / "developer_snapshot" / "scripts" / "client").exists()
    changes = (tmp_path / "developer_snapshot" / "changelog" / "CHANGES.md").read_text(encoding="utf-8")
    assert "SO Dispatch" in changes


def test_refuses_to_write_inside_the_public_repo():
    with pytest.raises(cli.CliError):
        cli.resolve_output(str(cli._TOOL_REPO / "erpnext-config"))


def test_output_is_required(monkeypatch):
    monkeypatch.delenv("VIGILANTE_OUTPUT", raising=False)
    with pytest.raises(cli.CliError):
        cli.resolve_output(None)


def test_env_file_parsing(tmp_path, monkeypatch):
    for key in ("FRAPPE_URL", "FRAPPE_API_KEY", "FRAPPE_API_SECRET"):
        monkeypatch.delenv(key, raising=False)
    monkeypatch.setenv("FRAPPE_API_SECRET", "from-environment")
    env = tmp_path / ".env"
    env.write_text(
        "﻿# comment\nFRAPPE_URL = https://erp.example.com\n"
        "FRAPPE_API_KEY='abc'\nFRAPPE_API_SECRET=from-file\n",
        encoding="utf-8",
    )
    cli.load_env_file(env)
    assert os.environ["FRAPPE_URL"] == "https://erp.example.com"
    assert os.environ["FRAPPE_API_KEY"] == "abc"
    assert os.environ["FRAPPE_API_SECRET"] == "from-environment"  # not overridden


def test_missing_credentials_is_a_friendly_error(monkeypatch):
    for key in ("FRAPPE_URL", "FRAPPE_API_KEY", "FRAPPE_API_SECRET"):
        monkeypatch.delenv(key, raising=False)
    with pytest.raises(cli.CliError, match="FRAPPE_URL"):
        cli.make_source()
