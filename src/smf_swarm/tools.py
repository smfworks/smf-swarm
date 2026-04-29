"""SMF Swarm — Tool-calling integration for data gathering.

Optional extras: enables DuckDuckGo web search and Python REPL for
real data in the data gatherer node.

Usage:
    from smf_swarm.tools import ToolKit
    tools = ToolKit()
    result = tools.duckduckgo_search("NVIDIA market cap 2026 forecast")
    # result is a dict with links + snippets
"""

from __future__ import annotations

import traceback
from typing import Optional


class ToolKit:
    """Lightweight tool runner for data gathering enrichment."""

    _ddgs: Optional[object] = None

    def __init__(self):
        self._check_ddgs()

    def _check_ddgs(self):
        if self._ddgs is None:
            try:
                from duckduckgo_search import DDGS

                self._ddgs = DDGS()
            except ImportError:
                self._ddgs = False

    @property
    def search_available(self) -> bool:
        return self._ddgs is not False

    def duckduckgo_search(self, query: str, max_results: int = 5) -> dict:
        """Free web search via DuckDuckGo. Returns links + snippets."""
        if not self.search_available:
            return {
                "tool": "duckduckgo_search",
                "query": query,
                "results": [],
                "error": "duckduckgo-search not installed. Install with: pip install duckduckgo-search",
            }
        try:
            results = self._ddgs.text(query, max_results=max_results)
            return {
                "tool": "duckduckgo_search",
                "query": query,
                "results": [
                    {
                        "title": r.get("title", ""),
                        "href": r.get("href", ""),
                        "body": r.get("body", ""),
                    }
                    for r in results
                ],
                "error": None,
            }
        except Exception as e:
            return {
                "tool": "duckduckgo_search",
                "query": query,
                "results": [],
                "error": str(e),
            }

    def python_repl(self, code: str) -> dict:
        """Execute Python math/finance in an isolated REPL."""
        # Restricted globals for safety
        safe_globals = {
            "__builtins__": {
                "abs": abs,
                "all": all,
                "any": any,
                "bool": bool,
                "complex": complex,
                "dict": dict,
                "divmod": divmod,
                "float": float,
                "int": int,
                "len": len,
                "list": list,
                "max": max,
                "min": min,
                "pow": pow,
                "range": range,
                "round": round,
                "sorted": sorted,
                "str": str,
                "sum": sum,
                "tuple": tuple,
                "zip": zip,
                "enumerate": enumerate,
                "filter": filter,
                "map": map,
                "print": print,
            }
        }
        safe_locals = {}
        output_lines = []

        # Capture stdout
        import io
        import sys

        old_stdout = sys.stdout
        sys.stdout = buffer = io.StringIO()
        try:
            exec(code, safe_globals, safe_locals)
            captured = buffer.getvalue()
            # Also capture the last expression value if present
            last_value = safe_locals.get("__result__", None)
            result = {
                "tool": "python_repl",
                "code": code,
                "stdout": captured.strip(),
                "last_value": str(last_value) if last_value is not None else None,
                "locals": {
                    k: str(v) for k, v in safe_locals.items() if not k.startswith("__")
                },
                "error": None,
            }
        except Exception:
            result = {
                "tool": "python_repl",
                "code": code,
                "stdout": buffer.getvalue().strip(),
                "error": traceback.format_exc(),
            }
        finally:
            sys.stdout = old_stdout

        return result
