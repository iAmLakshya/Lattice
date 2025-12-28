"""Call resolution strategies - re-exports from submodules."""

from lattice.parsing.call_resolution.resolvers.chained import (
    resolve_chained_call,
    resolve_cpp_operator_call,
    resolve_iife,
)
from lattice.parsing.call_resolution.resolvers.imports import (
    resolve_via_imports,
)
from lattice.parsing.call_resolution.resolvers.inheritance import (
    resolve_inherited_method,
    resolve_super_call,
)
from lattice.parsing.call_resolution.resolvers.language_builtins import (
    resolve_builtin_call,
)
from lattice.parsing.call_resolution.resolvers.simple import (
    calculate_distance,
    resolve_by_simple_name,
    resolve_class_name,
    resolve_same_module_call,
)

__all__ = [
    "calculate_distance",
    "resolve_builtin_call",
    "resolve_by_simple_name",
    "resolve_chained_call",
    "resolve_class_name",
    "resolve_cpp_operator_call",
    "resolve_iife",
    "resolve_inherited_method",
    "resolve_same_module_call",
    "resolve_super_call",
    "resolve_via_imports",
]
