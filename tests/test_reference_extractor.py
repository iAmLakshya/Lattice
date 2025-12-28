"""Tests for the ReferenceExtractor class."""

import pytest

from lattice.documents.reference_extractor import ReferenceExtractor


class TestReferenceExtractor:
    @pytest.fixture
    def extractor(self):
        return ReferenceExtractor()

    @pytest.fixture
    def known_entities(self):
        return {
            "AuthService",
            "AuthService.login",
            "AuthService.logout",
            "UserRepository",
            "UserRepository.find_by_id",
            "utils.crypto.hash_password",
            "generate_token",
            "PaymentService",
            "PaymentService.process_payment",
        }

    def test_extract_backtick_references(self, extractor, known_entities):
        content = "The `AuthService` handles authentication. Use `login` method."

        refs = extractor.extract(content, known_entities)

        entity_names = {r.entity_qualified_name for r in refs}
        assert "AuthService" in entity_names

    def test_extract_qualified_name_reference(self, extractor, known_entities):
        content = "Call `AuthService.login` to authenticate users."

        refs = extractor.extract(content, known_entities)

        entity_names = {r.entity_qualified_name for r in refs}
        assert "AuthService.login" in entity_names

    def test_extract_from_code_block(self, extractor, known_entities):
        content = """
Here's how to use the service:

```python
from services import AuthService

async def authenticate():
    service = AuthService()
    token = await service.login("user@example.com", "password")
```
"""
        refs = extractor.extract(content, known_entities)

        entity_names = {r.entity_qualified_name for r in refs}
        assert "AuthService" in entity_names

    def test_extract_function_definition_in_code_block(self, extractor, known_entities):
        content = """
```python
def hash_password(password: str) -> str:
    return bcrypt.hash(password)
```
"""
        refs = extractor.extract(content, known_entities)

        entity_names = {r.entity_qualified_name for r in refs}
        assert "utils.crypto.hash_password" in entity_names

    def test_extract_class_definition_in_code_block(self, extractor, known_entities):
        content = """
```python
class UserRepository:
    def find_by_id(self, id):
        pass
```
"""
        refs = extractor.extract(content, known_entities)

        entity_names = {r.entity_qualified_name for r in refs}
        assert "UserRepository" in entity_names

    def test_extract_pascal_case_class_name(self, extractor, known_entities):
        content = "The PaymentService handles all payment operations."

        refs = extractor.extract(content, known_entities)

        entity_names = {r.entity_qualified_name for r in refs}
        assert "PaymentService" in entity_names

    def test_deduplicates_references(self, extractor, known_entities):
        content = """
`AuthService` is important.
Use `AuthService` for authentication.
The AuthService class handles login.
"""
        refs = extractor.extract(content, known_entities)

        auth_refs = [r for r in refs if r.entity_qualified_name == "AuthService"]
        assert len(auth_refs) == 1

    def test_keeps_highest_confidence(self, extractor, known_entities):
        content = "`AuthService` and AuthService both appear."

        refs = extractor.extract(content, known_entities)

        auth_ref = next(
            (r for r in refs if r.entity_qualified_name == "AuthService"), None
        )
        assert auth_ref is not None
        assert auth_ref.confidence >= 0.8

    def test_no_matches_returns_empty(self, extractor, known_entities):
        content = "This document has no code references at all."

        refs = extractor.extract(content, known_entities)

        assert len(refs) == 0

    def test_partial_match_not_extracted(self, extractor, known_entities):
        content = "The authentication service is important."

        refs = extractor.extract(content, known_entities)

        entity_names = {r.entity_qualified_name for r in refs}
        assert "AuthService" not in entity_names

    def test_tracks_line_numbers(self, extractor, known_entities):
        content = """Line 1
Line 2
The `AuthService` is here on line 3.
Line 4
"""
        refs = extractor.extract(content, known_entities)

        auth_ref = next(
            (r for r in refs if r.entity_qualified_name == "AuthService"), None
        )
        assert auth_ref is not None
        assert auth_ref.line_number == 3

    def test_extract_entity_names_without_known(self, extractor):
        content = """
The `MyClass` handles things.

```python
def my_function():
    pass

class AnotherClass:
    pass
```
"""
        names = extractor.extract_entity_names(content)

        assert "MyClass" in names
        assert "my_function" in names
        assert "AnotherClass" in names

    def test_confidence_levels(self, extractor, known_entities):
        content = """
`AuthService.login` is specific.
`AuthService` is a class.
PaymentService handles payments.
"""
        refs = extractor.extract(content, known_entities)

        qualified_ref = next(
            (r for r in refs if r.entity_qualified_name == "AuthService.login"), None
        )
        simple_ref = next(
            (r for r in refs if r.entity_qualified_name == "PaymentService"), None
        )

        if qualified_ref and simple_ref:
            assert qualified_ref.confidence >= simple_ref.confidence

    def test_pattern_types_are_set(self, extractor, known_entities):
        content = "`AuthService` and PaymentService"

        refs = extractor.extract(content, known_entities)

        pattern_types = {r.pattern_type for r in refs}
        assert "backtick_simple" in pattern_types or "class_name" in pattern_types

    def test_import_statement_extraction(self, extractor, known_entities):
        content = """
```python
from services.auth import AuthService, UserRepository
```
"""
        refs = extractor.extract(content, known_entities)

        entity_names = {r.entity_qualified_name for r in refs}
        assert "AuthService" in entity_names
        assert "UserRepository" in entity_names

    def test_suffix_matching(self, extractor, known_entities):
        content = "Use `find_by_id` to look up users."

        refs = extractor.extract(content, known_entities)

        entity_names = {r.entity_qualified_name for r in refs}
        assert "UserRepository.find_by_id" in entity_names

    def test_method_pattern_matching(self, extractor, known_entities):
        content = "Call `UserRepository.find_by_id` for lookups."

        refs = extractor.extract(content, known_entities)

        entity_names = {r.entity_qualified_name for r in refs}
        assert "UserRepository.find_by_id" in entity_names

    def test_with_real_auth_doc(self, extractor, sample_docs_path):
        if not sample_docs_path.exists():
            pytest.skip("Sample docs not found")

        auth_file = sample_docs_path / "authentication.md"
        content = auth_file.read_text()

        known_entities = {
            "AuthService",
            "AuthService.login",
            "AuthService.logout",
            "AuthService.verify_token",
            "AuthService.register",
            "UserRepository",
            "utils.crypto.hash_password",
            "utils.crypto.generate_token",
        }

        refs = extractor.extract(content, known_entities)

        entity_names = {r.entity_qualified_name for r in refs}

        assert "AuthService" in entity_names

    def test_with_real_payment_doc(self, extractor, sample_docs_path):
        if not sample_docs_path.exists():
            pytest.skip("Sample docs not found")

        payment_file = sample_docs_path / "payments.md"
        content = payment_file.read_text()

        known_entities = {
            "PaymentService",
            "PaymentService.create_intent",
            "PaymentService.process_payment",
            "PaymentService.refund",
            "PaymentService.cancel",
            "PaymentError",
            "InsufficientFundsError",
        }

        refs = extractor.extract(content, known_entities)

        entity_names = {r.entity_qualified_name for r in refs}

        assert "PaymentService" in entity_names

    def test_empty_content(self, extractor, known_entities):
        refs = extractor.extract("", known_entities)
        assert refs == []

    def test_empty_known_entities(self, extractor):
        content = "`SomeClass` and `some_function` are mentioned."
        refs = extractor.extract(content, set())
        assert refs == []

    def test_function_call_pattern(self, extractor, known_entities):
        content = "You can call generate_token() to create tokens."

        refs = extractor.extract(content, known_entities)

        entity_names = {r.entity_qualified_name for r in refs}
        assert "generate_token" in entity_names

    @pytest.fixture
    def sample_docs_path(self):
        from pathlib import Path
        return Path(__file__).parent / "fixtures" / "sample_docs"
