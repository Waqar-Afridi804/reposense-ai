import re


def _sanitize_mermaid_id(raw: str) -> str:
    cleaned = re.sub(r"[^A-Za-z0-9_]", "_", raw)
    if not cleaned or cleaned[0].isdigit():
        cleaned = "m_" + cleaned
    return cleaned


def _resolve_relative_module(importing_file: str, importing_module: str, level: int, target_module: str) -> str:
    """Resolve a relative import (e.g. from .foo import bar) to a dotted module path."""
    is_init = importing_file.endswith("/__init__.py") or importing_file == "__init__.py"
    parts = importing_module.split(".") if importing_module != "__init__" else []
    package_parts = parts if is_init else parts[:-1]

    up = max(level - 1, 0)
    if up > len(package_parts):
        base_parts: list[str] = []
    else:
        base_parts = package_parts[: len(package_parts) - up] if up > 0 else package_parts

    if target_module:
        return ".".join([*base_parts, target_module]) if base_parts else target_module
    return ".".join(base_parts)


def build_dependency_graph(ast_results: list[dict]) -> dict:
    """Build internal and external/unresolved dependency graph from AST import results."""
    module_to_file: dict[str, str] = {}
    alias_to_module: dict[str, str] = {}

    for item in ast_results:
        mod = item["module_name"]
        fpath = item["file_path"]
        module_to_file[mod] = fpath
        alias_to_module[mod] = mod
        if mod.startswith("src."):
            alias_to_module[mod[len("src."):]] = mod

    def match_internal(candidate: str) -> str | None:
        if not candidate:
            return None
        if candidate in alias_to_module:
            return alias_to_module[candidate]
        # Also match parent package when importing a symbol from a module (e.g., from pkg.mod import Func)
        parts = candidate.split(".")
        while len(parts) > 1:
            parts.pop()
            parent = ".".join(parts)
            if parent in alias_to_module:
                return alias_to_module[parent]
        return None

    internal_edges_map: dict[tuple[str, str], set[int]] = {}
    external_edges_map: dict[tuple[str, str], set[int]] = {}
    external_packages: set[str] = set()

    for item in ast_results:
        source_mod = item["module_name"]
        source_file = item["file_path"]

        for imp in item.get("imports", []):
            level = imp.get("level", 0)
            raw_mod = imp.get("module", "")
            line_no = imp.get("line_number", 0)

            if level > 0:
                resolved_target = _resolve_relative_module(source_file, source_mod, level, raw_mod)
                matched = match_internal(resolved_target)
                if not matched and imp.get("names"):
                    for imported_name in imp["names"]:
                        sub_candidate = f"{resolved_target}.{imported_name}" if resolved_target else imported_name
                        matched = match_internal(sub_candidate)
                        if matched:
                            break
                if matched and matched != source_mod:
                    internal_edges_map.setdefault((source_mod, matched), set()).add(line_no)
                elif resolved_target:
                    ext_name = resolved_target.split(".")[0]
                    external_packages.add(ext_name)
                    external_edges_map.setdefault((source_mod, ext_name), set()).add(line_no)
            else:
                matched = match_internal(raw_mod)
                if matched and matched != source_mod:
                    internal_edges_map.setdefault((source_mod, matched), set()).add(line_no)
                elif raw_mod:
                    top_pkg = raw_mod.split(".")[0]
                    external_packages.add(top_pkg)
                    external_edges_map.setdefault((source_mod, top_pkg), set()).add(line_no)

    nodes: list[dict] = []
    seen_nodes: set[str] = set()

    for mod, fpath in sorted(module_to_file.items()):
        nodes.append({"id": mod, "label": mod, "type": "internal", "file_path": fpath})
        seen_nodes.add(mod)

    for ext in sorted(external_packages):
        ext_id = f"ext:{ext}"
        if ext_id not in seen_nodes:
            nodes.append({"id": ext_id, "label": ext, "type": "external", "file_path": None})
            seen_nodes.add(ext_id)

    edges: list[dict] = []
    for (src, dst), lines in sorted(internal_edges_map.items()):
        edges.append(
            {
                "source": src,
                "target": dst,
                "target_type": "internal",
                "relationship": "imports",
                "line_numbers": sorted(lines),
            }
        )
    for (src, ext), lines in sorted(external_edges_map.items()):
        edges.append(
            {
                "source": src,
                "target": f"ext:{ext}",
                "target_type": "external_or_unresolved",
                "relationship": "imports",
                "line_numbers": sorted(lines),
            }
        )

    mermaid = generate_mermaid_flowchart(nodes, edges)

    return {
        "nodes": nodes,
        "edges": edges,
        "internal_dependency_count": len(internal_edges_map),
        "external_dependencies": sorted(external_packages),
        "mermaid": mermaid,
    }


def generate_mermaid_flowchart(nodes: list[dict], edges: list[dict], max_edges: int = 60) -> str:
    """Render a Mermaid.js flowchart LR diagram from nodes and edges."""
    if not nodes:
        return 'flowchart LR\n  empty["No Python modules detected"]'

    lines = ["flowchart LR"]
    node_ids: dict[str, str] = {}
    used_ids: set[str] = set()

    for node in nodes:
        base_id = _sanitize_mermaid_id(node["id"])
        candidate = base_id
        counter = 1
        while candidate in used_ids:
            counter += 1
            candidate = f"{base_id}_{counter}"
        used_ids.add(candidate)
        node_ids[node["id"]] = candidate

    # Prioritize internal edges first, then external edges up to max_edges
    sorted_edges = sorted(edges, key=lambda e: (0 if e["target_type"] == "internal" else 1, e["source"], e["target"]))
    displayed_edges = sorted_edges[:max_edges]

    referenced_nodes: set[str] = set()
    for edge in displayed_edges:
        referenced_nodes.add(edge["source"])
        referenced_nodes.add(edge["target"])

    # If no edges exist, show up to 20 internal modules
    if not referenced_nodes:
        for node in [n for n in nodes if n["type"] == "internal"][:20]:
            referenced_nodes.add(node["id"])

    for node in nodes:
        if node["id"] not in referenced_nodes:
            continue
        mid = node_ids[node["id"]]
        label = re.sub(r'["\'<>()\[\]{};]', " ", node["label"]).strip() or "module"
        if node["type"] == "external":
            lines.append(f'  {mid}(["{label} (external)"])')
        else:
            lines.append(f'  {mid}["{label}"]')

    for edge in displayed_edges:
        src_id = node_ids[edge["source"]]
        dst_id = node_ids[edge["target"]]
        if edge["target_type"] == "internal":
            lines.append(f"  {src_id} --> {dst_id}")
        else:
            lines.append(f"  {src_id} -.-> {dst_id}")

    return "\n".join(lines)
