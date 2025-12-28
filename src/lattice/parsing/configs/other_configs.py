from __future__ import annotations

from lattice.parsing.language_config import LanguageConfig

RUST_CONFIG = LanguageConfig(
    name="rust",
    display_name="Rust",
    file_extensions=[".rs"],
    function_node_types=["function_item"],
    class_node_types=["struct_item", "enum_item", "trait_item", "impl_item"],
    method_node_types=["function_item"],
    call_node_types=["call_expression", "macro_invocation"],
    import_node_types=["use_declaration"],
    module_node_types=["source_file"],
    comment_node_types=["line_comment", "block_comment"],
    string_node_types=["string_literal", "raw_string_literal"],
    package_indicators=["Cargo.toml"],
)

JAVA_CONFIG = LanguageConfig(
    name="java",
    display_name="Java",
    file_extensions=[".java"],
    function_node_types=["method_declaration", "constructor_declaration"],
    class_node_types=["class_declaration", "interface_declaration", "enum_declaration"],
    method_node_types=["method_declaration"],
    call_node_types=["method_invocation"],
    import_node_types=["import_declaration"],
    module_node_types=["program"],
    comment_node_types=["line_comment", "block_comment"],
    string_node_types=["string_literal"],
    package_indicators=["pom.xml", "build.gradle", "build.gradle.kts"],
)

GO_CONFIG = LanguageConfig(
    name="go",
    display_name="Go",
    file_extensions=[".go"],
    function_node_types=["function_declaration", "method_declaration"],
    class_node_types=["type_declaration"],
    method_node_types=["method_declaration"],
    call_node_types=["call_expression"],
    import_node_types=["import_declaration", "import_spec"],
    module_node_types=["source_file"],
    comment_node_types=["comment"],
    string_node_types=["raw_string_literal", "interpreted_string_literal"],
    package_indicators=["go.mod"],
)

CPP_CONFIG = LanguageConfig(
    name="cpp",
    display_name="C++",
    file_extensions=[".cpp", ".cc", ".cxx", ".hpp", ".h", ".hxx"],
    function_node_types=["function_definition"],
    class_node_types=["class_specifier", "struct_specifier"],
    method_node_types=["function_definition"],
    call_node_types=["call_expression"],
    import_node_types=["preproc_include"],
    module_node_types=["translation_unit"],
    comment_node_types=["comment"],
    string_node_types=["string_literal", "raw_string_literal"],
    package_indicators=["CMakeLists.txt", "Makefile"],
)
