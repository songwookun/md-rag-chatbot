"""2단계 — 토큰 발급/검증.

외부 호출이 없는 순수 로직이라 네트워크 없이 전부 돈다.
"""

import time

from app.core import security


def test_token_roundtrip():
    """방금 발급한 토큰은 통과해야 한다."""
    token, max_age = security.create_token()
    assert max_age == security.TOKEN_MAX_AGE
    assert security.verify_token(token) is True


def test_rejects_tampered_signature():
    """서명을 한 글자만 바꿔도 거부돼야 한다 — 이게 HMAC 을 쓰는 이유다."""
    token, _ = security.create_token()
    payload, sig = token.rsplit(".", 1)
    flipped = "0" if sig[-1] != "0" else "1"
    assert security.verify_token(f"{payload}.{sig[:-1]}{flipped}") is False


def test_rejects_tampered_payload():
    """만료시각을 미래로 늘려도 서명이 안 맞으므로 거부된다."""
    token, _ = security.create_token()
    _, sig = token.rsplit(".", 1)
    forged_expiry = str(int(time.time() * 1000) + 999_999_999)
    assert security.verify_token(f"{forged_expiry}.{sig}") is False


def test_rejects_expired_token():
    """서명이 맞아도 만료됐으면 거부. 과거 시각으로 직접 서명해 만든다."""
    past = str(int(time.time() * 1000) - 1000)
    expired = f"{past}.{security._sign(past)}"
    assert security.verify_token(expired) is False


def test_rejects_malformed():
    """형식이 아예 아닌 입력들. 예외가 아니라 False 여야 한다."""
    for bad in (None, "", "점없음", "한글.서명", ".", "abc.def"):
        assert security.verify_token(bad) is False
