"""
PII Guardrail Tests

Unit tests for PII detection functionality.
"""

from app.governance_plane.guardrails.pii.patterns import (
    validate_email,
    validate_phone,
    validate_ssn,
    validate_credit_card,
)


class TestPIIValidators:
    """Tests for PII validators."""

    def test_validate_email_valid(self) -> None:
        """Test valid emails pass validation."""
        assert validate_email("test@example.com") is True
        assert validate_email("user.name@company.co.uk") is True

    def test_validate_email_invalid(self) -> None:
        """Test invalid emails fail validation."""
        assert validate_email("notanemail") is False
        assert validate_email("missing@domain") is False

    def test_validate_phone_valid(self) -> None:
        """Test valid phone numbers pass validation."""
        assert validate_phone("555-123-4567") is True
        assert validate_phone("(555) 123-4567") is True
        assert validate_phone("5551234567") is True

    def test_validate_phone_invalid(self) -> None:
        """Test invalid phone numbers fail validation."""
        assert validate_phone("123") is False
        assert validate_phone("abc-def-ghij") is False

    def test_validate_ssn_valid(self) -> None:
        """Test valid SSNs pass validation."""
        assert validate_ssn("123-45-6789") is True
        assert validate_ssn("123456789") is True

    def test_validate_ssn_invalid(self) -> None:
        """Test invalid SSNs fail validation."""
        assert validate_ssn("000-45-6789") is False  # Area 000 invalid
        assert validate_ssn("666-45-6789") is False  # Area 666 invalid
        assert validate_ssn("900-45-6789") is False  # Area 900+ invalid

    def test_validate_credit_card_valid(self) -> None:
        """Test valid credit cards pass Luhn check."""
        # Test card numbers (from Stripe test cards)
        assert validate_credit_card("4242424242424242") is True
        assert validate_credit_card("4242-4242-4242-4242") is True

    def test_validate_credit_card_invalid(self) -> None:
        """Test invalid credit cards fail Luhn check."""
        assert validate_credit_card("1234567890123456") is False
        assert validate_credit_card("123") is False
