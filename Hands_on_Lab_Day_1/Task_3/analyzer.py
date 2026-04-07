"""
analyzer.py — AST-driven static analysis engine.
Produces a structured ASTFindings dict consumed by the LLM reviewer.
"""

import ast
import textwrap
from dataclasses import dataclass, field
from typing import Any

# Python builtins that are commonly shadowed
_BUILTINS = frozenset(dir(__builtins__) if isinstance(__builtins__, dict) else dir(__builtins__))

@dataclass
class ASTFindings:
    syntax_error: dict | None = None          # {msg, line, col}
    functions: list[dict] = field(default_factory=list)
    classes: list[dict] = field(default_factory=list)
    imports: list[dict] = field(default_factory=list)
    globals_: list[str] = field(default_factory=list)
    control_flow: dict = field(default_factory=lambda: {
        "try_except": [], "with_blocks": 0,
        "async_defs": [], "comprehensions": 0
    })
    anti_patterns: list[dict] = field(default_factory=list)
    line_count: int = 0

    def to_dict(self) -> dict:
        return {
            "syntax_error": self.syntax_error,
            "line_count": self.line_count,
            "functions": self.functions,
            "classes": self.classes,
            "imports": self.imports,
            "globals": self.globals_,
            "control_flow": self.control_flow,
            "anti_patterns": self.anti_patterns,
        }


class _Visitor(ast.NodeVisitor):
    def __init__(self, source_lines: list[str]):
        self.source_lines = source_lines
        self.findings = ASTFindings(line_count=len(source_lines))
        self._scope_depth = 0  # for nesting detection
        self._imported_names: set[str] = set()

    # ── Imports ──────────────────────────────────────────────────────────────
    def visit_Import(self, node: ast.Import):
        for alias in node.names:
            name = alias.asname or alias.name
            self._imported_names.add(name.split(".")[0])
            self.findings.imports.append({
                "type": "import",
                "module": alias.name,
                "alias": alias.asname,
                "line": node.lineno,
            })
        self.generic_visit(node)

    def visit_ImportFrom(self, node: ast.ImportFrom):
        for alias in node.names:
            name = alias.asname or alias.name
            self._imported_names.add(name)
            self.findings.imports.append({
                "type": "from_import",
                "module": node.module or "",
                "name": alias.name,
                "alias": alias.asname,
                "line": node.lineno,
            })
        self.generic_visit(node)

    # ── Functions ─────────────────────────────────────────────────────────────
    def visit_FunctionDef(self, node: ast.FunctionDef):
        self._check_mutable_defaults(node)
        self._check_builtin_shadow(node)
        info = {
            "name": node.name,
            "line": node.lineno,
            "args": [a.arg for a in node.args.args],
            "decorators": [self._unparse(d) for d in node.decorator_list],
            "is_async": isinstance(node, ast.AsyncFunctionDef),
            "nesting_depth": self._scope_depth,
        }
        if self._scope_depth > 2:
            self.findings.anti_patterns.append({
                "type": "deep_nesting",
                "message": f"Function '{node.name}' defined at nesting depth {self._scope_depth}.",
                "line": node.lineno,
            })
        if isinstance(node, ast.AsyncFunctionDef):
            self.findings.control_flow["async_defs"].append(node.name)
        self.findings.functions.append(info)
        self._scope_depth += 1
        self.generic_visit(node)
        self._scope_depth -= 1

    visit_AsyncFunctionDef = visit_FunctionDef

    # ── Classes ───────────────────────────────────────────────────────────────
    def visit_ClassDef(self, node: ast.ClassDef):
        self._check_builtin_shadow(node)
        self.findings.classes.append({
            "name": node.name,
            "line": node.lineno,
            "bases": [self._unparse(b) for b in node.bases],
        })
        self._scope_depth += 1
        self.generic_visit(node)
        self._scope_depth -= 1

    # ── Control flow ──────────────────────────────────────────────────────────
    def visit_ExceptHandler(self, node: ast.ExceptHandler):
        if node.type is None:
            self.findings.anti_patterns.append({
                "type": "bare_except",
                "message": "Bare `except:` catches all exceptions including SystemExit and KeyboardInterrupt.",
                "line": node.lineno,
            })
            self.findings.control_flow["try_except"].append({"line": node.lineno, "bare": True})
        else:
            self.findings.control_flow["try_except"].append({
                "line": node.lineno,
                "bare": False,
                "type": self._unparse(node.type),
            })
        self.generic_visit(node)

    def visit_With(self, node: ast.With):
        self.findings.control_flow["with_blocks"] += 1
        self.generic_visit(node)

    def visit_ListComp(self, node):
        self.findings.control_flow["comprehensions"] += 1
        self.generic_visit(node)

    visit_SetComp = visit_DictComp = visit_GeneratorExp = visit_ListComp

    # ── Globals ───────────────────────────────────────────────────────────────
    def visit_Global(self, node: ast.Global):
        self.findings.globals_.extend(node.names)
        self.generic_visit(node)

    # ── Assign — mutable default check at module level ───────────────────────
    def visit_Assign(self, node: ast.Assign):
        # Detect list/dict/set literals assigned to names that shadow builtins
        for target in node.targets:
            if isinstance(target, ast.Name) and target.id in _BUILTINS:
                self.findings.anti_patterns.append({
                    "type": "shadow_builtin",
                    "message": f"Name '{target.id}' shadows a Python builtin.",
                    "line": node.lineno,
                })
        self.generic_visit(node)

    # ── Helpers ───────────────────────────────────────────────────────────────
    def _check_mutable_defaults(self, node: ast.FunctionDef):
        defaults = node.args.defaults + node.args.kw_defaults
        for default in defaults:
            if default is None:
                continue
            if isinstance(default, (ast.List, ast.Dict, ast.Set)):
                self.findings.anti_patterns.append({
                    "type": "mutable_default_arg",
                    "message": (
                        f"Function '{node.name}' has a mutable default argument "
                        f"({type(default).__name__}). Use None as default instead."
                    ),
                    "line": node.lineno,
                })

    def _check_builtin_shadow(self, node):
        name = node.name
        if name in _BUILTINS:
            self.findings.anti_patterns.append({
                "type": "shadow_builtin",
                "message": f"Definition '{name}' shadows a Python builtin.",
                "line": node.lineno,
            })

    @staticmethod
    def _unparse(node) -> str:
        try:
            return ast.unparse(node)
        except Exception:
            return "<unparseable>"


def analyze(source: str) -> ASTFindings:
    """Parse source and return ASTFindings. Handles syntax errors gracefully."""
    findings = ASTFindings()
    findings.line_count = source.count("\n") + 1

    try:
        tree = ast.parse(source)
    except SyntaxError as e:
        findings.syntax_error = {
            "message": str(e.msg),
            "line": e.lineno,
            "col": e.offset,
            "text": e.text,
        }
        return findings

    lines = source.splitlines()
    visitor = _Visitor(lines)
    visitor.visit(tree)
    return visitor.findings