from payops_core.auth.audit import sanitize_metadata
from payops_core.auth.passwords import hash_password, verify_password
from payops_core.auth.policy import validate_signup


def test_password_is_hashed_and_verified() -> None:
    stored = hash_password("Testuser1!x")
    assert stored.startswith("scrypt$")
    assert "Testuser1!x" not in stored
    assert verify_password("Testuser1!x", stored)
    assert not verify_password("wrong-password", stored)


def test_signup_validation_covers_required_cases() -> None:
    assert validate_signup("Ada Lovelace", "ada@payintel.test", "Testuser1!x", "Testuser1!x") == []
    invalid = validate_signup("Ada", "not-an-email", "Testuser1!x", "Testuser1!x")
    mismatch = validate_signup("Ada", "ada@payintel.test", "Testuser1!x", "other")
    assert any("valid email" in item.lower() for item in invalid)
    assert any("match" in item.lower() for item in mismatch)
    weak = validate_signup("Ada", "ada@payintel.test", "short", "short")
    assert weak


def test_audit_metadata_strips_secrets() -> None:
    clean = sanitize_metadata(
        {
            "email": "ada@payintel.test",
            "password": "secret",
            "token": "abc",
            "reset_token": "xyz",
            "api_key": "k",
            "from_role": "user",
        }
    )
    assert clean == {"email": "ada@payintel.test", "from_role": "user"}
