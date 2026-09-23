"""Build a dependency graph from collected artifacts.

Pure and dependency-free. Nodes are artifacts (plus external targets referenced but
not themselves collected, e.g. a standard DocType). Edges point from an artifact to
each thing it depends on. Output is deterministic (sorted).
"""

from __future__ import annotations


def _external_id(dep_type: str, name: str) -> str:
    return f"ext::{dep_type}::{name}".lower()


def build_dependency_graph(artifacts: dict[str, dict]) -> dict:
    # Resolve a dependency {type,name} to a node id. Prefer a collected artifact.
    doctype_nodes = {
        a.get("name"): key
        for key, a in artifacts.items()
        if a.get("collector") == "custom_doctypes"
    }

    nodes: dict[str, dict] = {}
    edges: list[dict] = []

    for key in sorted(artifacts):
        artifact = artifacts[key]
        nodes[key] = {
            "id": key,
            "label": artifact.get("name"),
            "type": artifact.get("type"),
            "collector": artifact.get("collector"),
            "external": False,
        }

    for key in sorted(artifacts):
        artifact = artifacts[key]
        for dep in artifact.get("dependencies") or []:
            dep_type = dep.get("type")
            dep_name = dep.get("name")
            if not dep_name:
                continue

            if dep_type == "DocType" and dep_name in doctype_nodes:
                target_id = doctype_nodes[dep_name]
            else:
                target_id = _external_id(dep_type, dep_name)
                if target_id not in nodes:
                    nodes[target_id] = {
                        "id": target_id,
                        "label": dep_name,
                        "type": dep_type,
                        "collector": None,
                        "external": True,
                    }
            edges.append({"from": key, "to": target_id, "type": dep_type})

    # Deterministic ordering.
    edges = sorted(edges, key=lambda e: (e["from"], e["to"], e["type"]))
    seen = set()
    unique_edges = []
    for edge in edges:
        sig = (edge["from"], edge["to"], edge["type"])
        if sig not in seen:
            seen.add(sig)
            unique_edges.append(edge)

    ordered_nodes = [nodes[nid] for nid in sorted(nodes)]
    return {
        "node_count": len(ordered_nodes),
        "edge_count": len(unique_edges),
        "nodes": ordered_nodes,
        "edges": unique_edges,
    }
