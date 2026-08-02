"""Pinecone 어댑터 — 벡터 저장/검색.

TS 원본: src/lib/pinecone.ts

★ 파이썬 특유의 함정: pinecone SDK는 동기(blocking) 라이브러리다.
  FastAPI의 async 핸들러 안에서 그냥 호출하면 그 순간 이벤트 루프 전체가 멈춰서
  다른 요청도 같이 대기한다. 반드시 asyncio.to_thread 로 감싸 별도 스레드로 보낼 것.
      results = await asyncio.to_thread(index.query, vector=..., top_k=...)
  TS에는 없던 고민 — Node는 SDK가 애초에 전부 비동기였다.

=== 3단계에서 구현 ===
"""

from app.schemas.chat import NoteHit

# ★ 실측 튜닝값(2026-07-14): 관련 0.64+, 무관 0.58- 사이의 골.
#   Gemini 임베딩은 무관한 문서도 점수가 높게 눌려 나와서 0.5는 너무 낮다.
#   이 값이 abstention(모르면 보류) 동작을 좌우하는 유일한 손잡이다.
THRESHOLD = 0.6
RELATED_THRESHOLD = 0.6


def _index():
    """Pinecone 인덱스 핸들 (지연 생성 + 재사용).

    TS 대응: pinecone.ts:4-17 — 모듈 전역에 클라이언트를 캐시하는 패턴

    TODO(3단계): 구현
      힌트 — from pinecone import Pinecone
             Pinecone(api_key=...).Index(settings.pinecone_index)
             @lru_cache 를 쓰면 TS의 `let client = null` 패턴을 대체할 수 있다
    """
    raise NotImplementedError


def _to_ascii_id(path: str) -> str:
    """한글이 섞인 경로를 Pinecone ID로 쓸 수 있는 ASCII로 변환.

    Pinecone ID는 ASCII만 허용한다. 경로가 "concepts/2026-08-01-리액트.md" 처럼
    한글을 포함하므로 base64url 로 인코딩한다.
    ★ 같은 경로 → 항상 같은 ID 여야 재색인 시 덮어쓰기(upsert)가 성립한다.

    TS 대응: pinecone.ts:20-22  Buffer.from(path).toString("base64url")

    TODO(3단계): 구현
      힌트 — import base64
             base64.urlsafe_b64encode(path.encode()).decode()
             ※ 파이썬은 패딩 "=" 을 남기고 Node의 base64url 은 제거한다.
               기존 인덱스와 ID를 맞추려면 .rstrip("=") 필요 — 새로 색인할 거면 상관없음.
               (어느 쪽이든 정하고 나면 바꾸지 말 것. 바꾸면 중복 벡터가 생긴다)
    """
    raise NotImplementedError


async def upsert_note(*, title: str, path: str, summary: str) -> None:
    """노트를 벡터로 만들어 저장.

    ★ small-to-big 의 '저장' 쪽:
      원본 전체가 아니라 **요약**을 임베딩한다.
      이유 — 요약은 노이즈가 적어 검색 정확도가 높고, 원본은 GitHub에 있으니
             벡터DB에 본문을 중복 저장할 이유가 없다.
      metadata.path 가 원본으로 가는 포인터 역할을 한다.

    TS 대응: pinecone.ts:55-76

    TODO(3단계): 구현
      1. vector = await gemini.embed(summary, is_query=False)   ← 문서 쪽 task_type
      2. await asyncio.to_thread(
             _index().upsert,
             vectors=[{"id": _to_ascii_id(path), "values": vector,
                       "metadata": {"title": title, "path": path, "summary": summary}}],
         )
      ※ 파이썬 SDK는 upsert(vectors=[...]), TS는 upsert({records:[...]}) — 인자 이름이 다르다
    """
    raise NotImplementedError


async def query(question: str, top_k: int = 5) -> list[NoteHit]:
    """질문과 의미가 가까운 노트를 '찾기'만 한다. 본문 로드는 하지 않는다.

    ★ 여기서 THRESHOLD 미만을 잘라내는 게 abstention 의 출발점이다.
      결과가 0건이면 상위 로직(services/retrieval.py)이 "모르겠다"고 답하게 된다.
      임계값을 낮추면 없는 얘기를 지어내기 시작하니 함부로 내리지 말 것.

    TS 대응: pinecone.ts:82-102

    TODO(3단계): 구현
      1. vector = await gemini.embed(question, is_query=True)   ← 질문 쪽 task_type
      2. results = await asyncio.to_thread(_index().query, vector=vector,
                                           top_k=top_k, include_metadata=True)
      3. score >= THRESHOLD 인 것만 NoteHit(title, path, score) 로 변환해 반환
         metadata 가 없을 수 있으니 (m.metadata or {}).get("title", "") 식으로 방어
    """
    raise NotImplementedError


async def find_related(text: str, top_k: int = 3) -> list[str]:
    """새 노트와 관련된 기존 노트 '제목' 목록. Obsidian [[링크]] 생성용.

    ★ 관련 노트를 LLM에게 묻지 않고 벡터 유사도로 찾는 이유:
      LLM은 존재하지 않는 노트 제목을 그럴듯하게 지어낸다.
      벡터 검색은 실제로 인덱스에 있는 것만 돌려준다.

    ★ 호출 시점 주의: 반드시 upsert_note 전에 호출해야 한다.
      저장 후에 부르면 방금 넣은 노트가 자기 자신과 매칭된다(self-match).

    TS 대응: pinecone.ts:26-41

    TODO(3단계): 구현
      query() 와 거의 같되 RELATED_THRESHOLD 로 거르고 title 문자열만 반환.
      빈 title 은 제외.
    """
    raise NotImplementedError


async def clear_index() -> None:
    """인덱스 전체 비우기. 재색인(sync) 전에 호출.

    옛 방식으로 만들어진 벡터가 새 벡터와 섞이면 점수 분포가 망가지므로
    재색인은 '지우고 다시'가 원칙.

    TS 대응: pinecone.ts:44-52

    TODO(7단계): 구현
      delete_all 호출. 단, 인덱스가 비어 있으면 "namespace not found" / 404 가
      날 수 있는데 이건 실패가 아니므로 삼켜야 한다 (TS도 동일하게 처리).
    """
    raise NotImplementedError
