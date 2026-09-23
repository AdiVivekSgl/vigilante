"""ZIP / folder bundling of the Markdown + JSON exports.

Deterministic: files are written in sorted order with a fixed ZIP timestamp so the same
snapshot content produces byte-identical archives.
"""

from __future__ import annotations

import io
import os
import zipfile

from dev_vigilante.exporters.json_exporter import JsonExporter
from dev_vigilante.exporters.markdown_exporter import MarkdownExporter

_FIXED_TIME = (1980, 1, 1, 0, 0, 0)

ROOT_FOLDER = "developer_snapshot"

# Vigilante Settings ``default_export_format`` values.
MARKDOWN_ONLY = "Markdown only"
JSON_ONLY = "JSON only"


def build_all_files(snapshot: dict, export_format: str | None = None) -> dict:
    """Relpath -> content map for the ``developer_snapshot`` tree.

    ``export_format`` restricts the tree to Markdown or JSON; any other value
    (``ZIP``, ``Git-ready folder``, ``None``) produces both.
    """
    files: dict[str, str] = {}
    if export_format != JSON_ONLY:
        markdown = MarkdownExporter(link_machine_readable=export_format != MARKDOWN_ONLY)
        files.update(markdown.build_files(snapshot))
    if export_format != MARKDOWN_ONLY:
        files.update(JsonExporter().build_files(snapshot))
    return files


def build_zip_bytes(
    snapshot: dict, root: str = ROOT_FOLDER, export_format: str | None = None
) -> bytes:
    files = build_all_files(snapshot, export_format)
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w", zipfile.ZIP_DEFLATED) as zf:
        for relpath in sorted(files):
            content = files[relpath]
            if isinstance(content, str):
                content = content.encode("utf-8")
            info = zipfile.ZipInfo(f"{root}/{relpath}", date_time=_FIXED_TIME)
            info.compress_type = zipfile.ZIP_DEFLATED
            info.external_attr = 0o644 << 16
            zf.writestr(info, content)
    return buffer.getvalue()


def write_folder(files: dict, output_directory: str) -> str:
    """Write ``files`` to ``<output_directory>/developer_snapshot`` and return that path.

    Files left over from a previous snapshot (e.g. a deleted script's page) are removed
    so the folder mirrors the current ERP state and Git sees the deletion. Only the
    ``developer_snapshot`` subfolder is ever touched; dot-folders such as ``.git`` are
    left alone.
    """
    if not output_directory or not os.path.isabs(output_directory):
        raise ValueError("Git-ready output directory must be an absolute path.")

    root = os.path.realpath(os.path.join(output_directory, ROOT_FOLDER))
    wanted = set()
    for relpath, content in files.items():
        target = os.path.realpath(os.path.join(root, *relpath.split("/")))
        if os.path.commonpath([root, target]) != root:
            raise ValueError(f"Refusing to write outside the snapshot folder: {relpath}")
        wanted.add(target)
        os.makedirs(os.path.dirname(target), exist_ok=True)
        data = content.encode("utf-8") if isinstance(content, str) else content
        with open(target, "wb") as fh:
            fh.write(data)

    for dirpath, dirnames, filenames in os.walk(root, topdown=False):
        if _is_hidden(root, dirpath):
            continue
        for filename in filenames:
            path = os.path.join(dirpath, filename)
            if path not in wanted and not filename.startswith("."):
                os.remove(path)
        if dirpath != root and not os.listdir(dirpath):
            os.rmdir(dirpath)
    return root


def _is_hidden(root: str, dirpath: str) -> bool:
    rel = os.path.relpath(dirpath, root)
    return rel != "." and any(part.startswith(".") for part in rel.split(os.sep))
