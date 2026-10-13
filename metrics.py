import ast
import io
import tokenize


def analyze_metrics(sources):
    results = []

    for path, source in sorted(sources.items()):
        if not path.endswith(".py"):
            continue

        try:
            tree = ast.parse(source, filename=path)
        except (SyntaxError, ValueError) as exc:
            results.append({"file": path, "lines": len(source.splitlines()), "loc": None, "functions": 0, "classes": 0, "complexity": None, "long_functions": [], "error": str(exc)})
            continue

        functions = [n for n in ast.walk(tree) if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef))]
        classes = [n for n in ast.walk(tree) if isinstance(n, ast.ClassDef)]
        decisions = 0

        for node in ast.walk(tree):
            if isinstance(node, (ast.If, ast.For, ast.AsyncFor, ast.While, ast.IfExp, ast.ExceptHandler, ast.Assert)):
                decisions += 1
            elif isinstance(node, ast.BoolOp):
                decisions += max(0, len(node.values) - 1)
            elif isinstance(node, ast.comprehension):
                decisions += len(node.ifs)

        long_functions = []
        for node in functions:
            start = node.lineno
            end = getattr(node, "end_lineno", start)
            if end - start + 1 > 30:
                long_functions.append({"name": node.name, "start_line": start, "end_line": end, "lines": end - start + 1})

        try:
            tokens = tokenize.generate_tokens(io.StringIO(source).readline)
            code_lines = {t.start[0] for t in tokens if t.type not in (tokenize.ENCODING, tokenize.NL, tokenize.NEWLINE, tokenize.INDENT, tokenize.DEDENT, tokenize.COMMENT, tokenize.ENDMARKER) and t.string.strip()}
            loc = len(code_lines)
        except (tokenize.TokenError, IndentationError):
            loc = None

        results.append({"file": path, "lines": len(source.splitlines()), "loc": loc, "functions": len(functions), "classes": len(classes), "complexity": 1 + decisions, "long_functions": long_functions, "error": None})

    return results
