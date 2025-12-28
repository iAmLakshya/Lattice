import re

from lattice.documents.models import ExplicitReference
from lattice.shared.config.loader import ReferenceExtractionConfig


class ReferenceExtractor:
    INLINE_PATTERNS = {
        "backtick_qualified": (
            re.compile(r"`([A-Za-z_][A-Za-z0-9_]*(?:\.[A-Za-z_][A-Za-z0-9_]*)+)`"),
            ReferenceExtractionConfig.backtick_qualified_confidence,
        ),
        "backtick_simple": (
            re.compile(r"`([A-Za-z_][A-Za-z0-9_]*)`"),
            ReferenceExtractionConfig.backtick_simple_confidence,
        ),
        "class_name": (
            re.compile(r"\b([A-Z][a-z]+(?:[A-Z][a-z]+)+)\b"),
            ReferenceExtractionConfig.class_name_confidence,
        ),
        "function_call": (
            re.compile(r"\b([a-z_][a-z0-9_]*)\s*\("),
            ReferenceExtractionConfig.function_call_confidence,
        ),
    }

    CODE_BLOCK_PATTERNS = {
        "python_def": (
            re.compile(r"(?:def|async def)\s+([A-Za-z_][A-Za-z0-9_]*)"),
            ReferenceExtractionConfig.python_def_confidence,
        ),
        "python_class": (
            re.compile(r"class\s+([A-Za-z_][A-Za-z0-9_]*)"),
            ReferenceExtractionConfig.python_class_confidence,
        ),
        "js_function": (
            re.compile(r"function\s+([A-Za-z_][A-Za-z0-9_]*)"),
            ReferenceExtractionConfig.js_function_confidence,
        ),
        "import_from": (
            re.compile(r"from\s+[\w.]+\s+import\s+([A-Za-z_][A-Za-z0-9_,\s]*)"),
            ReferenceExtractionConfig.import_from_confidence,
        ),
    }

    CODE_BLOCK_REGEX = re.compile(r"```[\s\S]*?```", re.MULTILINE)

    def extract(
        self,
        content: str,
        known_entities: set[str],
    ) -> list[ExplicitReference]:
        references = []

        code_blocks = self.CODE_BLOCK_REGEX.findall(content)
        for block in code_blocks:
            self._extract_from_code_block(block, known_entities, references)

        lines = content.split("\n")
        for line_num, line in enumerate(lines, 1):
            for pattern_name, (pattern, base_confidence) in self.INLINE_PATTERNS.items():
                for match in pattern.finditer(line):
                    ref_text = match.group(1)
                    matched_entity = self._match_entity(ref_text, known_entities)

                    if matched_entity:
                        references.append(
                            ExplicitReference(
                                text=ref_text,
                                entity_qualified_name=matched_entity,
                                pattern_type=pattern_name,
                                confidence=base_confidence,
                                line_number=line_num,
                            )
                        )

        seen = {}
        for ref in references:
            key = ref.entity_qualified_name
            if key not in seen or ref.confidence > seen[key].confidence:
                seen[key] = ref

        return list(seen.values())

    def _extract_from_code_block(
        self,
        block_content: str,
        known_entities: set[str],
        references: list[ExplicitReference],
    ) -> None:
        for pattern_name, (pattern, confidence) in self.CODE_BLOCK_PATTERNS.items():
            for match in pattern.finditer(block_content):
                ref_text = match.group(1)
                if "," in ref_text:
                    for part in ref_text.split(","):
                        part = part.strip()
                        matched = self._match_entity(part, known_entities)
                        if matched:
                            references.append(
                                ExplicitReference(
                                    text=part,
                                    entity_qualified_name=matched,
                                    pattern_type=pattern_name,
                                    confidence=confidence,
                                    line_number=0,
                                )
                            )
                else:
                    matched = self._match_entity(ref_text, known_entities)
                    if matched:
                        references.append(
                            ExplicitReference(
                                text=ref_text,
                                entity_qualified_name=matched,
                                pattern_type=pattern_name,
                                confidence=confidence,
                                line_number=0,
                            )
                        )

    def _match_entity(self, ref_text: str, known_entities: set[str]) -> str | None:
        if ref_text in known_entities:
            return ref_text

        for entity in known_entities:
            parts = entity.split(".")
            if parts[-1] == ref_text:
                return entity
            if len(parts) >= 2 and f"{parts[-2]}.{parts[-1]}" == ref_text:
                return entity

        return None

    def extract_entity_names(self, content: str) -> set[str]:
        names = set()

        for _, (pattern, _) in self.INLINE_PATTERNS.items():
            for match in pattern.finditer(content):
                names.add(match.group(1))

        code_blocks = self.CODE_BLOCK_REGEX.findall(content)
        for block in code_blocks:
            for _, (pattern, _) in self.CODE_BLOCK_PATTERNS.items():
                for match in pattern.finditer(block):
                    ref_text = match.group(1)
                    if "," in ref_text:
                        for part in ref_text.split(","):
                            names.add(part.strip())
                    else:
                        names.add(ref_text)

        return names
