"""FastAPI 앱 진입점.

TS 대응: Next.js는 파일 경로가 곧 라우트라 이런 파일이 없었다.
FastAPI는 라우터를 명시적으로 등록한다 — 어떤 엔드포인트가 있는지 한눈에 보이는 게 장점.
"""

from contextlib import asynccontextmanager

from fastapi import FastAPI

import asyncio
import logging

from app.adapters import github, reranker
from app.api import auth, chat, collect, sync
from app.config import get_settings


# ★ 앱 로거를 설정한다.
#   uvicorn 은 자기 로거만 설정해서, 앱 모듈의 log.info/log.warning 이 아무 데도 안 나간다.
#   실제로 리랭커 워밍업 로그가 통째로 사라져 성공했는지 알 수 없었다.
#   워밍업 실패나 노트 로드 실패는 조용히 넘어가는 종류라 로그가 유일한 단서다.
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)-7s %(name)s: %(message)s",
    datefmt="%H:%M:%S",
)

log = logging.getLogger(__name__)


async def _warm_reranker() -> None:
    """리랭커 모델을 미리 올려둔다.

    ★ 왜 필요한가 — 지연 로드로 두면 **첫 질문이 35초** 걸린다(실측).
      추론 자체는 2.5초인데 torch import + 가중치 로드 + MPS 워밍업이 그만큼이다.

    ★ 왜 실제와 같은 모양으로 부르는가
      처음엔 `score("워밍업", ["워밍업"])` 로 했는데 **효과가 없었다.**
      MPS 는 텐서 모양이 바뀌면 다시 컴파일해서, 작은 입력으로 데워도
      첫 실제 질문이 9.9초 걸렸다(안정 상태 2.2초). 실측:
          1회차 9.86 → 2회차 4.01 → 5회차 2.76 → 안정 2.2초
      그래서 TOP_K 개 × MAX_CHARS 로 같은 모양을 미리 통과시킨다.

    ★ 왜 백그라운드인가 — 기동을 35초 막으면 `--reload` 개발이 괴롭고,
      헬스체크가 늦어 배포 실패로 잡히는 환경도 있다.
      로그인하고 질문을 던질 때쯤이면 대개 준비가 끝나 있다.

    실패해도 앱은 뜬다 — 그때는 첫 질문에서 지연 로드된다.
    """
    try:
        # retrieval 이 실제로 넘기는 것과 같은 모양 (문서 수 × 길이)
        from app.services.retrieval import TOP_K  # noqa: PLC0415

        await reranker.score("워밍업 질문", ["워밍업 " * (reranker.MAX_CHARS // 4)] * TOP_K)
        log.info("리랭커 준비 완료")
    except Exception as exc:
        log.warning("리랭커 워밍업 실패 — 첫 질문에서 로드됩니다: %s", exc)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """앱 수명 동안 유지되는 자원 정리.

    github 어댑터가 연결 재사용을 위해 httpx.AsyncClient 를 하나 들고 있다.
    종료할 때 닫지 않으면 "Unclosed client session" 경고가 뜬다.
    """
    task = None
    if get_settings().rerank_enabled:
        task = asyncio.create_task(_warm_reranker())
    yield
    if task and not task.done():
        task.cancel()
    await github.close()


app = FastAPI(
    title="md-rag-chatbot backend",
    description="마크다운 노트 기반 RAG 챗봇 엔진",
    version="0.1.0",
    lifespan=lifespan,
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

app.include_router(auth.router, prefix="/api", tags=["auth"])
app.include_router(chat.router, prefix="/api", tags=["chat"])
app.include_router(sync.router, prefix="/api", tags=["sync"])
app.include_router(collect.router, prefix="/api", tags=["collect"])
