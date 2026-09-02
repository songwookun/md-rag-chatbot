"""무상태(stateless) 인증 토큰.

TS 원본: src/lib/auth.ts

설계 아이디어 — 서버에 세션을 저장하지 않는다.
토큰 = "만료시각.HMAC서명(만료시각)"
서버는 서명키만 알면 되고, 받은 토큰의 서명을 다시 계산해서 같은지 보면 끝.
DB도 메모리 세션도 필요 없다. 대신 로그아웃 강제(토큰 폐기)는 불가능하다는 트레이드오프.
"""

import hashlib
import hmac
import time

from app.config import get_settings

TOKEN_COOKIE = "auth_token"
TOKEN_MAX_AGE = 60 * 60 * 24  # 24시간(초). TS: auth.ts:5


def _sign(payload: str) -> str:
    """payload 를 HMAC-SHA256 으로 서명해 hex 문자열로 반환.

    왜 HMAC 인가: 단순 해시(sha256(payload))는 누구나 계산할 수 있어 위조된다.
    HMAC 은 비밀키를 알아야 같은 값이 나오므로 "서버가 발급한 것"임을 증명한다.

    TS 대응: auth.ts:15-17
    """
    return hmac.new(
        get_settings().signing_secret.encode(),
        payload.encode(),
        hashlib.sha256,
    ).hexdigest()


def create_token() -> tuple[str, int]:
    """새 토큰 발급. (토큰문자열, max_age초) 반환.

    payload = 만료시각(ms). TS가 Date.now() + MAX_AGE*1000 을 썼으므로
    기존 쿠키와 형식을 맞추려면 파이썬도 ms 단위로 만든다.

    TS 대응: auth.ts:20-28
    """
    payload = str(int(time.time() * 1000) + TOKEN_MAX_AGE * 1000)
    return f"{payload}.{_sign(payload)}", TOKEN_MAX_AGE


def verify_token(raw: str | None) -> bool:
    """쿠키에서 꺼낸 토큰 문자열을 검증. 서명이 맞고, 아직 만료 전이면 True.

    TS 대응: auth.ts:31-50
    """
    if not raw or "." not in raw:
        return False

    # rsplit — payload 안에 점이 들어갈 가능성에 대비. TS도 lastIndexOf(".")
    payload, sig = raw.rsplit(".", 1)

    # ★ sig == _sign(payload) 로 쓰면 안 된다.
    #   일반 == 는 앞에서부터 비교하다 다르면 즉시 멈춰서, 응답 시간 차이로
    #   서명을 한 글자씩 알아낼 수 있다(타이밍 공격).
    #   compare_digest 는 항상 같은 시간이 걸린다. TS의 timingSafeEqual 과 같은 목적.
    # .encode() 필수 — 쿠키에 한글 같은 non-ASCII 를 넣어 보내면
    #   str 버전 compare_digest 가 TypeError 를 던져 500 이 난다(외부 입력이므로 방어).
    if not hmac.compare_digest(sig.encode(), _sign(payload).encode()):
        return False

    try:
        expires_at_ms = int(payload)
    except ValueError:
        # payload 가 숫자가 아니면 우리가 발급한 토큰이 아니다.
        # ※ 서명 검증을 이미 통과했으므로 실제로는 도달하기 어렵지만,
        #   "서명이 맞다"와 "형식이 맞다"는 별개 보장이라 따로 막는다.
        return False

    return expires_at_ms > int(time.time() * 1000)


def cookie_kwargs() -> dict:
    """FastAPI Response.set_cookie() 에 넘길 옵션 묶음.

    Next의 Set-Cookie 문자열과 같은 의미를 갖도록 맞춘다.
      HttpOnly  — JS에서 못 읽음 (XSS 방어)
      SameSite=lax — 다른 사이트에서 온 요청에는 쿠키를 안 붙임 (CSRF 완화)
      Secure    — HTTPS 에서만 전송. 로컬 http 개발에서 켜면 쿠키가 아예 저장 안 되므로
                  프로덕션에서만 켠다. TS: auth.ts:25

    TS 대응: auth.ts:26
    """
    return {
        "key": TOKEN_COOKIE,
        "httponly": True,
        "samesite": "lax",
        "path": "/",
        "max_age": TOKEN_MAX_AGE,
        "secure": get_settings().is_production,
    }
