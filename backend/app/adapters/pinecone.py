"""Pinecone 어댑터 — 벡터 저장/검색.

TS 원본: src/lib/pinecone.ts

★ 파이썬 특유의 함정: pinecone SDK는 동기(blocking) 라이브러리다.
  FastAPI의 async 핸들러 안에서 그냥 호출하면 그 순간 이벤트 루프 전체가 멈춰서
  다른 요청도 같이 대기한다. 반드시 asyncio.to_thread 로 감싸 별도 스레드로 보낼 것.
  TS에는 없던 고민 — Node는 SDK가 애초에 전부 비동기였다.

★ 임계값이 여기 없는 이유 (TS와 달라진 점):
  TS는 pinecone.ts:79 에서 THRESHOLD 로 걸러서 반환했다. 즉 "얼마나 닮아야
  관련 있다고 볼 것인가"라는 **판단**이 어댑터에 박혀 있었다.
  여기서는 어댑터가 점수를 그대로 돌려주고, 자르는 결정은 services/ 가 한다.
    - services/retrieval.py — 답변을 보류할지 (abstention)
    - services/ingest.py    — 관련 노트로 링크를 걸지
  같은 점수라도 두 용도의 기준이 다를 수 있고, 무엇보다 "언제 답을 안 할지"는
  이 시스템의 핵심 판단이라 검색 배관에 숨어 있으면 안 된다.
"""

import asyncio
import base64
import re
from functools import lru_cache

from pinecone import Pinecone

from app.adapters import gemini
from app.config import get_settings
from app.schemas.chat import NoteHit

_NOT_FOUND = re.compile(r"not found|404", re.IGNORECASE)


@lru_cache
def _index():
    """Pinecone 인덱스 핸들 (지연 생성 + 재사용).

    TS 대응: pinecone.ts:4-17 — 모듈 전역에 클라이언트를 캐시하는 패턴
    """
    settings = get_settings()
    if not settings.pinecone_api_key or not settings.pinecone_index:
        raise RuntimeError("Pinecone not configured (PINECONE_API_KEY / PINECONE_INDEX)")
    return Pinecone(api_key=settings.pinecone_api_key).Index(settings.pinecone_index)


def _to_ascii_id(path: str) -> str:
    """한글이 섞인 경로를 Pinecone ID로 쓸 수 있는 ASCII로 변환.

    Pinecone ID는 ASCII만 허용한다. 경로가 "concepts/2026-08-01-리액트.md" 처럼
    한글을 포함하므로 base64url 로 인코딩한다.
    ★ 같은 경로 → 항상 같은 ID 여야 재색인 시 덮어쓰기(upsert)가 성립한다.

    TS 대응: pinecone.ts:20-22  Buffer.from(path).toString("base64url")

    ★ rstrip("=") 이 중요하다. Node 의 base64url 은 패딩 "=" 을 제거하는데
      파이썬 urlsafe_b64encode 는 남긴다. 그대로 두면 TS 가 만든 기존 벡터와
      ID 가 달라져서, 같은 노트가 두 벌 들어간다(덮어쓰기가 안 된다).
    """
    return base64.urlsafe_b64encode(path.encode()).decode().rstrip("=")


async def upsert_note(*, title: str, path: str, summary: str) -> None:
    """노트를 벡터로 만들어 저장.

    ★ small-to-big 의 '저장' 쪽:
      원본 전체가 아니라 **요약**을 임베딩한다.
      이유 — 요약은 노이즈가 적어 검색 정확도가 높고, 원본은 GitHub에 있으니
             벡터DB에 본문을 중복 저장할 이유가 없다.
      metadata.path 가 원본으로 가는 포인터 역할을 한다.

    TS 대응: pinecone.ts:55-76
    """
    vector = await gemini.embed(summary, is_query=False)  # 문서 쪽 task_type
    await asyncio.to_thread(
        _index().upsert,
        vectors=[
            {
                "id": _to_ascii_id(path),
                "values": vector,
                "metadata": {"title": title, "path": path, "summary": summary},
            }
        ],
    )


async def _search(text: str, *, top_k: int, is_query: bool) -> list[NoteHit]:
    """임베딩 → 유사도 검색 → NoteHit 목록. **점수로 거르지 않는다.**

    query() 와 find_related() 가 공유한다. TS 에서는 이 코드가 두 벌이었고
    (pinecone.ts:26-41 / 82-102), 임계값만 달랐다.
    """
    vector = await gemini.embed(text, is_query=is_query)
    result = await asyncio.to_thread(
        _index().query,
        vector=vector,
        top_k=top_k,
        include_metadata=True,
    )
    hits = []
    for match in result.get("matches") or []:
        # metadata 가 통째로 없을 수 있다 (색인 방식이 바뀐 옛 벡터)
        meta = match.get("metadata") or {}
        hits.append(
            NoteHit(
                title=meta.get("title", ""),
                path=meta.get("path", ""),
                score=match.get("score") or 0.0,
            )
        )
    return hits


async def query(question: str, top_k: int = 5) -> list[NoteHit]:
    """질문과 의미가 가까운 노트를 '찾기'만 한다. 본문 로드는 하지 않는다.

    점수를 그대로 돌려주므로 **호출한 쪽이 임계값을 정해 잘라야 한다.**
    (services/retrieval.py 참고)

    TS 대응: pinecone.ts:82-102
    """
    return await _search(question, top_k=top_k, is_query=True)


async def find_related(text: str, top_k: int = 3) -> list[NoteHit]:
    """새 노트와 관련된 기존 노트 후보. Obsidian [[링크]] 생성용.

    ★ 관련 노트를 LLM에게 묻지 않고 벡터 유사도로 찾는 이유:
      LLM은 존재하지 않는 노트 제목을 그럴듯하게 지어낸다.
      벡터 검색은 실제로 인덱스에 있는 것만 돌려준다.

    ★ 호출 시점 주의: 반드시 upsert_note 전에 호출해야 한다.
      저장 후에 부르면 방금 넣은 노트가 자기 자신과 매칭된다(self-match).

    TS 대응: pinecone.ts:26-41
    """
    return await _search(text, top_k=top_k, is_query=True)


async def clear_index() -> None:
    """인덱스 전체 비우기. 재색인(sync) 전에 호출.

    옛 방식으로 만들어진 벡터가 새 벡터와 섞이면 점수 분포가 망가지므로
    재색인은 '지우고 다시'가 원칙.

    TS 대응: pinecone.ts:44-52
    """
    try:
        await asyncio.to_thread(_index().delete, delete_all=True)
    except Exception as exc:
        # 인덱스가 이미 비어 있으면 "namespace not found" / 404 가 난다.
        # 이건 실패가 아니라 원하는 상태이므로 삼킨다.
        if not _NOT_FOUND.search(str(exc)):
            raise
