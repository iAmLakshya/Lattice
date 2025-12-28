"""Entity and relationship buffers for batched graph operations."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass
class EntityBuffer:
    """Buffers for batched entity creation."""

    classes: list[dict[str, Any]] = field(default_factory=list)
    functions: list[dict[str, Any]] = field(default_factory=list)
    methods: list[dict[str, Any]] = field(default_factory=list)
    imports: list[dict[str, Any]] = field(default_factory=list)
    files: list[dict[str, Any]] = field(default_factory=list)

    def total_count(self) -> int:
        return (
            len(self.classes)
            + len(self.functions)
            + len(self.methods)
            + len(self.imports)
            + len(self.files)
        )

    def clear_all(self) -> None:
        self.classes.clear()
        self.functions.clear()
        self.methods.clear()
        self.imports.clear()
        self.files.clear()


@dataclass
class RelationshipBuffer:
    """Buffers for batched relationship creation."""

    defines_class: list[dict[str, Any]] = field(default_factory=list)
    defines_function: list[dict[str, Any]] = field(default_factory=list)
    defines_method: list[dict[str, Any]] = field(default_factory=list)
    extends: list[dict[str, Any]] = field(default_factory=list)
    imports: list[dict[str, Any]] = field(default_factory=list)
    calls: list[dict[str, Any]] = field(default_factory=list)

    def total_count(self) -> int:
        return (
            len(self.defines_class)
            + len(self.defines_function)
            + len(self.defines_method)
            + len(self.extends)
            + len(self.imports)
            + len(self.calls)
        )

    def clear_all(self) -> None:
        self.defines_class.clear()
        self.defines_function.clear()
        self.defines_method.clear()
        self.extends.clear()
        self.imports.clear()
        self.calls.clear()
