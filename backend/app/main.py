"""FastAPI 앱 진입점.

TS 대응: Next.js는 파일 경로가 곧 라우트라 이런 파일이 없었다.
FastAPI는 라우터를 명시적으로 등록한다 — 어떤 엔드포인트가 있는지 한눈에 보이는 게 장점.

이 파일은 1단계까지 완성된 상태. 라우터를 하나씩 구현할 때마다
아래 include_router 주석을 풀면 된다.
"""

from fastapi import FastAPI

from app.config import get_settings

app = FastAPI(
    title="md-rag-chatbot backend",
    description="마크다운 노트 기반 RAG 챗봇 엔진",
    version="0.1.0",
)


@app.get("/health")
def health() -> dict:
    """서버가 살아있는지 + 환경변수가 채워졌는지 확인.

    설정 누락을 여기서 먼저 드러내면, 나중에 Gemini 401 같은
    엉뚱한 에러로 헤매는 걸 막을 수 있다.
    """
    settings = get_settings()
    missing = settings.missing_keys()
    return {
        "status": "ok" if not missing else "misconfigured",
        "env": settings.app_env,
        "missing_env": missing,
    }


# ---------------------------------------------------------------
# 라우터 등록 — 각 단계에서 해당 줄의 주석을 해제한다.
#
# prefix 를 "/api" 로 맞춰두면 Next 프록시에서 경로를 그대로 전달할 수 있다.
#   Next: /api/chat  →  Python: /api/chat
# ---------------------------------------------------------------

# TODO(2단계): from app.api import auth
#              app.include_router(auth.router, prefix="/api", tags=["auth"])

# TODO(6단계): from app.api import chat
#              app.include_router(chat.router, prefix="/api", tags=["chat"])

# TODO(7단계): from app.api import sync, collect
#              app.include_router(sync.router, prefix="/api", tags=["sync"])
#              app.include_router(collect.router, prefix="/api", tags=["collect"])
