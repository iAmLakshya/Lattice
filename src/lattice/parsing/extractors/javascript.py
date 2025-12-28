from lattice.parsing.extractors.base import BaseExtractor
from lattice.parsing.extractors.js_visitors import JSEntityVisitor
from lattice.parsing.models import CodeEntity, ImportInfo


class JavaScriptExtractor(BaseExtractor):
    def __init__(self):
        super().__init__()
        self._visitor = JSEntityVisitor(self)

    def _extract_jsdoc(self, node, source: str) -> str | None:
        return self._visitor._extract_jsdoc(node, source)

    def extract_imports(self, root_node, source: str) -> list[ImportInfo]:
        imports = []

        for node in self._walk_tree(root_node, {"import_statement"}):
            source_node = self._find_child_by_type(node, "string")
            source_value = ""
            if source_node:
                source_value = self._get_node_text(source_node, source).strip("'\"")

            is_external = not source_value.startswith(".")

            import_clause = self._find_child_by_type(node, "import_clause")
            if import_clause:
                for child in import_clause.children:
                    if child.type == "identifier":
                        imports.append(
                            ImportInfo(
                                name=self._get_node_text(child, source),
                                source=source_value,
                                is_external=is_external,
                                line_number=self._get_node_line(node),
                            )
                        )

                named_imports = self._find_child_by_type(import_clause, "named_imports")
                if named_imports:
                    imports.extend(
                        self._extract_named_imports(named_imports, source, source_value, node)
                    )

                namespace_import = self._find_child_by_type(import_clause, "namespace_import")
                if namespace_import:
                    id_node = self._find_child_by_type(namespace_import, "identifier")
                    if id_node:
                        imports.append(
                            ImportInfo(
                                name="*",
                                alias=self._get_node_text(id_node, source),
                                source=source_value,
                                is_external=is_external,
                                line_number=self._get_node_line(node),
                            )
                        )

        imports.extend(self._extract_require_imports(root_node, source))
        return imports

    def _extract_named_imports(
        self, named_imports, source: str, source_value: str, node
    ) -> list[ImportInfo]:
        imports = []
        is_external = not source_value.startswith(".")

        for child in named_imports.children:
            if child.type == "import_specifier":
                name_node = child.children[0] if child.children else None
                alias_node = child.children[-1] if len(child.children) > 1 else None

                if name_node:
                    name = self._get_node_text(name_node, source)
                    alias = None
                    if alias_node and alias_node != name_node:
                        alias = self._get_node_text(alias_node, source)

                    imports.append(
                        ImportInfo(
                            name=name,
                            alias=alias,
                            source=source_value,
                            is_external=is_external,
                            line_number=self._get_node_line(node),
                        )
                    )
        return imports

    def _extract_require_imports(self, root_node, source: str) -> list[ImportInfo]:
        imports = []
        for node in self._walk_tree(root_node, {"call_expression"}):
            func_node = node.children[0] if node.children else None
            if func_node and self._get_node_text(func_node, source) == "require":
                args_node = self._find_child_by_type(node, "arguments")
                if args_node:
                    string_node = self._find_child_by_type(args_node, "string")
                    if string_node:
                        source_value = self._get_node_text(string_node, source).strip("'\"")
                        imports.append(
                            ImportInfo(
                                name=source_value,
                                source=source_value,
                                is_external=not source_value.startswith("."),
                                line_number=self._get_node_line(node),
                            )
                        )
        return imports

    def _extract_lexical_declaration_entities(self, node, source: str) -> list[CodeEntity]:
        entities = []
        for decl in self._find_child_by_type(node, "variable_declarator", find_all=True):
            value_node = None
            for child in decl.children:
                if child.type in ("arrow_function", "function"):
                    value_node = child
                    break

            if value_node:
                name_node = self._find_child_by_type(decl, "identifier")
                if name_node:
                    entity = self._visitor.extract_arrow_function(
                        node,
                        source,
                        self._get_node_text(name_node, source),
                        value_node,
                    )
                    if entity:
                        entities.append(entity)
        return entities

    def extract_entities(self, root_node, source: str) -> list[CodeEntity]:
        entities = []

        for node in root_node.children:
            if node.type == "function_declaration":
                entity = self._visitor.extract_function(node, source)
                if entity:
                    entities.append(entity)

            elif node.type == "class_declaration":
                entity = self._visitor.extract_class(node, source)
                if entity:
                    entities.append(entity)

            elif node.type == "lexical_declaration":
                entities.extend(self._extract_lexical_declaration_entities(node, source))

            elif node.type == "export_statement":
                entities.extend(self._extract_export_entities(node, source))

        return entities

    def _extract_export_entities(self, node, source: str) -> list[CodeEntity]:
        entities = []
        for child in node.children:
            if child.type == "function_declaration":
                entity = self._visitor.extract_function(child, source)
                if entity:
                    entities.append(entity)
            elif child.type == "class_declaration":
                entity = self._visitor.extract_class(child, source)
                if entity:
                    entities.append(entity)
            elif child.type == "lexical_declaration":
                entities.extend(self._extract_lexical_declaration_entities(child, source))
        return entities
