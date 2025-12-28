from lattice.parsing.models import CodeEntity
from lattice.shared.types import EntityType


class JSEntityVisitor:
    def __init__(self, extractor):
        self._extractor = extractor

    def _get_node_text(self, node, source: str) -> str:
        return self._extractor._get_node_text(node, source)

    def _get_node_line(self, node) -> int:
        return self._extractor._get_node_line(node)

    def _get_node_end_line(self, node) -> int:
        return self._extractor._get_node_end_line(node)

    def _find_child_by_type(self, node, type_name: str, find_all: bool = False):
        return self._extractor._find_child_by_type(node, type_name, find_all)

    def _walk_tree(self, node, types: set):
        return self._extractor._walk_tree(node, types)

    def _is_async_node(self, node, source: str) -> bool:
        return self._extractor._is_async_node(node, source)

    def _has_keyword(self, node, source: str, keyword: str) -> bool:
        return any(self._get_node_text(child, source) == keyword for child in node.children)

    def _extract_jsdoc(self, node, source: str) -> str | None:
        start_line = self._get_node_line(node)
        lines = source.split("\n")

        if start_line > 1:
            prev_line = lines[start_line - 2].strip()
            if prev_line.endswith("*/"):
                doc_lines = []
                for i in range(start_line - 2, -1, -1):
                    line = lines[i].strip()
                    doc_lines.insert(0, line)
                    if line.startswith("/**"):
                        break

                if doc_lines:
                    doc = "\n".join(doc_lines)
                    doc = doc.replace("/**", "").replace("*/", "")
                    doc = "\n".join(
                        line.lstrip("* ").rstrip() for line in doc.split("\n") if line.strip()
                    )
                    return doc.strip() if doc.strip() else None

        return None

    def _extract_calls(self, node, source: str) -> list[str]:
        calls = set()

        for call_node in self._walk_tree(node, {"call_expression"}):
            func_node = call_node.children[0] if call_node.children else None
            if func_node and func_node.type in ("identifier", "member_expression"):
                calls.add(self._get_node_text(func_node, source))

        return list(calls)

    def extract_function(self, node, source: str) -> CodeEntity | None:
        name_node = self._find_child_by_type(node, "identifier")
        if not name_node:
            return None
        name = self._get_node_text(name_node, source)

        params_node = self._find_child_by_type(node, "formal_parameters")
        params = self._get_node_text(params_node, source) if params_node else "()"

        is_async = self._is_async_node(node, source)
        docstring = self._extract_jsdoc(node, source)
        calls = self._extract_calls(node, source)

        return CodeEntity(
            type=EntityType.FUNCTION,
            name=name,
            qualified_name=name,
            signature=f"function {name}{params}",
            docstring=docstring,
            code=self._get_node_text(node, source),
            start_line=self._get_node_line(node),
            end_line=self._get_node_end_line(node),
            is_async=is_async,
            calls=calls,
        )

    def extract_arrow_function(self, node, source: str, name: str, arrow_node) -> CodeEntity:
        params_node = self._find_child_by_type(arrow_node, "formal_parameters")
        if params_node:
            params = self._get_node_text(params_node, source)
        else:
            param_node = arrow_node.children[0] if arrow_node.children else None
            if param_node and param_node.type == "identifier":
                params = f"({self._get_node_text(param_node, source)})"
            else:
                params = "()"

        is_async = self._is_async_node(arrow_node, source)
        docstring = self._extract_jsdoc(node, source)
        calls = self._extract_calls(arrow_node, source)

        return CodeEntity(
            type=EntityType.FUNCTION,
            name=name,
            qualified_name=name,
            signature=f"const {name} = {params} =>",
            docstring=docstring,
            code=self._get_node_text(node, source),
            start_line=self._get_node_line(node),
            end_line=self._get_node_end_line(node),
            is_async=is_async,
            calls=calls,
        )

    def extract_class(self, node, source: str) -> CodeEntity | None:
        name_node = self._find_child_by_type(node, "identifier")
        if not name_node:
            return None
        name = self._get_node_text(name_node, source)

        base_classes = []
        heritage = self._find_child_by_type(node, "class_heritage")
        if heritage:
            for child in heritage.children:
                if child.type == "identifier":
                    base_classes.append(self._get_node_text(child, source))

        body_node = self._find_child_by_type(node, "class_body")
        docstring = self._extract_jsdoc(node, source)

        methods = []
        if body_node:
            for child in body_node.children:
                if child.type == "method_definition":
                    method = self.extract_method(child, source, name)
                    if method:
                        methods.append(method)

        return CodeEntity(
            type=EntityType.CLASS,
            name=name,
            qualified_name=name,
            signature=f"class {name}",
            docstring=docstring,
            code=self._get_node_text(node, source),
            start_line=self._get_node_line(node),
            end_line=self._get_node_end_line(node),
            base_classes=base_classes,
            children=methods,
        )

    def extract_method(self, node, source: str, class_name: str) -> CodeEntity | None:
        name_node = self._find_child_by_type(node, "property_identifier")
        if not name_node:
            return None
        name = self._get_node_text(name_node, source)

        params_node = self._find_child_by_type(node, "formal_parameters")
        params = self._get_node_text(params_node, source) if params_node else "()"

        is_async = self._is_async_node(node, source)
        is_static = self._has_keyword(node, source, "static")
        docstring = self._extract_jsdoc(node, source)
        calls = self._extract_calls(node, source)

        return CodeEntity(
            type=EntityType.METHOD,
            name=name,
            qualified_name=f"{class_name}.{name}",
            signature=f"{name}{params}",
            docstring=docstring,
            code=self._get_node_text(node, source),
            start_line=self._get_node_line(node),
            end_line=self._get_node_end_line(node),
            is_async=is_async,
            is_static=is_static,
            parent_class=class_name,
            calls=calls,
        )
