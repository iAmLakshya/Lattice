from __future__ import annotations

from lattice.parsing.language_config import LanguageConfig

JAVASCRIPT_CONFIG = LanguageConfig(
    name="javascript",
    display_name="JavaScript",
    file_extensions=[".js", ".mjs", ".cjs"],
    function_node_types=[
        "function_declaration",
        "function_expression",
        "arrow_function",
        "generator_function_declaration",
    ],
    class_node_types=["class_declaration", "class"],
    method_node_types=["method_definition", "function_expression", "arrow_function"],
    call_node_types=["call_expression"],
    import_node_types=["import_statement", "import_specifier"],
    module_node_types=["program"],
    comment_node_types=["comment"],
    string_node_types=["string", "template_string"],
    function_query="""
        (function_declaration name: (identifier) @function)
        (variable_declarator name: (identifier) @function value: (arrow_function))
    """,
    class_query="(class_declaration name: (identifier) @class)",
    package_indicators=["package.json"],
)

JSX_CONFIG = LanguageConfig(
    name="jsx",
    display_name="JavaScript JSX",
    file_extensions=[".jsx"],
    function_node_types=JAVASCRIPT_CONFIG.function_node_types,
    class_node_types=JAVASCRIPT_CONFIG.class_node_types,
    method_node_types=JAVASCRIPT_CONFIG.method_node_types,
    call_node_types=JAVASCRIPT_CONFIG.call_node_types + ["jsx_element", "jsx_self_closing_element"],
    import_node_types=JAVASCRIPT_CONFIG.import_node_types,
    module_node_types=JAVASCRIPT_CONFIG.module_node_types,
    comment_node_types=JAVASCRIPT_CONFIG.comment_node_types,
    string_node_types=JAVASCRIPT_CONFIG.string_node_types,
    function_query=JAVASCRIPT_CONFIG.function_query,
    class_query=JAVASCRIPT_CONFIG.class_query,
    package_indicators=["package.json"],
)

TYPESCRIPT_CONFIG = LanguageConfig(
    name="typescript",
    display_name="TypeScript",
    file_extensions=[".ts", ".mts", ".cts"],
    function_node_types=[
        "function_declaration",
        "function_expression",
        "arrow_function",
        "generator_function_declaration",
    ],
    class_node_types=["class_declaration", "class", "abstract_class_declaration"],
    method_node_types=["method_definition", "method_signature"],
    call_node_types=["call_expression"],
    import_node_types=["import_statement", "import_specifier", "type_import"],
    module_node_types=["program"],
    comment_node_types=["comment"],
    string_node_types=["string", "template_string"],
    function_query="""
        (function_declaration name: (identifier) @function)
        (variable_declarator name: (identifier) @function value: (arrow_function))
    """,
    class_query="""
        (class_declaration name: (type_identifier) @class)
        (abstract_class_declaration name: (type_identifier) @class)
    """,
    package_indicators=["package.json", "tsconfig.json"],
)

TSX_CONFIG = LanguageConfig(
    name="tsx",
    display_name="TypeScript JSX",
    file_extensions=[".tsx"],
    function_node_types=TYPESCRIPT_CONFIG.function_node_types,
    class_node_types=TYPESCRIPT_CONFIG.class_node_types,
    method_node_types=TYPESCRIPT_CONFIG.method_node_types,
    call_node_types=TYPESCRIPT_CONFIG.call_node_types + ["jsx_element", "jsx_self_closing_element"],
    import_node_types=TYPESCRIPT_CONFIG.import_node_types,
    module_node_types=TYPESCRIPT_CONFIG.module_node_types,
    comment_node_types=TYPESCRIPT_CONFIG.comment_node_types,
    string_node_types=TYPESCRIPT_CONFIG.string_node_types,
    function_query=TYPESCRIPT_CONFIG.function_query,
    class_query=TYPESCRIPT_CONFIG.class_query,
    package_indicators=["package.json", "tsconfig.json"],
)
