from __future__ import annotations

from lattice.parsing.language_config import LanguageConfig

PYTHON_CONFIG = LanguageConfig(
    name="python",
    display_name="Python",
    file_extensions=[".py"],
    function_node_types=["function_definition"],
    class_node_types=["class_definition"],
    method_node_types=["function_definition"],
    call_node_types=["call"],
    import_node_types=["import_statement", "import_from_statement"],
    module_node_types=["module"],
    comment_node_types=["comment"],
    string_node_types=["string", "concatenated_string"],
    function_query="(function_definition name: (identifier) @function)",
    class_query="(class_definition name: (identifier) @class)",
    import_query="""
        (import_statement name: (dotted_name) @import)
        (import_from_statement module_name: (dotted_name) @module)
    """,
    package_indicators=["__init__.py", "pyproject.toml", "setup.py"],
)
