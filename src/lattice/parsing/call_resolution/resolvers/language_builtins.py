"""Language builtin call resolution strategies."""

from __future__ import annotations

from lattice.parsing.call_resolution.builtins import (
    BUILTIN_PREFIX,
    JS_BUILTIN_PATTERNS,
    JS_BUILTIN_TYPES,
    JS_FUNCTION_PROTOTYPE_SUFFIXES,
    PYTHON_BUILTINS,
    SEPARATOR_DOT,
    SEPARATOR_PROTOTYPE,
)


def resolve_builtin_call(
    call_name: str,
    language: str,
) -> tuple[str, str] | None:
    simple_name = call_name.split("(")[0]

    if language == "python":
        if simple_name in PYTHON_BUILTINS:
            return ("Function", f"builtins.{simple_name}")

    elif language in ("javascript", "typescript", "jsx", "tsx"):
        if call_name in JS_BUILTIN_PATTERNS:
            return ("Function", f"{BUILTIN_PREFIX}.{call_name}")
        if simple_name in JS_BUILTIN_TYPES:
            return ("Class", f"{BUILTIN_PREFIX}.{simple_name}")
        for suffix, method in JS_FUNCTION_PROTOTYPE_SUFFIXES.items():
            if call_name.endswith(suffix):
                return (
                    "Function",
                    f"{BUILTIN_PREFIX}{SEPARATOR_DOT}Function{SEPARATOR_PROTOTYPE}{method}",
                )
        if SEPARATOR_PROTOTYPE in call_name:
            if call_name.endswith(".call") or call_name.endswith(".apply"):
                base_call = call_name.rsplit(SEPARATOR_DOT, 1)[0]
                return ("Function", base_call)

    elif language in ("java",):
        java_types = {"String", "Integer", "Double", "Boolean", "Object", "List", "Map", "Set"}
        if simple_name in java_types:
            return ("Class", f"java.lang.{simple_name}")

    elif language in ("rust",):
        rust_macros = {"println", "format", "vec", "panic", "assert", "debug", "todo"}
        if simple_name in rust_macros:
            return ("Macro", f"std::macros::{simple_name}")

    return None
