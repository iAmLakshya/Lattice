from __future__ import annotations

from typing import TYPE_CHECKING

from lattice.parsing.type_inference.type_resolver import TypeResolver, safe_decode_text

if TYPE_CHECKING:
    from tree_sitter import Node


class PythonTraversal:
    def __init__(self, type_resolver: TypeResolver):
        self._type_resolver = type_resolver

    def infer_parameter_types(
        self, caller_node: Node, local_var_types: dict[str, str], module_qn: str
    ) -> None:
        params_node = caller_node.child_by_field_name("parameters")
        if not params_node:
            return

        for param in params_node.children:
            if param.type == "identifier":
                param_name = safe_decode_text(param)
                if param_name and param_name not in ("self", "cls"):
                    inferred = self._type_resolver.infer_type_from_parameter_name(
                        param_name, module_qn
                    )
                    if inferred:
                        local_var_types[param_name] = inferred
            elif param.type == "typed_parameter":
                name_node = param.child_by_field_name("name")
                type_node = param.child_by_field_name("type")
                if name_node and type_node:
                    param_name = safe_decode_text(name_node)
                    param_type = safe_decode_text(type_node)
                    if param_name and param_type:
                        local_var_types[param_name] = param_type

    def traverse_single_pass(
        self, node: Node, local_var_types: dict[str, str], module_qn: str
    ) -> None:
        assignments, comprehensions, for_statements = [], [], []

        stack: list[Node] = [node]
        while stack:
            current = stack.pop()
            node_type = current.type
            if node_type == "assignment":
                assignments.append(current)
            elif node_type == "list_comprehension":
                comprehensions.append(current)
            elif node_type == "for_statement":
                for_statements.append(current)
            stack.extend(reversed(current.children))

        for assign in assignments:
            self._process_assignment_simple(assign, local_var_types, module_qn)
        for assign in assignments:
            self._process_assignment_complex(assign, local_var_types, module_qn)
        for comp in comprehensions:
            self._analyze_comprehension(comp, local_var_types, module_qn)
        for for_stmt in for_statements:
            self._analyze_for_loop(for_stmt, local_var_types, module_qn)
        self._infer_instance_attrs(assignments, local_var_types, module_qn)

    def _process_assignment_simple(
        self, node: Node, local_var_types: dict[str, str], module_qn: str
    ) -> None:
        left, right = node.child_by_field_name("left"), node.child_by_field_name("right")
        if not left or not right:
            return
        var_name = safe_decode_text(left) if left.type == "identifier" else None
        if not var_name:
            return
        inferred = self._infer_simple_type(right, module_qn)
        if inferred:
            local_var_types[var_name] = inferred

    def _process_assignment_complex(
        self, node: Node, local_var_types: dict[str, str], module_qn: str
    ) -> None:
        left, right = node.child_by_field_name("left"), node.child_by_field_name("right")
        if not left or not right:
            return
        var_name = safe_decode_text(left) if left.type == "identifier" else None
        if not var_name or var_name in local_var_types:
            return
        if right.type == "call":
            func_node = right.child_by_field_name("function")
            if func_node and func_node.type == "attribute":
                method_text = safe_decode_text(func_node)
                if method_text:
                    inferred = self._type_resolver.infer_method_call_return_type(
                        method_text, module_qn, local_var_types
                    )
                    if inferred:
                        local_var_types[var_name] = inferred

    def _infer_simple_type(self, node: Node, module_qn: str) -> str | None:
        if node.type == "call":
            func_node = node.child_by_field_name("function")
            if func_node and func_node.type == "identifier":
                class_name = safe_decode_text(func_node)
                if class_name and class_name[0].isupper():
                    return class_name
        elif node.type == "list_comprehension":
            body = node.child_by_field_name("body")
            if body:
                return self._infer_simple_type(body, module_qn)
        return None

    def _analyze_comprehension(
        self, comp_node: Node, local_var_types: dict[str, str], module_qn: str
    ) -> None:
        for child in comp_node.children:
            if child.type == "for_in_clause":
                left = child.child_by_field_name("left")
                right = child.child_by_field_name("right")
                if left and right:
                    self._infer_loop_var(left, right, local_var_types, module_qn)

    def _analyze_for_loop(
        self, for_node: Node, local_var_types: dict[str, str], module_qn: str
    ) -> None:
        left = for_node.child_by_field_name("left")
        right = for_node.child_by_field_name("right")
        if left and right:
            self._infer_loop_var(left, right, local_var_types, module_qn)

    def _infer_loop_var(
        self,
        left: Node,
        right: Node,
        local_var_types: dict[str, str],
        module_qn: str,
    ) -> None:
        loop_var = safe_decode_text(left) if left.type == "identifier" else None
        if not loop_var:
            return
        elem_type = self._infer_iterable_element_type(right, local_var_types, module_qn)
        if elem_type:
            local_var_types[loop_var] = elem_type

    def _infer_iterable_element_type(
        self, node: Node, local_var_types: dict[str, str], module_qn: str
    ) -> str | None:
        if node.type == "list":
            for child in node.children:
                if child.type == "call":
                    func_node = child.child_by_field_name("function")
                    if func_node and func_node.type == "identifier":
                        class_name = safe_decode_text(func_node)
                        if class_name and class_name[0].isupper():
                            return class_name
        elif node.type == "identifier":
            var_name = safe_decode_text(node)
            if var_name and var_name in local_var_types:
                var_type = local_var_types[var_name]
                if var_type and var_type != "list":
                    return var_type
        return None

    def _infer_instance_attrs(
        self, assignments: list[Node], local_var_types: dict[str, str], module_qn: str
    ) -> None:
        for assign in assignments:
            left = assign.child_by_field_name("left")
            right = assign.child_by_field_name("right")
            if left and right and left.type == "attribute":
                left_text = safe_decode_text(left)
                if left_text and left_text.startswith("self."):
                    assigned_type = self._infer_simple_type(right, module_qn)
                    if assigned_type:
                        local_var_types[left_text] = assigned_type
