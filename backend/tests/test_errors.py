"""에러 문구 매핑 — 어댑터가 남긴 문자열에서 원인을 골라내는지."""

from app.core import errors


def test_maps_github_status_code():
    exc = RuntimeError("GitHub API error 422 (save concepts/x.md): already exists")
    assert "이미 존재" in errors.user_message(exc, "GitHub")


def test_maps_github_bad_credentials():
    exc = RuntimeError("GitHub API error 401 (load x.md): Bad credentials")
    assert "토큰이 만료" in errors.user_message(exc, "GitHub")


def test_maps_gemini_quota():
    exc = RuntimeError("429 RESOURCE_EXHAUSTED: quota exceeded")
    assert "사용량이 소진" in errors.user_message(exc, "Gemini")


def test_maps_pinecone_dimension_mismatch():
    exc = RuntimeError("Vector dimension 768 does not match the index dimension 3072")
    assert "차원" in errors.user_message(exc, "Pinecone")


def test_falls_back_to_raw_message():
    """개인용 도구라 원문을 감추지 않는다 — 감추면 본인이 로그를 뒤져야 한다."""
    msg = errors.user_message(RuntimeError("뭔가 새로운 오류"), "Gemini")
    assert "뭔가 새로운 오류" in msg
