"""Builtin functions, types, and constants for call resolution."""

PYTHON_BUILTINS = frozenset(
    {
        "print",
        "len",
        "range",
        "int",
        "str",
        "float",
        "bool",
        "list",
        "dict",
        "set",
        "tuple",
        "open",
        "type",
        "isinstance",
        "hasattr",
        "getattr",
        "setattr",
        "delattr",
        "enumerate",
        "zip",
        "map",
        "filter",
        "sorted",
        "reversed",
        "any",
        "all",
        "sum",
        "min",
        "max",
        "abs",
        "round",
        "input",
        "super",
        "classmethod",
        "staticmethod",
        "property",
        "callable",
        "iter",
        "next",
        "repr",
        "hash",
        "id",
        "dir",
        "vars",
        "globals",
        "locals",
        "compile",
        "eval",
        "exec",
        "format",
        "Exception",
        "ValueError",
        "TypeError",
        "KeyError",
        "IndexError",
        "AttributeError",
        "RuntimeError",
        "StopIteration",
        "NotImplementedError",
        "AssertionError",
        "ImportError",
        "OSError",
        "IOError",
        "FileNotFoundError",
    }
)

JS_BUILTIN_TYPES = frozenset(
    {
        "Array",
        "Object",
        "String",
        "Number",
        "Date",
        "RegExp",
        "Function",
        "Map",
        "Set",
        "WeakMap",
        "WeakSet",
        "Promise",
        "Error",
        "Boolean",
        "Symbol",
        "BigInt",
        "ArrayBuffer",
        "DataView",
        "Int8Array",
        "Uint8Array",
        "Float32Array",
        "Float64Array",
        "Proxy",
        "Reflect",
        "Intl",
    }
)

JS_BUILTIN_PATTERNS = frozenset(
    {
        "Object.create",
        "Object.keys",
        "Object.values",
        "Object.entries",
        "Object.assign",
        "Object.freeze",
        "Object.seal",
        "Object.defineProperty",
        "Object.getOwnPropertyNames",
        "Object.getPrototypeOf",
        "Array.from",
        "Array.isArray",
        "Array.of",
        "parseInt",
        "parseFloat",
        "isNaN",
        "isFinite",
        "encodeURI",
        "decodeURI",
        "encodeURIComponent",
        "decodeURIComponent",
        "console.log",
        "console.error",
        "console.warn",
        "console.info",
        "console.debug",
        "console.trace",
        "JSON.parse",
        "JSON.stringify",
        "Math.random",
        "Math.floor",
        "Math.ceil",
        "Math.round",
        "Math.abs",
        "Math.max",
        "Math.min",
        "Math.pow",
        "Math.sqrt",
        "Date.now",
        "Date.parse",
        "Promise.resolve",
        "Promise.reject",
        "Promise.all",
        "Promise.race",
        "Promise.allSettled",
        "Reflect.get",
        "Reflect.set",
        "Reflect.has",
        "Reflect.apply",
        "setTimeout",
        "setInterval",
        "clearTimeout",
        "clearInterval",
        "fetch",
        "require",
    }
)

JS_FUNCTION_PROTOTYPE_SUFFIXES: dict[str, str] = {
    ".call": "call",
    ".apply": "apply",
    ".bind": "bind",
}

IIFE_FUNC_PREFIX = "iife_func_"
IIFE_ARROW_PREFIX = "iife_arrow_"

SEPARATOR_DOT = "."
SEPARATOR_DOUBLE_COLON = "::"
SEPARATOR_COLON = ":"
SEPARATOR_PROTOTYPE = ".prototype."

BUILTIN_PREFIX = "builtin"

KEYWORD_SUPER = "super"
KEYWORD_SELF = "self"
KEYWORD_THIS = "this"
KEYWORD_CONSTRUCTOR = "constructor"
KEYWORD_INIT = "__init__"

CPP_OPERATORS: dict[str, str] = {
    "operator+": "builtin.operator_add",
    "operator-": "builtin.operator_sub",
    "operator*": "builtin.operator_mul",
    "operator/": "builtin.operator_div",
    "operator==": "builtin.operator_eq",
    "operator!=": "builtin.operator_ne",
    "operator<": "builtin.operator_lt",
    "operator>": "builtin.operator_gt",
    "operator<=": "builtin.operator_le",
    "operator>=": "builtin.operator_ge",
    "operator[]": "builtin.operator_index",
    "operator()": "builtin.operator_call",
    "operator<<": "builtin.operator_lshift",
    "operator>>": "builtin.operator_rshift",
}

OPERATOR_PREFIX = "operator"

RUST_CRATE = "crate"
RUST_SELF = "self"
RUST_SUPER = "super"

JAVA_THIS = "this"
JAVA_SUPER = "super"
