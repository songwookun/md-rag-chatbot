"""외부 서비스 예외 → 사용자에게 보여줄 한글 메시지.

TS 원본: src/app/api/chat/route.ts:11-49 getErrorMessage()

왜 따로 두는가 — 라우트 핸들러(api/chat.py)는 "흐름"만 보이게 하고,
"이 에러는 이렇게 안내한다"는 표는 여기 모아두면 나중에 문구만 고치기 쉽다.

★ 문자열 매칭인 이유: 세 SDK(httpx / google-genai / pinecone)가 각자 다른 예외 타입을
  던지는데, 공통점은 "메시지에 상태코드가 들어 있다"는 것뿐이다.
  그래서 어댑터들이 예외를 던질 때 상태코드를 메시지에 남기도록 맞춰 놨다.
  (adapters/github.py 의 _raise_for_status 참고)
  각 SDK 예외 타입을 확정하면 isinstance 로 바꾸는 게 더 정확하다.
"""

from typing import Literal

Service = Literal["Gemini", "GitHub", "Pinecone"]

# (매칭할 조각들, 사용자 문구) — 위에서부터 먼저 걸리는 것이 이긴다.
_RULES: dict[str, list[tuple[tuple[str, ...], str]]] = {
    "Gemini": [
        (
            ("429", "quota", "RESOURCE_EXHAUSTED"),
            "⚠️ Gemini API 사용량이 소진되었습니다. Google AI Studio에서 할당량을 확인해주세요.",
        ),
        (
            ("401", "403", "API_KEY_INVALID"),
            "⚠️ Gemini API 키가 유효하지 않습니다. 키를 재발급해주세요.",
        ),
        (("404",), "⚠️ Gemini 모델을 찾을 수 없습니다. 모델명을 확인해주세요."),
    ],
    "GitHub": [
        (("401", "Bad credentials"), "⚠️ GitHub 토큰이 만료되었습니다. 새 토큰을 발급해주세요."),
        (
            ("403", "rate limit"),
            "⚠️ GitHub API 호출 한도를 초과했습니다. 잠시 후 다시 시도해주세요.",
        ),
        (
            ("404",),
            "⚠️ GitHub 저장소를 찾을 수 없습니다. GITHUB_REPO 설정을 확인해주세요.",
        ),
        (("422",), "⚠️ GitHub 저장 실패: 같은 이름의 파일이 이미 존재합니다."),
    ],
    "Pinecone": [
        (
            ("401", "Unauthorized", "UNAUTHENTICATED"),
            "⚠️ Pinecone API 키가 유효하지 않습니다. 키를 확인해주세요.",
        ),
        (
            ("404", "not found"),
            "⚠️ Pinecone 인덱스를 찾을 수 없습니다. PINECONE_INDEX 설정을 확인해주세요.",
        ),
        (
            ("dimension",),
            "⚠️ Pinecone 벡터 차원이 일치하지 않습니다. "
            "인덱스 차원과 EMBEDDING_DIMENSIONS 설정이 같은지 확인해주세요.",
        ),
        (("quota", "limit"), "⚠️ Pinecone 무료 한도를 초과했습니다. 사용량을 확인해주세요."),
    ],
}


def user_message(exc: Exception, service: Service) -> str:
    """예외를 사용자용 안내 문구로 변환. 매칭 실패 시 원문을 그대로 노출한다.

    ★ fallback 에서 원문을 감추지 않는 이유:
      "알 수 없는 오류"만 보여주면 사용자(=개발자 본인)가 로그를 뒤져야 한다.
      개인용 도구라 원문 노출의 이득이 더 크다. 공개 서비스라면 반대로 감춰야 한다.
    """
    msg = str(exc)
    for needles, friendly in _RULES.get(service, []):
        if any(needle in msg for needle in needles):
            return friendly
    return f"⚠️ {service} 오류: {msg}"
