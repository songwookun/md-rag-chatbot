"""크로스인코더 리랭커 — 질문과 문서를 같이 보고 관련도를 다시 매긴다.

실험③(docs/experiments/03-abstention.md)에서 채택한 수단.

★ 임베딩과 무엇이 다른가
  임베딩(바이인코더)은 질문과 문서를 **따로** 인코딩해 벡터 거리를 잰다.
  그래서 "주제가 비슷한가"는 잘 재지만 "답이 실제로 적혀 있는가"는 못 본다.
  크로스인코더는 둘을 **한 모델에 같이 넣어** 상호작용을 본다.

  실험③ 결과 — 보류AUC 0.9605 → 1.0000, 층 누수 6/28 → 0/28,
  그리고 R@1 이 0.947 → 1.000 으로 검색까지 좋아졌다.

★ 왜 상위 k개에만 거는가
  사전 색인이 불가능하다. 질문이 와야 계산할 수 있어서 문서 수에 비례해 느려진다.
  임베딩이 후보를 좁히고, 리랭커가 그 안에서 다시 매기는 2단 구조가 표준이다.

★ 무거운 의존성을 지연 로드하는 이유
  torch 가 2GB 다. 서빙 기본 설치(`pip install -e .`)에는 들어가지 않고
  `[lab]` 에만 있다. RERANK_ENABLED=false 로 두면 이 모듈은 import 만 되고
  torch 를 건드리지 않으므로, 리랭커 없이도 서버가 뜬다.
"""

import asyncio
import logging
from functools import lru_cache

from app.config import get_settings

log = logging.getLogger(__name__)

# 리랭커에 넘기기 전 문서를 자르는 길이. 위 score() 주석의 실측 근거 참고.
MAX_CHARS = 3000


@lru_cache
def _model():
    """크로스인코더 로드 (프로세스당 한 번). 첫 호출에서 가중치를 내려받는다.

    ★ import 를 함수 안에 둔다 — 모듈 최상단에 두면 torch 없이 서버가 안 뜬다.
    """
    try:
        from sentence_transformers import CrossEncoder  # noqa: PLC0415
        import torch  # noqa: PLC0415
    except ImportError as exc:  # pragma: no cover - 설치 안내
        raise RuntimeError(
            "재순위화가 켜져 있는데 리랭커 의존성이 없습니다. "
            "`pip install -e \".[rerank]\"` 로 설치하거나 RERANK_ENABLED=false 로 끄세요."
        ) from exc

    settings = get_settings()
    device = "mps" if torch.backends.mps.is_available() else "cpu"
    log.info("리랭커 로드: %s on %s", settings.rerank_model, device)
    return CrossEncoder(settings.rerank_model, device=device, max_length=512)


async def score(question: str, documents: list[str]) -> list[float]:
    """(질문, 문서) 쌍마다 0~1 관련도. 문서 순서 그대로 반환한다.

    ★ CrossEncoder.predict 는 동기 함수다. async 핸들러에서 그냥 부르면
      추론하는 2초 동안 이벤트 루프가 멈춰 다른 요청까지 대기한다.
      adapters/pinecone.py 와 같은 이유로 to_thread 로 보낸다.

    ★ max_length=512 라 긴 노트는 앞부분만 본다. 뒤쪽에만 답이 있는 긴 노트는 놓칠 수 있다.

    ★ 넣기 전에 MAX_CHARS 로 자른다 — 성능 때문이다.
      max_length 는 **토크나이즈한 뒤** 자르므로, 47,813자 노트를 통째로 넘기면
      버려질 토큰까지 전부 토크나이징한다. 실측:
          자르지 않음(55,159자)  6.86초
          3000자로 자름          2.09초   점수 변화 0.00000
          1500자로 자름          1.93초   점수 변화 0.00746  ← 여기선 결과가 바뀐다
      3000자는 512 토큰을 채우고도 남는 여유값이다. 1500자는 부족하다.
    """
    if not documents:
        return []
    documents = [d[:MAX_CHARS] for d in documents]

    def _run() -> list[float]:
        # ★ _model() 도 스레드 안에서 부른다.
        #   to_thread(_model().predict, ...) 로 쓰면 **_model() 이 이벤트 루프에서
        #   먼저 평가된다.** 첫 호출에서 2.3GB 가중치를 로드하는 동안 루프가 통째로
        #   멈춰 /health 조차 27초 걸렸다. 실제로 겪은 버그다.
        pairs = [(question, d) for d in documents]
        return [float(s) for s in _model().predict(pairs, show_progress_bar=False)]

    return await asyncio.to_thread(_run)
