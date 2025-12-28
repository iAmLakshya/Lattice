from __future__ import annotations

import logging
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from tree_sitter import Node

logger = logging.getLogger(__name__)


def safe_decode_text(node: Node) -> str | None:
    if node.text:
        return node.text.decode("utf-8")
    return None


class JsTsTypeInference:
    def __init__(
        self,
        type_resolver: "TypeResolver | None" = None,
    ):
        from lattice.parsing.type_inference.type_resolver import TypeResolver

        self._type_resolver = type_resolver or TypeResolver()

    def infer_types(
        self,
        caller_node: Node,
        local_var_types: dict[str, str],
        module_qn: str,
        language: str,
    ) -> None:
        self._infer_parameter_types(caller_node, local_var_types, module_qn, language)

        declarations = []
        assignments = []
        stack = [caller_node]

        while stack:
            node = stack.pop()
            node_type = node.type
            if node_type in (
                "variable_declarator",
                "lexical_declaration",
                "variable_declaration",
            ):
                declarations.append(node)
            if node_type == "assignment_expression":
                assignments.append(node)
            stack.extend(reversed(node.children))

        for decl in declarations:
            self._process_declaration(decl, local_var_types, module_qn, language)
        for assign in assignments:
            self._process_assignment(assign, local_var_types, module_qn)

    def _infer_parameter_types(
        self,
        caller_node: Node,
        local_var_types: dict[str, str],
        module_qn: str,
        language: str,
    ) -> None:
        for child in caller_node.children:
            if child.type == "formal_parameters":
                for param in child.children:
                    self._process_param(param, local_var_types, module_qn, language)

    def _process_param(
        self,
        param: Node,
        local_var_types: dict[str, str],
        module_qn: str,
        language: str,
    ) -> None:
        if param.type == "identifier":
            param_name = safe_decode_text(param)
            if param_name:
                inferred_type = self._type_resolver.infer_type_from_parameter_name(
                    param_name, module_qn
                )
                if inferred_type:
                    local_var_types[param_name] = inferred_type

        elif param.type in ("required_parameter", "optional_parameter"):
            name_node = param.child_by_field_name("pattern")
            type_node = param.child_by_field_name("type")
            if name_node and type_node:
                param_name = safe_decode_text(name_node)
                param_type = safe_decode_text(type_node)
                if param_name and param_type:
                    local_var_types[param_name] = self._clean_ts_type(param_type)

        elif param.type == "assignment_pattern":
            left = param.child_by_field_name("left")
            right = param.child_by_field_name("right")
            if left:
                param_name = safe_decode_text(left)
                if param_name and right:
                    inferred_type = self._infer_expression_type(right, module_qn)
                    if inferred_type:
                        local_var_types[param_name] = inferred_type

    def _process_declaration(
        self,
        decl: Node,
        local_var_types: dict[str, str],
        module_qn: str,
        language: str,
    ) -> None:
        if decl.type == "variable_declarator":
            name_node = decl.child_by_field_name("name")
            value_node = decl.child_by_field_name("value")
            type_node = decl.child_by_field_name("type")

            if name_node:
                var_name = safe_decode_text(name_node)
                if not var_name:
                    return
                if type_node:
                    type_str = safe_decode_text(type_node)
                    if type_str:
                        local_var_types[var_name] = self._clean_ts_type(type_str)
                        return
                if value_node:
                    inferred_type = self._infer_expression_type(value_node, module_qn)
                    if inferred_type:
                        local_var_types[var_name] = inferred_type

        elif decl.type in ("lexical_declaration", "variable_declaration"):
            for child in decl.children:
                if child.type == "variable_declarator":
                    self._process_declaration(
                        child, local_var_types, module_qn, language
                    )

    def _process_assignment(
        self,
        assign: Node,
        local_var_types: dict[str, str],
        module_qn: str,
    ) -> None:
        left = assign.child_by_field_name("left")
        right = assign.child_by_field_name("right")
        if left and right and left.type == "identifier":
            var_name = safe_decode_text(left)
            if var_name and var_name not in local_var_types:
                inferred_type = self._infer_expression_type(right, module_qn)
                if inferred_type:
                    local_var_types[var_name] = inferred_type

    def _infer_expression_type(self, node: Node, module_qn: str) -> str | None:
        node_type = node.type

        if node_type == "new_expression":
            constructor = node.child_by_field_name("constructor")
            if constructor:
                return safe_decode_text(constructor)

        if node_type == "call_expression":
            func_node = node.child_by_field_name("function")
            if func_node and func_node.type == "identifier":
                func_name = safe_decode_text(func_node)
                if func_name and func_name[0].isupper():
                    return func_name

        if node_type == "array":
            return "Array"
        if node_type == "object":
            return "Object"
        if node_type in ("string", "template_string"):
            return "String"
        if node_type == "number":
            return "Number"
        if node_type in ("true", "false"):
            return "Boolean"

        return None

    def _clean_ts_type(self, type_str: str) -> str:
        type_str = type_str.strip()
        if "<" in type_str:
            type_str = type_str.split("<")[0]
        if type_str.endswith("[]"):
            type_str = type_str[:-2]
        if "|" in type_str:
            type_str = type_str.split("|")[0].strip()
        if "&" in type_str:
            type_str = type_str.split("&")[0].strip()
        return type_str
