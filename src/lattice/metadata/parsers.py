import json
import re
from typing import Any

from lattice.metadata.models import (
    CoreFeature,
    DependencyInfo,
    EntryPoint,
    FolderNode,
    TechStack,
)


def parse_field_response(field_name: str, content: str) -> Any:
    if field_name in ("project_overview", "architecture_diagram"):
        json_str = extract_json(content)
        if json_str:
            try:
                parsed = json.loads(json_str)
                if isinstance(parsed, dict):
                    return (
                        parsed.get("overview")
                        or parsed.get("diagram")
                        or parsed.get("content")
                        or str(parsed)
                    )
            except json.JSONDecodeError:
                pass
        content = strip_code_blocks(content)
        return content.strip()

    json_str = extract_json(content)
    if not json_str:
        raise ValueError(f"No JSON found in response for {field_name}")

    parsed = json.loads(json_str)

    if field_name == "folder_structure":
        return FolderNode.model_validate(parsed)
    elif field_name == "tech_stack":
        return TechStack.model_validate(parsed)
    elif field_name == "dependencies":
        return DependencyInfo.model_validate(parsed)
    elif field_name == "entry_points":
        if not isinstance(parsed, list):
            parsed = [parsed]
        return [EntryPoint.model_validate(e) for e in parsed]
    elif field_name == "core_features":
        if not isinstance(parsed, list):
            parsed = [parsed]
        return [CoreFeature.model_validate(f) for f in parsed]
    else:
        return parsed


def extract_json(content: str) -> str | None:
    code_block_pattern = r"```(?:json)?\s*([\s\S]*?)```"
    for match in re.finditer(code_block_pattern, content):
        candidate = match.group(1).strip()
        if candidate:
            try:
                json.loads(candidate)
                return candidate
            except json.JSONDecodeError:
                continue

    result = find_json_by_brackets(content)
    if result:
        return result

    return None


def find_json_by_brackets(content: str) -> str | None:
    first_obj = content.find("{")
    first_arr = content.find("[")

    if first_obj == -1 and first_arr == -1:
        return None
    elif first_arr == -1:
        order = [("{", "}")]
    elif first_obj == -1:
        order = [("[", "]")]
    elif first_arr < first_obj:
        order = [("[", "]"), ("{", "}")]
    else:
        order = [("{", "}"), ("[", "]")]

    for start_char, end_char in order:
        start_idx = content.find(start_char)
        if start_idx != -1:
            depth = 0
            in_string = False
            escape_next = False

            for i, char in enumerate(content[start_idx:], start_idx):
                if escape_next:
                    escape_next = False
                    continue
                if char == "\\":
                    escape_next = True
                    continue
                if char == '"' and not escape_next:
                    in_string = not in_string
                    continue
                if in_string:
                    continue
                if char == start_char:
                    depth += 1
                elif char == end_char:
                    depth -= 1
                    if depth == 0:
                        candidate = content[start_idx : i + 1]
                        try:
                            json.loads(candidate)
                            return candidate
                        except json.JSONDecodeError:
                            break
    return None


def strip_code_blocks(content: str) -> str:
    content = re.sub(r"```\w*\n?", "", content)
    return content.strip()
