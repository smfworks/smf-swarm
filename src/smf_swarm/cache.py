"""SMF Swarm — LLM response caching with diskcache.

Caches LLM responses keyed by (prompt_hash, model_config_hash) to
eliminate redundant calls during repeated experiments or identical queries.
"""

from __future__ import annotations

import hashlib
import json
from typing import Optional, Any

from langchain_core.messages import AIMessage

try:
    from diskcache import Cache
    _CACHE_AVAILABLE = True
except ImportError:
    _CACHE_AVAILABLE = False


class LLMCache:
    """Disk-backed cache for LLM responses."""

    def __init__(self, cache_dir: str | None = None, enabled: bool = True):
        self.enabled = enabled and _CACHE_AVAILABLE
        self._cache: Any = None
        if self.enabled:
            from pathlib import Path
            if cache_dir is None:
                cache_dir = str(Path.home() / ".cache" / "smf-swarm")
            self._cache = Cache(cache_dir)

    def _make_key(self, messages: list, model: str = "", temperature: float = 0.3, **kwargs) -> str:
        """Deterministic hash key for a prompt + config combination."""
        content = json.dumps({
            "messages": [m.content for m in messages],
            "model": model,
            "temperature": temperature,
            "extra": kwargs,
        }, sort_keys=True)
        return hashlib.sha256(content.encode("utf-8")).hexdigest()[:32]

    def get(self, messages: list, **kwargs) -> Optional[AIMessage]:
        if not self.enabled or self._cache is None:
            return None
        key = self._make_key(messages, **kwargs)
        try:
            data = self._cache.get(key)
            if data:
                return AIMessage(content=data["content"], response_metadata=data.get("metadata", {}))
        except Exception:
            pass
        return None

    def set(self, messages: list, response: AIMessage, **kwargs) -> None:
        if not self.enabled or self._cache is None:
            return
        key = self._make_key(messages, **kwargs)
        try:
            self._cache.set(key, {
                "content": response.content,
                "metadata": response.response_metadata,
            }, expire=86400 * 7)  # 7-day TTL
        except Exception:
            pass

    def close(self):
        if self._cache:
            self._cache.close()

    def disable(self):
        """Temporarily disable cache (e.g., for --no-cache CLI flag)."""
        self.enabled = False
