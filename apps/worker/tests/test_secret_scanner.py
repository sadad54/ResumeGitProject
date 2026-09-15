from proofhire_worker.ingestion.secret_scanner import contains_secret


def test_detects_aws_access_key():
    assert contains_secret("AWS_KEY = 'AKIAABCDEFGHIJKLMNOP'") is True


def test_detects_private_key_header():
    assert contains_secret("-----BEGIN RSA PRIVATE KEY-----\nMIIE...") is True


def test_detects_github_pat():
    assert contains_secret("token: ghp_" + "a" * 36) is True


def test_detects_openai_style_key():
    assert contains_secret('OPENAI_API_KEY="sk-' + "a" * 30 + '"') is True


def test_ordinary_source_code_is_clean():
    code = """
def add(a: int, b: int) -> int:
    return a + b
"""
    assert contains_secret(code) is False


def test_readme_prose_is_clean():
    text = "This project uses an API key for authentication, configured via env vars."
    assert contains_secret(text) is False
