from __future__ import annotations

import logging
import sys
from collections import OrderedDict
from pathlib import Path
from typing import Any, Generic, TypeVar

logger = logging.getLogger(__name__)

K = TypeVar("K")
V = TypeVar("V")


class BoundedCache(Generic[K, V]):
    """Memory-aware LRU cache with automatic eviction."""

    def __init__(self, max_entries: int = 1000, max_memory_mb: int = 500):
        self._cache: OrderedDict[K, V] = OrderedDict()
        self.max_entries = max_entries
        self.max_memory_bytes = max_memory_mb * 1024 * 1024
        self._hits = 0
        self._misses = 0

    def __setitem__(self, key: K, value: V) -> None:
        if key in self._cache:
            del self._cache[key]
        self._cache[key] = value
        self._enforce_limits()

    def __getitem__(self, key: K) -> V:
        if key not in self._cache:
            self._misses += 1
            raise KeyError(key)
        self._hits += 1
        self._cache.move_to_end(key)
        return self._cache[key]

    def __delitem__(self, key: K) -> None:
        if key in self._cache:
            del self._cache[key]

    def __contains__(self, key: K) -> bool:
        return key in self._cache

    def __len__(self) -> int:
        return len(self._cache)

    def get(self, key: K, default: V | None = None) -> V | None:
        try:
            return self[key]
        except KeyError:
            return default

    def items(self):
        return self._cache.items()

    def keys(self):
        return self._cache.keys()

    def values(self):
        return self._cache.values()

    def clear(self) -> None:
        self._cache.clear()
        self._hits = 0
        self._misses = 0

    def _enforce_limits(self) -> None:
        while len(self._cache) > self.max_entries:
            evicted_key, _ = self._cache.popitem(last=False)
            logger.debug(f"Evicted {evicted_key} due to entry limit")

        if self._should_evict_for_memory():
            entries_to_remove = max(1, len(self._cache) // 10)
            for _ in range(entries_to_remove):
                if self._cache:
                    evicted_key, _ = self._cache.popitem(last=False)
                    logger.debug(f"Evicted {evicted_key} due to memory pressure")

    def _should_evict_for_memory(self) -> bool:
        try:
            cache_size = sum(sys.getsizeof(v) for v in self._cache.values())
            return cache_size > self.max_memory_bytes
        except Exception:
            return len(self._cache) > int(self.max_entries * 0.8)

    @property
    def hit_rate(self) -> float:
        total = self._hits + self._misses
        return self._hits / total if total > 0 else 0.0

    @property
    def stats(self) -> dict[str, Any]:
        return {
            "entries": len(self._cache),
            "max_entries": self.max_entries,
            "hits": self._hits,
            "misses": self._misses,
            "hit_rate": self.hit_rate,
        }


class ASTCache(BoundedCache[Path, tuple[Any, str]]):
    """Cache for parsed AST nodes, stores (root_node, language) tuples."""

    def remove_file(self, file_path: Path) -> bool:
        if file_path in self._cache:
            del self._cache[file_path]
            return True
        return False

    def get_cached_files(self) -> list[Path]:
        return list(self._cache.keys())


class FunctionRegistry:
    """Registry for tracking function/class definitions with trie-based lookups.

    Provides O(1) lookups by qualified name, O(1) lookups by simple name suffix,
    and O(k) prefix-based lookups where k is the number of results.

    The registry maintains three data structures:
    - _entries: Direct QN -> entity_type mapping for O(1) exact lookups
    - _simple_name_index: Simple name -> set of QNs for O(1) suffix lookups
    - _trie: Hierarchical trie for O(k) prefix queries
    """

    def __init__(self, simple_name_lookup: dict[str, set[str]] | None = None):
        self._entries: dict[str, str] = {}
        # Use provided lookup or create new one (allows sharing between components)
        self._simple_name_index: dict[str, set[str]] = simple_name_lookup or {}
        self._trie: dict[str, Any] = {}

    def register(self, qualified_name: str, entity_type: str) -> None:
        self._entries[qualified_name] = entity_type

        simple_name = qualified_name.split(".")[-1]
        if simple_name not in self._simple_name_index:
            self._simple_name_index[simple_name] = set()
        self._simple_name_index[simple_name].add(qualified_name)

        parts = qualified_name.split(".")
        current = self._trie
        for part in parts:
            if part not in current:
                current[part] = {}
            current = current[part]
        current["__type__"] = entity_type
        current["__qn__"] = qualified_name

    def unregister(self, qualified_name: str) -> bool:
        if qualified_name not in self._entries:
            return False

        del self._entries[qualified_name]

        simple_name = qualified_name.split(".")[-1]
        if simple_name in self._simple_name_index:
            self._simple_name_index[simple_name].discard(qualified_name)
            if not self._simple_name_index[simple_name]:
                del self._simple_name_index[simple_name]

        self._cleanup_trie_path(qualified_name.split("."))
        return True

    def _cleanup_trie_path(self, parts: list[str]) -> None:
        if not parts:
            return

        current = self._trie
        path = []

        for part in parts[:-1]:
            if part not in current:
                return
            path.append((current, part))
            current = current[part]

        last_part = parts[-1]
        if last_part in current:
            current[last_part].pop("__type__", None)
            current[last_part].pop("__qn__", None)
            if not current[last_part]:
                del current[last_part]

    def get(self, qualified_name: str) -> str | None:
        return self._entries.get(qualified_name)

    def __contains__(self, qualified_name: str) -> bool:
        return qualified_name in self._entries

    def __len__(self) -> int:
        return len(self._entries)

    def find_by_simple_name(self, simple_name: str) -> list[str]:
        """Find all qualified names ending with the given simple name. O(1) lookup."""
        return list(self._simple_name_index.get(simple_name, []))

    def find_ending_with(self, suffix: str) -> list[str]:
        """Find all qualified names ending with .suffix. O(1) lookup via index.

        This uses the simple_name_index for O(1) lookup when the suffix
        matches a simple name. Falls back to linear scan for dotted suffixes.

        Args:
            suffix: The suffix to match (without leading dot)

        Returns:
            List of qualified names ending with the suffix
        """
        # O(1) lookup via the simple name index
        if suffix in self._simple_name_index:
            return list(self._simple_name_index[suffix])

        # Fallback to linear scan for dotted suffixes
        suffix_with_dot = f".{suffix}"
        return [qn for qn in self._entries if qn.endswith(suffix_with_dot)]

    def find_with_prefix(self, prefix: str) -> list[tuple[str, str]]:
        """Find all entries with qualified names starting with prefix. O(k) where k=results."""
        results = []
        prefix_parts = prefix.split(".")

        current = self._trie
        for part in prefix_parts:
            if part not in current:
                return []
            current = current[part]

        def collect_entries(node: dict[str, Any]) -> None:
            if "__qn__" in node:
                results.append((node["__qn__"], node["__type__"]))
            for key, child in node.items():
                if not key.startswith("__") and isinstance(child, dict):
                    collect_entries(child)

        collect_entries(current)
        return results

    def find_with_prefix_and_suffix(
        self, prefix: str, suffix: str
    ) -> list[str]:
        """Find qualified names matching both prefix and suffix pattern.

        Efficiently combines prefix navigation with suffix filtering.

        Args:
            prefix: The prefix to match (e.g., "myapp.models")
            suffix: The suffix to match (e.g., "save")

        Returns:
            List of qualified names matching both patterns
        """
        prefix_matches = self.find_with_prefix(prefix)
        suffix_pattern = f".{suffix}"
        return [qn for qn, _ in prefix_matches if qn.endswith(suffix_pattern)]

    def remove_by_prefix(self, prefix: str) -> int:
        """Remove all entries with qualified names starting with prefix."""
        entries_to_remove = [qn for qn, _ in self.find_with_prefix(prefix)]
        for qn in entries_to_remove:
            self.unregister(qn)
        return len(entries_to_remove)

    def all_entries(self) -> dict[str, str]:
        """Return a copy of all entries."""
        return dict(self._entries)

    def keys(self):
        """Return view of all qualified names."""
        return self._entries.keys()

    def items(self):
        """Return view of all (qualified_name, entity_type) pairs."""
        return self._entries.items()

    def __iter__(self):
        """Iterate over qualified names."""
        return iter(self._entries)

    def __getitem__(self, qualified_name: str) -> str:
        """Get entity type by qualified name. Raises KeyError if not found."""
        return self._entries[qualified_name]

    def __setitem__(self, qualified_name: str, entity_type: str) -> None:
        """Register an entry using dict-like syntax."""
        self.register(qualified_name, entity_type)

    def __delitem__(self, qualified_name: str) -> None:
        """Unregister an entry using dict-like syntax."""
        self.unregister(qualified_name)
