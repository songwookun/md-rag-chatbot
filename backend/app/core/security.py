"""무상태(stateless) 인증 토큰.

TS 원본: src/lib/auth.ts

설계 아이디어 — 서버에 세션을 저장하지 않는다.
토큰 = "만료시각.HMAC서명(만료시각)"
서버는 서명키만 알면 되고, 받은 토큰의 서명을 다시 계산해서 같은지 보면 끝.
DB도 메모리 세션도 필요 없다. 대신 로그아웃 강제(토큰 폐기)는 불가능하다는 트레이드오프.

=== 2단계에서 구현 ===
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
        createHmac("sha256", getSecret()).update(payload).digest("hex")

    TODO(2단계): 구현
      힌트 — hmac.new(key: bytes, msg: bytes, hashlib.sha256).hexdigest()
             파이썬 hmac 은 str 이 아니라 bytes 를 받는다. .encode() 필요.
             키는 get_settings().signing_secret
    """
    raise NotImplementedError


def create_token() -> tuple[str, int]:
    """새 토큰 발급. (토큰문자열, max_age초) 반환.

    payload = 만료시각(ms). TS가 Date.now() + MAX_AGE*1000 을 썼으므로
    프론트/기존 쿠키와 형식을 맞추려면 파이썬도 ms 단위로 만든다.
    (time.time() 은 초 단위 float → int(time.time() * 1000))

    TS 대응: auth.ts:20-28

    TODO(2단계): 구현
      1. payload = str(만료시각 ms)
      2. token = f"{payload}.{_sign(payload)}"
      3. return token, TOKEN_MAX_AGE
    """
    raise NotImplementedError


def verify_token(raw: str | None) -> bool:
    """쿠키에서 꺼낸 토큰 문자열을 검증.

    검사 두 가지:
      ① 서명이 맞는가 (위조 아닌가)
      ② 아직 만료 전인가

    TS 대응: auth.ts:31-50

    TODO(2단계): 구현
      1. raw 가 없거나 "." 가 없으면 False
      2. rsplit(".", 1) 로 payload / sig 분리
         — 왜 rsplit 인가: payload 안에 점이 들어갈 가능성에 대비. TS도 lastIndexOf(".")
      3. hmac.compare_digest(sig, _sign(payload)) 로 비교
         ★ sig == _sign(payload) 로 쓰면 안 된다.
           일반 == 는 앞에서부터 비교하다 다르면 즉시 멈춰서, 응답 시간 차이로
           서명을 한 글자씩 알아낼 수 있다(타이밍 공격).
           compare_digest 는 항상 같은 시간이 걸린다. TS의 timingSafeEqual 과 같은 목적.
      4. int(payload) 가 현재 시각(ms)보다 큰지 확인. 숫자 변환 실패는 False
    """
    raise NotImplementedError


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
