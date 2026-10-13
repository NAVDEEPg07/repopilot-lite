
"""Static Python import and change-impact analysis. Uploaded code is never executed."""
import ast
from collections import deque
from pathlib import PurePosixPath


def _module_name(path: str) -> str:
    p = PurePosixPath(path)
    parts = list(p.parts)
    if not parts or p.suffix != ".py":
        return ""
    if parts[-1] == "__init__.py":
        parts = parts[:-1]
    else:
        parts[-1] = p.stem
    return ".".join(parts)


def analyze_sources(sources: dict[str, str]) -> dict:
    """Analyze Python imports and resolve them to files inside the uploaded project."""
    python_paths = sorted(p for p in sources if p.endswith(".py"))
    module_to_path = {}

    for path in python_paths:
        module = _module_name(path)
        if module:
            module_to_path.setdefault(module, path)

    # Also map unique module names, e.g. user_service.py inside sample_project/.
    leaf_modules = {}
    for module, path in module_to_path.items():
        leaf_modules.setdefault(module.rsplit(".", 1)[-1], []).append(path)

    for leaf, paths in leaf_modules.items():
        if len(paths) == 1:
            module_to_path.setdefault(leaf, paths[0])

    dependencies = {p: set() for p in python_paths}
    warnings = []
    unresolved = []

    for path in python_paths:
        try:
            tree = ast.parse(sources[path], filename=path)
        except (SyntaxError, ValueError) as exc:
            message = exc.msg if isinstance(exc, SyntaxError) else str(exc)
            warnings.append({"file": path, "message": f"Python parsing failed: {message}"})
            continue

        current_module = _module_name(path)
        is_init = PurePosixPath(path).name == "__init__.py"
        current_package = current_module if is_init else current_module.rpartition(".")[0]

        for node in ast.walk(tree):
            names_to_resolve = []

            if isinstance(node, ast.Import):
                names_to_resolve.extend((alias.name, 0) for alias in node.names)

            elif isinstance(node, ast.ImportFrom):
                level = node.level
                module_name = node.module or ""

                if level:
                    package_parts = current_package.split(".") if current_package else []
                    keep = max(0, len(package_parts) - level + 1)
                    base = package_parts[:keep]
                    base_name = ".".join(base + ([module_name] if module_name else []))
                else:
                    base_name = module_name

                if base_name:
                    names_to_resolve.append((base_name, level))
                for alias in node.names:
                    if alias.name != "*":
                        alias_module = ".".join(filter(None, [base_name, alias.name]))
                        names_to_resolve.append((alias_module, level))

            for name, level in names_to_resolve:
                candidates = [name] if name else []

                # Try parent modules for imports such as package.module.function.
                pieces = name.split(".") if name else []
                candidates.extend(
                    ".".join(pieces[:i])
                    for i in range(len(pieces) - 1, 0, -1)
                )

                resolved = None
                for candidate in candidates:
                    if candidate in module_to_path:
                        resolved = module_to_path[candidate]
                        break

                if resolved and resolved != path:
                    dependencies[path].add(resolved)
                elif name:
                    top = name.split(".")[0]
                    if top not in module_to_path and name not in {"os", "sys"}:
                        unresolved.append({
                            "file": path,
                            "import": name,
                            "line": getattr(node, "lineno", None)
                        })

    edges = [
        {"from": importer, "to": imported}
        for importer in sorted(dependencies)
        for imported in sorted(dependencies[importer])
    ]

    files = [
        {"path": path, "type": "python" if path.endswith(".py") else "file"}
        for path in sorted(sources)
    ]

    return {
        "files": files,
        "python_files": python_paths,
        "dependencies": {p: sorted(v) for p, v in dependencies.items()},
        "edges": edges,
        "unresolved_imports": unresolved,
        "warnings": warnings,
    }


def impact_for(analysis: dict, selected_file: str) -> dict:
    """Return direct and indirect dependents of a selected Python file."""
    python_files = set(analysis.get("python_files", []))

    if selected_file not in python_files:
        raise ValueError("Select a Python file from the analyzed project.")

    reverse = {p: set() for p in python_files}

    for edge in analysis.get("edges", []):
        reverse.setdefault(edge["to"], set()).add(edge["from"])

    queue = deque([(selected_file, [selected_file])])
    visited = {selected_file}
    direct = []
    indirect = []
    paths = []

    while queue:
        current, path = queue.popleft()

        for dependent in sorted(reverse.get(current, set())):
            if dependent in visited:
                continue

            visited.add(dependent)
            next_path = path + [dependent]
            distance = len(next_path) - 2

            item = {
                "file": dependent,
                "path": next_path,
                "distance": distance
            }

            paths.append(item)
            (direct if distance == 0 else indirect).append(item)
            queue.append((dependent, next_path))

    return {
        "selected_file": selected_file,
        "direct_dependents": direct,
        "indirect_dependents": indirect,
        "dependency_paths": paths,
        "note": "These files may be affected by a change; this does not mean they are broken."
    }
