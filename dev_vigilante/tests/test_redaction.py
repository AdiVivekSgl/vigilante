from dev_vigilante.redaction import REDACTED, redact


def test_secret_keys_are_redacted():
    out = redact({"db_password": "x", "encryption_key": "y", "db_name": "site1"})
    assert out["db_password"] == REDACTED
    assert out["encryption_key"] == REDACTED
    assert out["db_name"] == "site1"


def test_nested_dicts_and_lists_are_walked():
    out = redact({"backups": [{"aws_access_key_id": "AKIA", "bucket": "b"}]})
    assert out["backups"][0]["aws_access_key_id"] == REDACTED
    assert out["backups"][0]["bucket"] == "b"


def test_url_credentials_are_masked():
    out = redact({"redis_cache": "redis://:hunter2@localhost:13000"})
    assert "hunter2" not in out["redis_cache"]
    assert out["redis_cache"] == f"redis://:{REDACTED}@localhost:13000"


def test_urls_without_credentials_are_untouched():
    assert redact("https://erp.example.com:8000/app") == "https://erp.example.com:8000/app"
