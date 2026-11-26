import ast


def file_path_to_module(file_path: str) -> str:
    """Convert a repository file path to a dotted Python module name."""
    normalized = file_path.strip("/")
    if normalized.endswith("/__init__.py"):
        normalized = normalized[: -len("/__init__.py")]
    elif normalized == "__init__.py":
        return "__init__"
    elif normalized.endswith(".py"):
        normalized = normalized[:-3]
    return normalized.replace("/", ".")


def _extract_func_info(node: ast.FunctionDef | ast.AsyncFunctionDef) -> dict:
    args = [arg.arg for arg in node.args.args]
    return {
        "name": node.name,
        "line_start": node.lineno,
        "line_end": getattr(node, "end_lineno", node.lineno),
        "args": args,
        "is_async": isinstance(node, ast.AsyncFunctionDef),
    }


def _get_base_name(node: ast.expr) -> str:
    if isinstance(node, ast.Name):
        return node.id
    if isinstance(node, ast.Attribute):
        return f"{_get_base_name(node.value)}.{node.attr}"
    if isinstance(node, ast.Subscript):
        return _get_base_name(node.value)
    return "expr"


def analyze_python_source(file_path: str, source: str) -> dict:
    """Parse Python source code using the built-in AST module without executing it."""
    module_name = file_path_to_module(file_path)

    try:
        tree = ast.parse(source, filename=file_path)
    except SyntaxError as exc:
        return {
            "file_path": file_path,
            "module_name": module_name,
            "parse_error": f"SyntaxError at line {exc.lineno}: {exc.msg}",
            "classes": [],
            "functions": [],
            "methods_count": 0,
            "imports": [],
        }
    except ValueError as exc:
        return {
            "file_path": file_path,
            "module_name": module_name,
            "parse_error": f"ValueError: {exc}",
            "classes": [],
            "functions": [],
            "methods_count": 0,
            "imports": [],
        }

    classes: list[dict] = []
    functions: list[dict] = []
    imports: list[dict] = []
    methods_count = 0

    for node in tree.body:
        if isinstance(node, ast.ClassDef):
            methods: list[dict] = []
            for item in node.body:
                if isinstance(item, (ast.FunctionDef, ast.AsyncFunctionDef)):
                    methods.append(_extract_func_info(item))
                    methods_count += 1

            classes.append(
                {
                    "name": node.name,
                    "line_start": node.lineno,
                    "line_end": getattr(node, "end_lineno", node.lineno),
                    "bases": [_get_base_name(base) for base in node.bases],
                    "methods": methods,
                }
            )
        elif isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            functions.append(_extract_func_info(node))

    # Walk all nodes for imports (including conditional or function-scoped imports)
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                imports.append(
                    {
                        "kind": "import",
                        "module": alias.name,
                        "names": [alias.asname or alias.name],
                        "level": 0,
                        "line_number": node.lineno,
                    }
                )
        elif isinstance(node, ast.ImportFrom):
            imports.append(
                {
                    "kind": "from",
                    "module": node.module or "",
                    "names": [alias.name for alias in node.names],
                    "level": node.level or 0,
                    "line_number": node.lineno,
                }
            )

    return {
        "file_path": file_path,
        "module_name": module_name,
        "parse_error": None,
        "classes": classes,
        "functions": functions,
        "methods_count": methods_count,
        "imports": imports,
    }
